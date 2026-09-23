"""Bind the CMS files into DuckDB and run the SQL analyses."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import duckdb
import pandas as pd

QUERIES = (
    "rating_coverage",
    "coverage_by_ownership",
    "ownership_ratings",
    "state_ratings",
    "hrrp_conditions",
    "readmission_by_stars",
)


def _sql(name: str) -> str:
    return resources.files("hospital_quality").joinpath("sql", f"{name}.sql").read_text()


def connect(hospitals: Path | pd.DataFrame, hrrp: Path | pd.DataFrame, footnotes: Path | pd.DataFrame):
    con = duckdb.connect()
    for name, source in (("raw_hospitals", hospitals), ("raw_hrrp", hrrp), ("raw_footnotes", footnotes)):
        if isinstance(source, pd.DataFrame):
            con.register(name, source.astype(str).where(source.notna(), None))
        else:
            con.read_csv(str(source), all_varchar=True).create_view(name)
    con.execute(_sql("00_views"))
    return con


def connect_dir(raw_dir: Path):
    return connect(
        raw_dir / "hospital_general_information.csv",
        raw_dir / "hrrp_fy2026.csv",
        raw_dir / "footnote_crosswalk.csv",
    )


def run(con, name: str) -> pd.DataFrame:
    if name not in QUERIES:
        raise KeyError(f"unknown query {name!r}; choose from {QUERIES}")
    return con.execute(_sql(name)).df()
