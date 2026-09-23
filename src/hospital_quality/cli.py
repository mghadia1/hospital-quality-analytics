"""Command line: `hospital-quality download | analyze`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from hospital_quality import analysis, charts, data, stats

MIN_GROUP = 30   # smallest ownership group admitted to a significance test
MIN_STATE = 15   # smallest state shown with a confidence interval


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="hospital-quality")
    sub = parser.add_subparsers(dest="command", required=True)
    dl = sub.add_parser("download", help="fetch and checksum the pinned CMS files")
    dl.add_argument("--destination", type=Path, default=Path("data/raw"))
    an = sub.add_parser("analyze", help="run the SQL and statistics; write CSVs, charts, summary")
    an.add_argument("--raw", type=Path, default=Path("data/raw"))
    an.add_argument("--out", type=Path, default=Path("outputs"))
    an.add_argument("--permutations", type=int, default=10_000)
    args = parser.parse_args(argv)

    if args.command == "download":
        for path in data.download(args.destination):
            print(path)
    else:
        print(json.dumps(analyze(args.raw, args.out, args.permutations), indent=2))


def analyze(raw: Path, out: Path, permutations: int = 10_000) -> dict:
    for source in data.SOURCES:
        data.verify(raw / source.filename, source.sha256)
    out.mkdir(parents=True, exist_ok=True)
    con = analysis.connect_dir(raw)
    results = {name: analysis.run(con, name) for name in analysis.QUERIES}
    rated = con.execute("SELECT * FROM rated_acute").df()

    # Ownership: omnibus test, then pairwise with Holm correction.
    kruskal = stats.kruskal_by_group(rated, "ownership_group", "stars", MIN_GROUP)
    pairwise = stats.pairwise_mann_whitney(rated, "ownership_group", "stars", MIN_GROUP)
    permutation = stats.stratified_permutation_test(
        rated, "ownership_group", "Non-profit", "For-profit", "state", "stars", permutations
    )
    results["ownership_pairwise"] = pairwise

    # Could the gap be produced by which hospitals go unrated?
    coverage = results["coverage_by_ownership"].set_index("ownership_group")
    ownership = results["ownership_ratings"].set_index("ownership_group")

    def break_even(assumed_unrated_nonprofit: float) -> float:
        np_, fp = "Non-profit", "For-profit"
        return stats.selection_break_even(
            ownership.loc[np_, "mean_stars"], coverage.loc[np_, "rated"],
            coverage.loc[np_, "hospitals"] - coverage.loc[np_, "rated"], assumed_unrated_nonprofit,
            ownership.loc[fp, "mean_stars"], coverage.loc[fp, "rated"],
            coverage.loc[fp, "hospitals"] - coverage.loc[fp, "rated"],
        )

    # States: bootstrap CI on the mean for states with enough hospitals.
    states = results["state_ratings"]
    states = states[states["hospitals"] >= MIN_STATE].copy()
    cis = [stats.bootstrap_mean_ci(rated.loc[rated["state"] == s, "stars"].to_numpy(), seed=i)
           for i, s in enumerate(states["state"])]
    states["ci_low"], states["ci_high"] = zip(*cis)
    national = float(rated["stars"].mean())
    states["ci_excludes_national"] = (states["ci_low"] > national) | (states["ci_high"] < national)
    results["state_ratings_ci"] = states

    readmit = results["readmission_by_stars"]
    rho = stats.spearman(readmit["stars"].to_numpy(), readmit["mean_ratio"].to_numpy())

    for name, frame in results.items():
        frame.to_csv(out / f"{name}.csv", index=False)
    charts.ownership_distribution(results["ownership_ratings"], out / "ownership_stars.png")
    charts.state_means(states, national, out / "state_means.png")
    charts.readmission_by_stars(readmit, out / "readmission_by_stars.png")

    az = states.set_index("state").loc["AZ"]
    summary = {
        "hospitals": int(con.execute("SELECT count(*) FROM hospitals").fetchone()[0]),
        "rated_hospitals_all_types": int(con.execute("SELECT count(stars) FROM hospitals").fetchone()[0]),
        "rated_acute_care": int(len(rated)),
        "national_mean_stars_acute": round(national, 3),
        "kruskal_ownership": kruskal,
        "nonprofit_vs_forprofit_permutation": permutation,
        "forprofit_unrated_mean_needed_to_close_gap": {
            "if_unrated_nonprofits_match_rated": round(break_even(ownership.loc["Non-profit", "mean_stars"]), 3),
            "if_unrated_nonprofits_all_1_star": round(break_even(1.0), 3),
        },
        "states_tested": int(len(states)),
        "states_ci_excludes_national": int(states["ci_excludes_national"].sum()),
        "arizona": {"hospitals": int(az["hospitals"]), "mean_stars": float(az["mean_stars"]),
                    "ci": [round(az["ci_low"], 3), round(az["ci_high"], 3)]},
        "stars_vs_mean_excess_readmission_ratio": rho,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary


if __name__ == "__main__":
    main()
