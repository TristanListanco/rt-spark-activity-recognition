"""How do the models do on data recorded with the board (data/own, tools/record.py)?

1. Transfer: each model type from evaluate.py is trained on all of the Kaggle (iPhone)
   data and tested on the board recordings, as is the deployed 2-class ONNX model.
   These models have no "idle" class; for idle windows we report what they predict.
2. Three classes (walk, run, idle): the rotation-trained CNN is trained on Kaggle data
   plus board data. With one recording session per activity, each session is cut into
   4 consecutive time blocks; each block is tested by a model that didn't see it (with
   a 10-window gap, so no training window shares samples with a test window). Each fold
   also holds out 3 Kaggle recording days, to check walk/run on unseen Kaggle days.

Usage: uv run python evaluate_own.py [--out results/own_evaluation.json]
"""

import argparse
import collections
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from sklearn.metrics import confusion_matrix

from activity_ml.data import LABELS, load_dataset, load_own, make_windows, own_windows
from activity_ml.model import CLASSES
from activity_ml.training import TRAIN_STRIDE, fit_cnn, predict_proba, with_own_data
from evaluate import MODELS, train_and_predict

WINDOW = 10  # for the transfer test: the window the 2-class models were trained with
FOLDS = 4
# Three-class settings compared (window, repeat, balance_classes); the deployed model
# uses CHOSEN. It was picked using these same folds, so its numbers are optimistic.
VARIANTS = {
    "w10_repeat10_balanced": (10, 10, True),
    "w10_repeat10_unweighted": (10, 10, False),
    "w10_repeat5_unweighted": (10, 5, False),
    "w20_repeat10_balanced": (20, 10, True),
    "w20_repeat10_unweighted": (20, 10, False),
}
CHOSEN = "w20_repeat10_balanced"


def summarize(pred: np.ndarray, truth: np.ndarray) -> dict:
    walk_run = truth != "idle"
    result = {
        "walk_run_accuracy": round(float((pred[walk_run] == truth[walk_run]).mean()), 4),
        "windows": int(walk_run.sum()),
    }
    for label in ("walk", "run"):
        m = truth == label
        result[f"{label}_recall"] = round(float((pred[m] == label).mean()), 4)
    idle = truth == "idle"
    if idle.any():
        counts = collections.Counter(pred[idle].tolist())
        result["idle_predicted_as"] = {k: round(v / idle.sum(), 4) for k, v in counts.items()}
    return result


def blocks(sessions: np.ndarray, folds: int) -> np.ndarray:
    """Fold number of each window: each session's windows cut into `folds` time blocks."""
    out = np.zeros(len(sessions), dtype=int)
    for s in np.unique(sessions):
        idx = np.flatnonzero(sessions == s)
        out[idx] = np.arange(len(idx)) * folds // len(idx)
    return out


