"""Statistics for ordinal star ratings.

Star ratings are ordinal (1-5), so group comparisons use rank-based tests
(Kruskal-Wallis, Mann-Whitney) rather than t-tests. Means are still reported
because they are easy to read, but no inference relies on the ratings being
interval-scaled, except the state-adjusted difference, which is labelled as a
difference in mean stars.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def rank_biserial(x: np.ndarray, y: np.ndarray) -> float:
    """Effect size for Mann-Whitney: P(x > y) - P(x < y), in [-1, 1]."""
    u = stats.mannwhitneyu(x, y, alternative="two-sided").statistic
    return float(2 * u / (len(x) * len(y)) - 1)


def holm(pvalues: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, returned in the input order."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adjusted = np.empty(m)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (m - rank) * p[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def kruskal_by_group(frame: pd.DataFrame, group: str, value: str, min_size: int) -> dict:
    groups = {name: g[value].to_numpy() for name, g in frame.groupby(group) if len(g) >= min_size}
    h, p = stats.kruskal(*groups.values())
    n = sum(len(v) for v in groups.values())
    # epsilon-squared effect size for Kruskal-Wallis: H / (n - 1)
    return {"groups": sorted(groups), "n": n, "H": float(h), "p": float(p), "epsilon_sq": float(h / (n - 1))}


def pairwise_mann_whitney(frame: pd.DataFrame, group: str, value: str, min_size: int) -> pd.DataFrame:
    names = sorted(name for name, g in frame.groupby(group) if len(g) >= min_size)
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            x = frame.loc[frame[group] == a, value].to_numpy()
            y = frame.loc[frame[group] == b, value].to_numpy()
            p = stats.mannwhitneyu(x, y, alternative="two-sided").pvalue
            rows.append({"a": a, "b": b, "n_a": len(x), "n_b": len(y),
                         "rank_biserial": rank_biserial(x, y), "p": float(p)})
    table = pd.DataFrame(rows)
    table["p_holm"] = holm(table["p"].tolist())
    return table


def _within_strata_difference(values: np.ndarray, is_a: np.ndarray, strata: np.ndarray) -> float:
    """Weighted mean of per-stratum (mean_a - mean_b).

    Weights are n_a * n_b / n per stratum (the Cochran-Mantel-Haenszel weight),
    so a stratum with only one group contributes nothing, and a state with 3
    hospitals cannot outweigh one with 300.
    """
    total, weight_sum = 0.0, 0.0
    for s in np.unique(strata):
        mask = strata == s
        a = values[mask & is_a]
        b = values[mask & ~is_a]
        if len(a) == 0 or len(b) == 0:
            continue
        w = len(a) * len(b) / (len(a) + len(b))
        total += w * (a.mean() - b.mean())
        weight_sum += w
    return total / weight_sum


def stratified_permutation_test(
    frame: pd.DataFrame,
    group: str,
    a: str,
    b: str,
    strata: str,
    value: str,
    n_permutations: int = 10_000,
    seed: int = 0,
) -> dict:
    """Is group a rated differently from group b *within the same stratum*?

    Labels are shuffled only inside each stratum, so the null distribution keeps
    every state's mix of owners and ratings. This asks whether ownership
    matters after removing the part of the raw gap that is explained by which
    states each ownership type is concentrated in.
    """
    sub = frame[frame[group].isin([a, b])]
    values = sub[value].to_numpy(dtype=float)
    is_a = (sub[group] == a).to_numpy()
    strata_values = sub[strata].to_numpy()

    observed = _within_strata_difference(values, is_a, strata_values)
    naive = float(values[is_a].mean() - values[~is_a].mean())

    # Vectorised: for each stratum, draw every permutation at once. Within a
    # stratum n_a and n_b never change, so each permutation only needs the sum
    # of the values labelled a; mean_b follows from the stratum total.
    rng = np.random.default_rng(seed)
    blocks = [np.flatnonzero(strata_values == s) for s in np.unique(strata_values)]
    weighted = np.zeros(n_permutations)
    weight_sum = 0.0
    for idx in blocks:
        n_a = int(is_a[idx].sum())
        n_b = len(idx) - n_a
        if n_a == 0 or n_b == 0:
            continue
        labels = rng.permuted(np.tile(is_a[idx], (n_permutations, 1)), axis=1)
        block_values = values[idx]
        sum_a = labels @ block_values
        diff = sum_a / n_a - (block_values.sum() - sum_a) / n_b
        w = n_a * n_b / len(idx)
        weighted += w * diff
        weight_sum += w
    null = weighted / weight_sum
    extreme = int((np.abs(null) >= abs(observed) - 1e-12).sum())

    contributing = [s for s, idx in zip(np.unique(strata_values), blocks) if 0 < is_a[idx].sum() < len(idx)]
    return {
        "a": a,
        "b": b,
        "naive_difference": naive,
        "within_strata_difference": float(observed),
        # add-one correction: the observed labelling is itself one permutation
        "p_value": (extreme + 1) / (n_permutations + 1),
        "n_permutations": n_permutations,
        "strata_contributing": len(contributing),
        "hospitals": int(len(sub)),
    }


def bootstrap_mean_ci(values: np.ndarray, n_boot: int = 5_000, seed: int = 0, level: float = 0.95) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    means = rng.choice(values, size=(n_boot, len(values)), replace=True).mean(axis=1)
    tail = (1 - level) / 2
    return float(np.quantile(means, tail)), float(np.quantile(means, 1 - tail))


def spearman(x: np.ndarray, y: np.ndarray) -> dict:
    result = stats.spearmanr(x, y)
    return {"rho": float(result.statistic), "p": float(result.pvalue), "n": int(len(x))}


def selection_break_even(
    rated_a_mean: float, rated_a: int, unrated_a: int, assumed_unrated_a: float,
    rated_b_mean: float, rated_b: int, unrated_b: int,
) -> float:
    """Mean star rating the unrated members of group b would need for b to match a.

    Unrated hospitals have no stars, so a gap between rated groups could in
    principle be a selection artifact. This answers: given an assumption about
    group a's unrated hospitals, how good would b's unrated hospitals have to be
    to erase the gap? A value above 5 means no possible ratings could do it.
    """
    full_a = (rated_a_mean * rated_a + assumed_unrated_a * unrated_a) / (rated_a + unrated_a)
    return (full_a * (rated_b + unrated_b) - rated_b_mean * rated_b) / unrated_b
