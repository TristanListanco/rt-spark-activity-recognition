"""Train the final model on all data and export it for the classifier service.

Writes
- models/model.onnx       input "imu": (N, W, 6) raw windows in g and rad/s
                          output "probs": (N, 2) probabilities for [walk, run]
- models/model_meta.json  window, rate, labels, training settings, checksum,
                          and the evaluation scores of this configuration

The settings default to the configuration chosen from results/evaluation.json
(see docs/ml-report.md).

Usage: uv run python train.py [--window 10] [--augmentation mirror]
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch

from activity_ml.data import LABELS, load_dataset, make_windows
from activity_ml.model import CHANNELS, WithSoftmax, parameter_count
from activity_ml.preprocess import AXES, RATE_HZ
from activity_ml.training import AUGMENTATIONS, TRAIN_STRIDE, fit_cnn, predict_proba

AUGMENTATION_TO_MODEL = {"none": "cnn", "mirror": "cnn_mirror", "rotate": "cnn_rotate"}


def export_onnx(model: torch.nn.Module, window: int, path: Path) -> None:
    wrapped = WithSoftmax(model).eval()
    example = torch.zeros(2, window, len(AXES))
    torch.onnx.export(
        wrapped,
        (example,),
        path,
        input_names=["imu"],
        output_names=["probs"],
        dynamic_shapes={"x": {0: torch.export.Dim("batch", min=1)}},
        external_data=False,
        dynamo=True,
    )
    onnx.checker.check_model(onnx.load(path))


def check_onnx_matches(model, path: Path, windows: np.ndarray) -> float:
    """Largest difference between PyTorch and ONNX Runtime probabilities."""
    session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    onnx_probs = session.run(["probs"], {"imu": windows.astype(np.float32)})[0]
    single = session.run(["probs"], {"imu": windows[:1].astype(np.float32)})[0]  # batch of 1
    torch_probs = predict_proba(model, windows)
    assert single.shape == (1, 2)
    return float(np.abs(onnx_probs - torch_probs).max())


def inference_ms(path: Path, window: int, runs: int = 500) -> float:
    session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    x = np.zeros((1, window, len(AXES)), dtype=np.float32)
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        session.run(["probs"], {"imu": x})
        times.append(time.perf_counter() - start)
    return round(float(np.median(times)) * 1000, 4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", type=Path, default=Path("data/dataset.csv"))
    parser.add_argument("--window", type=int, default=10)
    parser.add_argument("--augmentation", choices=AUGMENTATIONS, default="rotate")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--evaluation", type=Path, default=Path("results/evaluation.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("models"))
    args = parser.parse_args()

    df = load_dataset(args.data)
    windows, labels, _ = make_windows(df, args.window, TRAIN_STRIDE)
    print(f"training on {len(windows)} windows of {args.window} samples, aug={args.augmentation}")
    model = fit_cnn(windows, labels, augmentation=args.augmentation, seed=args.seed)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = args.out_dir / "model.onnx"
    export_onnx(model, args.window, onnx_path)
    check_windows, _, _ = make_windows(df, args.window, stride=37)
    max_diff = check_onnx_matches(model, onnx_path, check_windows)
    assert max_diff < 1e-5, f"ONNX output differs from PyTorch by {max_diff}"

    evaluation = None
    if args.evaluation.exists():
        key = f"{AUGMENTATION_TO_MODEL[args.augmentation]}_w{args.window}"
        evaluation = json.loads(args.evaluation.read_text()).get(key)

    meta = {
        "model_file": onnx_path.name,
        "sha256": hashlib.sha256(onnx_path.read_bytes()).hexdigest(),
        "input": {
            "name": "imu",
            "shape": ["batch", args.window, len(AXES)],
            "axes": list(AXES),
            "units": {"accel": "g, gravity included", "gyro": "rad/s"},
        },
        "output": {"name": "probs", "labels": list(LABELS)},
        "window": args.window,
        "rate_hz": RATE_HZ,
        "architecture": "8 channels (6 axes + |a| + |g|, standardized) → Conv1d(16, k=3) → ReLU "
        "→ Conv1d(16, k=3) → ReLU → global average pool → Linear(2) → softmax",
        "parameters": parameter_count(model),
        "channels": list(CHANNELS),
        "channel_mean": np.round(model.mean.numpy(), 5).tolist(),
        "channel_std": np.round(model.std.numpy(), 5).tolist(),
        "training": {
            "dataset": "Kaggle vmalyi/run-or-walk",
            "windows": int(len(windows)),
            "train_stride": TRAIN_STRIDE,
            "augmentation": args.augmentation,
            "seed": args.seed,
            "torch": torch.__version__,
        },
        "onnx_max_abs_diff_vs_torch": max_diff,
        "inference_ms_per_window": inference_ms(onnx_path, args.window),
        "evaluation": evaluation,
    }
    meta_path = args.out_dir / "model_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"saved {onnx_path} ({onnx_path.stat().st_size} bytes) and {meta_path}")
    print(f"parameters={meta['parameters']}  max|onnx-torch|={max_diff:.2e}  "
          f"inference={meta['inference_ms_per_window']} ms/window")


if __name__ == "__main__":
    main()
