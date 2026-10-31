"""Compare models on splits that test generalization, and save the results.

Protocols
- leave-one-day-out: 12 folds; train on 11 recording days, test on the 12th.
  Windows overlap, so a random split would leak near-copies of test windows
  into training; splitting by day prevents that.
- rotated device: the same leave-one-day-out models, tested on the held-out
  day after a fixed random 3D rotation of all its data. This simulates the
  real deployment risk: a different device (the RT-Spark) worn in a different
  orientation than the iPhone that recorded the dataset.
- cross-wrist: train on left-wrist data and test on right-wrist data, and the
  reverse.

Models
- baseline:        window statistics + logistic regression (ignores time order)
- baseline_rotate: the same, trained on randomly rotated/mirrored windows
- cnn:             1D-CNN, no augmentation
- cnn_mirror:      1D-CNN trained with left/right wrist mirroring
- cnn_rotate:      1D-CNN trained with mirroring + random 3D rotations

Usage: uv run python evaluate.py [--windows 10 20] [--out results/evaluation.json]
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from activity_ml.data import load_dataset, make_windows
from activity_ml.training import (
    TRAIN_STRIDE,
    augment,
    fit_baseline,
    fit_cnn,
    predict_proba,
    random_rotations,
    window_features,
)

MODELS = {
    "baseline": "none",
    "baseline_rotate": "rotate",
    "cnn": "none",
    "cnn_mirror": "mirror",
    "cnn_rotate": "rotate",
}
WRISTS = {0: "left", 1: "right"}


def train_and_predict(model: str, x_train, y_train, tests: list, seed: int) -> list[np.ndarray]:
    """Train one model, return its probabilities for each test set."""
    if model.startswith("baseline"):
        generator = torch.Generator().manual_seed(seed)
        x_aug = augment(torch.as_tensor(x_train), MODELS[model], generator).numpy()
        fitted = fit_baseline(x_aug, y_train)
        return [fitted.predict_proba(window_features(x)) for x in tests]
    cnn = fit_cnn(x_train, y_train, augmentation=MODELS[model], seed=seed)
    return [predict_proba(cnn, x) for x in tests]


def rotate_day(windows: np.ndarray, day: str, seed: int) -> np.ndarray:
    """Apply one fixed random rotation (seeded by the day) to all of a day's windows."""
    generator = torch.Generator().manual_seed(seed * 1000 + sum(map(ord, day)))
    rot = random_rotations(1, generator)[0].numpy()
    return np.concatenate([windows[..., :3] @ rot.T, windows[..., 3:] @ rot.T], axis=-1)


def scores(y: np.ndarray, probs: np.ndarray) -> dict:
    pred = probs.argmax(axis=1)
    return {
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "macro_f1": round(float(f1_score(y, pred, average="macro")), 4),
        "confusion": confusion_matrix(y, pred, labels=[0, 1]).tolist(),  # rows: true walk, run
        "n": int(len(y)),
    }


def evaluate(df, window: int, model: str, seed: int) -> dict:
    x_tr, y_tr, info_tr = make_windows(df, window, TRAIN_STRIDE)
    x_te, y_te, info_te = make_windows(df, window, stride=1)

    probs = np.zeros((len(x_te), 2))
    probs_rotated = np.zeros((len(x_te), 2))
    per_day, per_day_rotated = {}, {}
    for day in sorted(info_te["date"].unique()):
        train, test = (info_tr["date"] != day).to_numpy(), (info_te["date"] == day).to_numpy()
        tests = [x_te[test], rotate_day(x_te[test], day, seed)]
        probs[test], probs_rotated[test] = train_and_predict(
            model, x_tr[train], y_tr[train], tests, seed
        )
        per_day[day] = round(float((probs[test].argmax(1) == y_te[test]).mean()), 4)
        per_day_rotated[day] = round(float((probs_rotated[test].argmax(1) == y_te[test]).mean()), 4)
    result = {
        "leave_one_day_out": {**scores(y_te, probs), "per_day_accuracy": per_day},
        "rotated_device": {**scores(y_te, probs_rotated), "per_day_accuracy": per_day_rotated},
    }

    for train_wrist, test_wrist in ((0, 1), (1, 0)):
        train = (info_tr["wrist"] == train_wrist).to_numpy()
        test = (info_te["wrist"] == test_wrist).to_numpy()
        [p] = train_and_predict(model, x_tr[train], y_tr[train], [x_te[test]], seed)
        result[f"{WRISTS[train_wrist]}_to_{WRISTS[test_wrist]}"] = scores(y_te[test], p)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", type=Path, default=Path("data/dataset.csv"))
    parser.add_argument("--windows", type=int, nargs="+", default=[10, 20])
    parser.add_argument("--models", nargs="+", choices=list(MODELS), default=list(MODELS))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=Path("results/evaluation.json"))
    args = parser.parse_args()

    df = load_dataset(args.data)
    results = {}
    for window in args.windows:
        for model in args.models:
            start = time.time()
            r = evaluate(df, window, model, args.seed)
            results[f"{model}_w{window}"] = {"model": model, "window": window, **r}
            print(
                f"{model:<15} W={window:<3} day-out {r['leave_one_day_out']['accuracy']:.4f} "
                f"| rotated {r['rotated_device']['accuracy']:.4f} "
                f"| L→R {r['left_to_right']['accuracy']:.4f} "
                f"R→L {r['right_to_left']['accuracy']:.4f}  ({time.time() - start:.0f}s)",
                flush=True,
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
