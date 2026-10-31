"""Dataset facts and figures behind docs/ml-report.md and the contract's units.

Saves results/dataset_facts.json and two figures in docs/ml/:
- signals.png: y-acceleration and |gyro| over 10 s of walking vs running
- posture.png: mean acceleration per axis, walking vs running

Usage: uv run python explore.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from activity_ml.data import LABELS, SENSOR_COLUMNS, load_dataset  # noqa: E402

DATA = Path("data/dataset.csv")
FIG_DIR = Path("../docs/ml")
FACTS = Path("results/dataset_facts.json")

# Reference data-viz palette (light mode): categorical slots 1-2, ink and chrome.
COLORS = {"walk": "#2a78d6", "run": "#eb6834"}
SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelcolor=INK_2, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def facts(df) -> dict:
    dt = df.groupby("session")["t"].diff().dropna()
    acc = df[SENSOR_COLUMNS[:3]].to_numpy()
    gyr = df[SENSOR_COLUMNS[3:]].to_numpy()
    acc_mag, gyr_mag = np.linalg.norm(acc, axis=1), np.linalg.norm(gyr, axis=1)
    by_activity = {}
    for code, name in enumerate(LABELS):
        m = (df["activity"] == code).to_numpy()
        by_activity[name] = {
            "rows": int(m.sum()),
            "accel_magnitude_mean_g": round(float(acc_mag[m].mean()), 3),
            "accel_magnitude_median_g": round(float(np.median(acc_mag[m])), 3),
            "gyro_magnitude_mean_rad_s": round(float(gyr_mag[m].mean()), 3),
            "accel_axis_mean_g": dict(
                zip("xyz", np.round(acc[m].mean(0), 3).tolist(), strict=True)
            ),
        }
    sessions = df.groupby("session").size()
    return {
        "rows": len(df),
        "users": sorted(df["username"].unique().tolist()),
        "recording_days": int(df["date"].nunique()),
        "sessions": int(len(sessions)),
        "session_length_median_samples": int(sessions.median()),
        "sample_interval_median_s": round(float(dt.median()), 4),
        "sample_rate_hz": round(1 / float(dt.median()), 2),
        "wrist_rows": {
            "left": int((df["wrist"] == 0).sum()),
            "right": int((df["wrist"] == 1).sum()),
        },
        "accel_range_g": [round(float(acc.min()), 2), round(float(acc.max()), 2)],
        "gyro_range_rad_s": [round(float(gyr.min()), 2), round(float(gyr.max()), 2)],
        "by_activity": by_activity,
    }


def end_labels(ax, ends: dict[str, float], min_gap: float) -> None:
    """Direct labels at the right end of each line, pushed apart if they would overlap."""
    (low_name, low), (high_name, high) = sorted(ends.items(), key=lambda kv: kv[1])
    if high - low < min_gap:
        middle = (high + low) / 2
        low, high = middle - min_gap / 2, middle + min_gap / 2
    for name, y in ((low_name, low), (high_name, high)):
        ax.annotate(name, (10.0, y), xytext=(4, 0), textcoords="offset points",
                    va="center", color=INK_2, fontsize=9)


def signals_figure(df) -> None:
    """10 s of each activity, same (left) wrist, first long-enough session of each."""
    seconds = np.arange(50) / 5
    fig, axes = plt.subplots(2, 1, figsize=(8, 5.2), sharex=True, facecolor=SURFACE)
    ends = [{}, {}]
    for code, name in enumerate(LABELS):
        sizes = df[(df["activity"] == code) & (df["wrist"] == 0)].groupby("session").size()
        rows = df[df["session"] == sizes[sizes >= 50].index[0]].iloc[:50]
        acc_y = rows["acceleration_y"].to_numpy()
        gyr = np.linalg.norm(rows[SENSOR_COLUMNS[3:]].to_numpy(), axis=1)
        for i, (ax, values) in enumerate(zip(axes, (acc_y, gyr), strict=True)):
            ax.plot(seconds, values, color=COLORS[name], linewidth=2, label=name,
                    solid_joinstyle="round", solid_capstyle="round")
            ends[i][name] = values[-1]
    axes[0].set_title("acceleration y (g): about −1 g walking (arm hangs), near 0 running "
                      "(arm bent)", loc="left", color=INK, fontsize=11)
    axes[1].set_title("|angular rate| (rad/s): faster, larger arm rotation when running",
                      loc="left", color=INK, fontsize=11)
    for ax, end in zip(axes, ends, strict=True):
        low, high = ax.get_ylim()
        end_labels(ax, end, min_gap=0.08 * (high - low))
    axes[1].set_xlabel("time (s), 5 samples per second", color=INK_2)
    axes[0].legend(loc="upper left", frameon=False, labelcolor=INK_2, ncol=2)
    for ax in axes:
        style(ax)
        ax.set_xlim(0, 10.6)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "signals.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)


def posture_figure(info: dict) -> None:
    axes_names = ["x", "y", "z"]
    x = np.arange(3)
    width = 0.32
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=SURFACE)
    for i, name in enumerate(LABELS):
        means = [info["by_activity"][name]["accel_axis_mean_g"][a] for a in axes_names]
        bars = ax.bar(x + (i - 0.5) * width, means, width, color=COLORS[name], label=name,
                      edgecolor=SURFACE, linewidth=2)
        for bar, value in zip(bars, means, strict=True):
            ax.annotate(f"{value:+.2f}".replace("-", "−"),
                        (bar.get_x() + bar.get_width() / 2, value),
                        xytext=(0, -12 if value < 0 else 4), textcoords="offset points",
                        ha="center", color=INK_2, fontsize=9)
    ax.axhline(0, color=BASELINE, linewidth=1)
    ax.set_xticks(x, [f"accel {a}" for a in axes_names])
    ax.set_ylabel("mean acceleration (g)", color=INK_2)
    ax.set_ylim(-1.15, 0.25)
    ax.set_title("Gravity sits on −y while walking (arm down) and moves off it when running "
                 "(arm bent)", loc="left", color=INK, fontsize=11)
    ax.legend(loc="lower right", frameon=False, labelcolor=INK_2, ncol=2)
    style(ax)
    ax.spines["bottom"].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "posture.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    df = load_dataset(DATA)
    info = facts(df)
    FACTS.parent.mkdir(parents=True, exist_ok=True)
    FACTS.write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    signals_figure(df)
    posture_figure(info)
    print(f"saved {FACTS}, {FIG_DIR / 'signals.png'}, {FIG_DIR / 'posture.png'}")


if __name__ == "__main__":
    main()
