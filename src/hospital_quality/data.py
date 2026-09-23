"""Download and verify the three CMS Provider Data files this analysis uses.

CMS republishes Care Compare data quarterly under new URLs. The URLs and hashes
below pin the exact snapshot the results in docs/results.md were computed from.
To move to a newer release, update both the URL and the hash, then re-run and
re-record the results. Never do one without the other.
"""

from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE = "https://data.cms.gov/provider-data/sites/default/files/resources"


@dataclass(frozen=True)
class Source:
    filename: str
    url: str
    sha256: str
    title: str
    modified: str


SOURCES = (
    Source(
        "hospital_general_information.csv",
        f"{BASE}/893c372430d9d71a1c52737d01239d47_1785189955/Hospital_General_Information.csv",
        "f874f09fef895a1ccf5bb7392dcbb2be05c9860339261b093fe00f0c1b013480",
        "Hospital General Information (dataset xubh-q36u)",
        "2026-07-22",
    ),
    Source(
        "hrrp_fy2026.csv",
        f"{BASE}/a171bc36c488d3e0dc33ec63abb469a6_1770163617/FY_2026_Hospital_Readmissions_Reduction_Program_Hospital.csv",
        "7e7915dd2751a1e59ac46dbc9194fb781e820962a04d47c31344ea2bb30c91f6",
        "Hospital Readmissions Reduction Program FY2026 (dataset 9n3s-kdb3)",
        "2026-01-26",
    ),
    Source(
        "footnote_crosswalk.csv",
        f"{BASE}/f29bb7c812e242f6edfef0a4b7d0eaca_1760630713/Footnote_Crosswalk.csv",
        "5214e1468fb04c5cdeac8920f2c446cccaa65e2f6f929424cd228042a52d963e",
        "Footnote Crosswalk (dataset y9us-9xdf)",
        "2025-09-18",
    ),
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    actual = sha256_of(path)
    if actual != expected:
        raise ValueError(f"checksum mismatch for {path.name}: {actual}")


def download(destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    paths = []
    for source in SOURCES:
        path = destination / source.filename
        if not path.exists():
            urllib.request.urlretrieve(source.url, path)
        verify(path, source.sha256)
        paths.append(path)
    return paths
