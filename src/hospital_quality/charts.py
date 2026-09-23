"""Matplotlib figures for the README and results document."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

INK = "#1f2937"
ACCENT = "#2563eb"
MUTED = "#9ca3af"
STAR_COLORS = ["#b91c1c", "#f97316", "#d1d5db", "#60a5fa", "#1d4ed8"]


def ownership_distribution(ownership: pd.DataFrame, path: Path) -> None:
    frame = ownership.set_index("ownership_group")
    counts = frame[[f"stars_{i}" for i in range(1, 6)]]
    shares = counts.div(counts.sum(axis=1), axis=0) * 100
    fig, ax = plt.subplots(figsize=(9, 3.2))
    left = pd.Series(0.0, index=shares.index)
    for i, color in zip(range(1, 6), STAR_COLORS):
        column = shares[f"stars_{i}"]
        ax.barh(shares.index, column, left=left, color=color, label=f"{i} star")
        left += column
    labels = [f"{name}  (n={n})" for name, n in frame["hospitals"].items()]
    ax.set_yticks(range(len(labels)), labels)
    ax.invert_yaxis()
    ax.set_xlabel("% of rated acute care hospitals")
    ax.set_title("CMS overall star rating by ownership", loc="left", color=INK)
    ax.legend(ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.28), loc="upper center")
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def state_means(states: pd.DataFrame, national_mean: float, path: Path, highlight: str = "AZ") -> None:
    frame = states.sort_values("mean_stars")
    fig, ax = plt.subplots(figsize=(7, 9))
    y = range(len(frame))
    colors = [ACCENT if s == highlight else INK for s in frame["state"]]
    ax.hlines(y, frame["ci_low"], frame["ci_high"], color=MUTED, linewidth=2)
    ax.scatter(frame["mean_stars"], y, color=colors, zorder=3, s=18)
    ax.axvline(national_mean, color=MUTED, linestyle="--", linewidth=1)
    ax.set_yticks(list(y), [f"{s} ({n})" for s, n in zip(frame["state"], frame["hospitals"])], fontsize=7)
    ax.set_xlabel("Mean star rating, 95% bootstrap CI (dashed = national)")
    ax.set_title("States with at least 15 rated acute care hospitals", loc="left", color=INK)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def readmission_by_stars(frame: pd.DataFrame, path: Path) -> None:
    groups = [frame.loc[frame["stars"] == s, "mean_ratio"].to_numpy() for s in range(1, 6)]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.boxplot(groups, tick_labels=[str(s) for s in range(1, 6)], showfliers=False)
    ax.axhline(1.0, color=MUTED, linestyle="--", linewidth=1)
    ax.set_xlabel("Overall star rating")
    ax.set_ylabel("Mean excess readmission ratio")
    ax.set_title("HRRP excess readmission ratio by star rating", loc="left", color=INK)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