def three_class_cv(
    kaggle, own, seed: int, window: int = WINDOW, repeat: int = 10, balance: bool = True
) -> dict:
    x_own, y_own, _, s_own = own_windows(own, window)
    x_k, y_k, info_k = make_windows(kaggle, window, TRAIN_STRIDE)
    x_kt, y_kt, info_kt = make_windows(kaggle, window, stride=1)
    days = sorted(info_k["date"].unique())
    fold_of_day = {day: i % FOLDS for i, day in enumerate(days)}
    block = blocks(s_own, FOLDS)
    index = {name: i for i, name in enumerate(CLASSES)}
    y_own_i = np.array([index[label] for label in y_own])

    own_pred = np.full(len(x_own), -1)
    kaggle_correct = kaggle_total = kaggle_as_idle = 0
    for k in range(FOLDS):
        test = block == k
        # train windows at least WINDOW positions away from any test window of their session
        near = np.zeros(len(x_own), dtype=bool)
        for s in np.unique(s_own):
            idx = np.flatnonzero(s_own == s)
            t_idx = idx[test[idx]]
            if len(t_idx):
                lo, hi = t_idx.min(), t_idx.max()
                near[idx] = (idx > lo - window) & (idx < hi + window)
        train_own = ~test & ~near

        k_train = info_k["date"].map(fold_of_day).to_numpy() != k
        x_train, y_train = with_own_data(
            x_k[k_train], y_k[k_train], x_own[train_own], y_own[train_own], repeat=repeat
        )
        model = fit_cnn(x_train, y_train, augmentation="rotate", seed=seed,
                        n_classes=len(CLASSES), balance_classes=balance)
        own_pred[test] = predict_proba(model, x_own[test]).argmax(1)

        k_test = info_kt["date"].map(fold_of_day).to_numpy() == k
        k_pred = predict_proba(model, x_kt[k_test]).argmax(1)
        kaggle_correct += int((k_pred == y_kt[k_test]).sum())
        kaggle_as_idle += int((k_pred == index["idle"]).sum())
        kaggle_total += int(k_test.sum())
        print(f"  fold {k}: board accuracy {np.mean(own_pred[test] == y_own_i[test]):.4f}, "
              f"Kaggle held-out days {np.mean(k_pred == y_kt[k_test]):.4f}")

    recall = {name: round(float(np.mean(own_pred[y_own_i == i] == i)), 4)
              for i, name in enumerate(CLASSES)}
    walk_run = y_own_i != index["idle"]
    walk_run_accuracy = np.mean(own_pred[walk_run] == y_own_i[walk_run])
    return {
        "board_accuracy": round(float(np.mean(own_pred == y_own_i)), 4),
        "board_walk_run_accuracy": round(float(walk_run_accuracy), 4),
        "board_recall": recall,
        "board_confusion": confusion_matrix(y_own_i, own_pred, labels=range(len(CLASSES))).tolist(),
        "kaggle_heldout_days_accuracy": round(kaggle_correct / kaggle_total, 4),
        "kaggle_windows_predicted_idle": round(kaggle_as_idle / kaggle_total, 4),
        "classes": list(CLASSES),
        "settings": {"window": window, "repeat": repeat, "balance_classes": balance},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", type=Path, default=Path("data/dataset.csv"))
    parser.add_argument("--own", type=Path, default=Path("data/own"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=Path("results/own_evaluation.json"))
    args = parser.parse_args()

    own = load_own(sorted(args.own.glob("*.csv")))
    x_own, y_own, _, s_own = own_windows(own, WINDOW)
    sessions = own.groupby("session")["label"].first().value_counts().to_dict()
    print(f"own data: {len(own)} samples, sessions per label {sessions}, {len(x_own)} windows")

    kaggle = load_dataset(args.data)
    x_tr, y_tr, _ = make_windows(kaggle, WINDOW, TRAIN_STRIDE)
    labels = np.array(LABELS)
    results = {}
    for model in MODELS:
        [probs] = train_and_predict(model, x_tr, y_tr, [x_own], args.seed)
        results[model] = summarize(labels[probs.argmax(1)], y_own)
        print(f"{model:<16} {results[model]}")

    # the M2 model, while it is still the deployed one (train.py replaces it with the
    # 3-class model, which has seen all of the board data)
    meta = json.loads(Path("models/model_meta.json").read_text())
    if meta["output"]["labels"] == list(LABELS) and meta["window"] == WINDOW:
        session = ort.InferenceSession("models/model.onnx", providers=["CPUExecutionProvider"])
        probs = session.run(None, {"imu": x_own.astype(np.float32)})[0]
        results["deployed_m2_onnx"] = summarize(labels[probs.argmax(1)], y_own)
        print(f"{'deployed_m2_onnx':<16} {results['deployed_m2_onnx']}")

    print("three classes, blocked cross-validation:")
    three = {}
    for name, (window, repeat, balance) in VARIANTS.items():
        three[name] = three_class_cv(kaggle, own, args.seed, window, repeat, balance)
        r = three[name]
        print(f"  {name:<26} board {r['board_accuracy']:.4f} recall {r['board_recall']} "
              f"kaggle days {r['kaggle_heldout_days_accuracy']:.4f}")

    out = {"own_data": {"samples": int(len(own)), "sessions_per_label": sessions,
                        "windows": int(len(x_own))},
           "kaggle_trained_on_own": results,
           "three_class_blocked_cv": {"chosen": CHOSEN, "variants": three}}
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
