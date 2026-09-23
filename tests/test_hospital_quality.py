"""Offline tests: SQL views on hand-built CMS-shaped rows, and each statistic
against a value that can be checked independently."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from hospital_quality import analysis, data, stats


def hospital(fid, state, htype, owner, rating, footnote=""):
    return {
        "Facility ID": fid, "Facility Name": f"H{fid}", "City/Town": "X", "State": state,
        "Hospital Type": htype, "Hospital Ownership": owner, "Emergency Services": "Yes",
        "Hospital overall rating": rating, "Hospital overall rating footnote": footnote,
    }


def hrrp(fid, condition, ratio, discharges="100"):
    return {
        "Facility ID": fid, "Measure Name": f"READM-30-{condition}-HRRP",
        "Number of Discharges": discharges, "Excess Readmission Ratio": ratio,
        "Predicted Readmission Rate": "10.0", "Expected Readmission Rate": "10.0", "Footnote": "",
    }


ACUTE = "Acute Care Hospitals"


@pytest.fixture
def con():
    hospitals = pd.DataFrame([
        hospital("1", "AZ", ACUTE, "Voluntary non-profit - Private", "5"),
        hospital("2", "AZ", ACUTE, "Voluntary non-profit - Church", "4"),
        hospital("3", "AZ", ACUTE, "Proprietary", "2"),
        hospital("4", "CA", ACUTE, "Government - Local", "3"),
        hospital("5", "CA", ACUTE, "Proprietary", "Not Available", "16"),
        hospital("6", "CA", "Psychiatric", "Proprietary", "Not Available", "19"),
        hospital("7", "CA", ACUTE, "Physician", "4"),
        hospital("8", "CA", ACUTE, "Tribal", "1", "16, 23"),
    ])
    readmissions = pd.DataFrame([
        hrrp("1", "HF", "0.90"), hrrp("1", "PN", "0.95"), hrrp("1", "AMI", "1.00"),
        hrrp("3", "HF", "1.10"), hrrp("3", "PN", "1.20"), hrrp("3", "AMI", "N/A", "N/A"),
        hrrp("4", "HF", "1.05"), hrrp("4", "PN", "Too Few to Report"),
    ])
    footnotes = pd.DataFrame({
        "Footnote": ["16", "19"],
        "Footnote Text": ["too few measures", "IQR/OQR participants only"],
    })
    return analysis.connect(hospitals, readmissions, footnotes)


def test_ownership_grouping_and_suppressed_values(con):
    h = con.execute("SELECT facility_id, ownership_group, stars, rating_footnote FROM hospitals ORDER BY 1").df()
    assert h["ownership_group"].tolist() == [
        "Non-profit", "Non-profit", "For-profit", "Government",
        "For-profit", "For-profit", "Physician-owned", "Government",
    ]
    assert h["stars"].isna().tolist() == [False, False, False, False, True, True, False, False]
    assert h.loc[h["facility_id"] == "8", "rating_footnote"].item() == "16"   # first of "16, 23"


def test_rated_acute_excludes_unrated_and_other_types(con):
    ids = con.execute("SELECT facility_id FROM rated_acute ORDER BY 1").df()["facility_id"].tolist()
    assert ids == ["1", "2", "3", "4", "7", "8"]


def test_rating_coverage_reports_reason_text(con):
    cov = analysis.run(con, "rating_coverage").set_index("hospital_type")
    assert cov.loc[ACUTE, "hospitals"] == 7
    assert cov.loc[ACUTE, "rated"] == 6
    assert cov.loc["Psychiatric", "rated_pct"] == 0.0
    assert cov.loc["Psychiatric", "main_missing_reason"] == "IQR/OQR participants only"


def test_ownership_ratings(con):
    own = analysis.run(con, "ownership_ratings").set_index("ownership_group")
    assert own.loc["Non-profit", "mean_stars"] == pytest.approx(4.5)
    assert own.loc["Non-profit", "pct_4_or_5"] == pytest.approx(100.0)
    assert own.loc["Government", "stars_1"] == 1 and own.loc["Government", "stars_3"] == 1


def test_readmissions_parse_and_require_three_conditions(con):
    conditions = analysis.run(con, "hrrp_conditions").set_index("condition")
    assert conditions.loc["PN", "with_ratio"] == 2                  # "Too Few to Report" -> NULL
    assert conditions.loc["HF", "pct_above_1"] == pytest.approx(66.7)
    by_stars = analysis.run(con, "readmission_by_stars")
    # hospital 1 has 3 ratios; 3 and 4 have only 2 each, so they are dropped
    assert by_stars["facility_id"].tolist() == ["1"]
    assert by_stars["mean_ratio"].item() == pytest.approx(0.95)


def test_rank_biserial_extremes():
    assert stats.rank_biserial(np.array([4, 5, 5]), np.array([1, 2, 2])) == pytest.approx(1.0)
    assert stats.rank_biserial(np.array([1, 2]), np.array([4, 5])) == pytest.approx(-1.0)
    assert stats.rank_biserial(np.array([3, 3]), np.array([3, 3])) == pytest.approx(0.0)


def test_holm_matches_hand_calculation():
    # sorted p: 0.01*3=0.03, 0.02*2=0.04, 0.04*1=0.04 (monotone), returned in input order
    assert stats.holm([0.04, 0.01, 0.02]) == pytest.approx([0.04, 0.03, 0.04])
    assert stats.holm([0.5, 0.9]) == pytest.approx([1.0, 1.0])


def _stratified(n_per_cell: int, a_shift: float, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    # state S1 is high-rated and mostly group a; S2 is low-rated and mostly b.
    for state, base, n_a, n_b in (("S1", 4.0, 3 * n_per_cell, n_per_cell), ("S2", 2.0, n_per_cell, 3 * n_per_cell)):
        rows += [{"state": state, "g": "a", "v": base + a_shift + rng.normal(0, 0.3)} for _ in range(n_a)]
        rows += [{"state": state, "g": "b", "v": base + rng.normal(0, 0.3)} for _ in range(n_b)]
    return pd.DataFrame(rows)


def test_stratified_permutation_removes_state_confounding():
    # no ownership effect at all: the raw gap is produced entirely by state mix
    frame = _stratified(40, a_shift=0.0)
    result = stats.stratified_permutation_test(frame, "g", "a", "b", "state", "v", 2000)
    assert result["naive_difference"] > 0.8
    assert abs(result["within_strata_difference"]) < 0.15
    assert result["p_value"] > 0.05


def test_stratified_permutation_detects_real_effect():
    frame = _stratified(40, a_shift=0.5)
    result = stats.stratified_permutation_test(frame, "g", "a", "b", "state", "v", 2000)
    assert result["within_strata_difference"] == pytest.approx(0.5, abs=0.15)
    assert result["p_value"] == pytest.approx(1 / 2001)
    assert result["strata_contributing"] == 2


def test_permutation_matches_slow_reference():
    """The vectorised null distribution must agree with a plain loop."""
    frame = _stratified(6, a_shift=0.1, seed=3)
    fast = stats.stratified_permutation_test(frame, "g", "a", "b", "state", "v", 3000, seed=7)
    values, is_a, strata = frame["v"].to_numpy(), (frame["g"] == "a").to_numpy(), frame["state"].to_numpy()
    observed = stats._within_strata_difference(values, is_a, strata)
    assert fast["within_strata_difference"] == pytest.approx(observed)
    rng = np.random.default_rng(99)
    shuffled, extreme = is_a.copy(), 0
    for _ in range(3000):
        for s in np.unique(strata):
            idx = np.flatnonzero(strata == s)
            shuffled[idx] = rng.permutation(is_a[idx])
        extreme += abs(stats._within_strata_difference(values, shuffled, strata)) >= abs(observed)
    slow_p = (extreme + 1) / 3001
    assert fast["p_value"] == pytest.approx(slow_p, abs=0.03)   # different RNG streams, same distribution


def test_bootstrap_ci_brackets_mean_and_is_reproducible():
    values = np.array([1, 2, 3, 4, 5] * 10)
    low, high = stats.bootstrap_mean_ci(values, seed=4)
    assert low < 3 < high
    assert (low, high) == stats.bootstrap_mean_ci(values, seed=4)


def test_selection_break_even():
    # a: 10 rated at mean 4, 0 unrated -> 4.0 overall
    # b: 5 rated at mean 3, 5 unrated -> unrated must average 5 to reach 4.0
    assert stats.selection_break_even(4.0, 10, 0, 1.0, 3.0, 5, 5) == pytest.approx(5.0)
    # if a's 10 unrated are all 1 star, a falls to 2.5 and b's unrated need only 2.0
    assert stats.selection_break_even(4.0, 10, 10, 1.0, 3.0, 5, 5) == pytest.approx(2.0)


def test_unknown_query_rejected(con):
    with pytest.raises(KeyError):
        analysis.run(con, "hospitals; DROP VIEW hospitals")


def test_checksum_mismatch(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        data.verify(path, data.SOURCES[0].sha256)
