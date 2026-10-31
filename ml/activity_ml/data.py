"""Load the Kaggle run-or-walk dataset and cut it into labelled windows.

Findings from the data (see docs/ml-report.md):
- `time` is H:M:S:nanoseconds; samples are 0.2 s apart, so the rate is 5 Hz.
- Recordings come as ~11 s sessions separated by gaps; a few rows are out of
  order, so rows are sorted by time and split into sessions on gaps > 1 s or
  a change of activity or wrist. Windows never cross a session boundary.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from activity_ml.preprocess import sliding_windows

SENSOR_COLUMNS = [
    "acceleration_x",
    "acceleration_y",
    "acceleration_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
]
LABELS = ("walk", "run")  # index = dataset `activity` value
SESSION_GAP_S = 1.0


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    hms = df["time"].str.split(":", expand=True).astype(int)
    df["t"] = hms[0] * 3600 + hms[1] * 60 + hms[2] + hms[3] / 1e9
    df = df.sort_values(["date", "t"], kind="stable").reset_index(drop=True)

    gap = df.groupby("date")["t"].diff()
    new_session = (
        gap.isna()
        | (gap > SESSION_GAP_S)
        | (df["activity"] != df["activity"].shift())
        | (df["wrist"] != df["wrist"].shift())
    )
    df["session"] = new_session.cumsum() - 1
    return df


def make_windows(
    df: pd.DataFrame, window: int, stride: int = 1
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Windows (M, window, 6), labels (M,) and per-window date/wrist/session info."""
    xs, ys, info = [], [], []
    for session, rows in df.groupby("session", sort=True):
        windows = sliding_windows(rows[SENSOR_COLUMNS].to_numpy(), window, stride)
        if len(windows) == 0:
            continue
        first = rows.iloc[0]
        xs.append(windows)
        ys.append(np.full(len(windows), first["activity"], dtype=np.int64))
        info.append(
            pd.DataFrame(
                {"date": first["date"], "wrist": first["wrist"], "session": session},
                index=range(len(windows)),
            )
        )
    return np.concatenate(xs), np.concatenate(ys), pd.concat(info, ignore_index=True)


OWN_COLUMNS = ["ax", "ay", "az", "gx", "gy", "gz"]


def load_own(paths: list[Path]) -> pd.DataFrame:
    """Labelled recordings from the board (tools/record.py), split into sessions.

    A session is a run of samples with the same label and no gap over 3 s. Each sample's
    time is its batch timestamp plus 200 ms per position in the batch (5 Hz).
    """
    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    df = df.drop_duplicates(["device_id", "batch_ts_ms", "sample_index"])
    df = df.sort_values(["batch_ts_ms", "sample_index"], kind="stable").reset_index(drop=True)
    df["t"] = df["batch_ts_ms"] + df["sample_index"] * 200
    gap = df["t"].diff().fillna(0)
    df["session"] = ((df["label"] != df["label"].shift()) | (gap > 3000)).cumsum() - 1
    return df


def own_windows(
    df: pd.DataFrame, window: int, trim: int = 10
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Windows (M, window, 6), string labels, the time (ms) of each window's last sample,
    and each window's session. Windows are consecutive (stride 1) within a session.

    The first and last `trim` samples (2 s) of each session are dropped: around a button
    press the wearer is still starting or stopping the activity.
    """
    xs, labels, times, sessions = [], [], [], []
    for session, rows in df.groupby("session", sort=True):
        rows = rows.iloc[trim : len(rows) - trim]
        windows = sliding_windows(rows[OWN_COLUMNS].to_numpy(), window)
        if len(windows) == 0:
            continue
        xs.append(windows)
        labels.append(np.full(len(windows), rows["label"].iloc[0]))
        times.append(rows["t"].to_numpy()[window - 1 :])
        sessions.append(np.full(len(windows), session))
    return (
        np.concatenate(xs),
        np.concatenate(labels),
        np.concatenate(times),
        np.concatenate(sessions),
    )
