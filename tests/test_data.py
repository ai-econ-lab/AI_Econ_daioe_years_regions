"""Aggregation maths and filters in daioe_regions.data."""

import polars as pl
import pytest

from daioe_regions import data
from tests.conftest import SUBINDEX

BY_COUNTY = ["county_code", "county"]


def county_row(frame: pl.DataFrame, county_code: str, year: int) -> dict:
    """The single aggregated row for a county and year."""
    rows = frame.filter(
        (pl.col("county_code") == county_code) & (pl.col("year") == year)
    )
    assert rows.height == 1
    return rows.row(0, named=True)


def aggregate(
    frame: pl.DataFrame, sex: str = "men", group: str = "all"
) -> pl.DataFrame:
    """Aggregate SSYK4 rows per county and year for the test sub-index."""
    return data.aggregate(frame, "SSYK4", BY_COUNTY, sex, group, SUBINDEX)


def test_exposure_is_employment_weighted(small_frame: pl.DataFrame) -> None:
    row = county_row(aggregate(small_frame), "01", 2024)
    assert row["exposure"] == pytest.approx((100 * 10 + 300 * 20) / 400)


def test_unscored_occupation_counts_toward_employment_only(
    small_frame: pl.DataFrame,
) -> None:
    row = county_row(aggregate(small_frame), "01", 2024)
    assert row["employment"] == 100 + 300 + 600


def test_high_exposure_share_uses_scored_employment(small_frame: pl.DataFrame) -> None:
    row = county_row(aggregate(small_frame), "01", 2024)
    assert row["high_exposure_share"] == pytest.approx(100 / 400)


def test_percentage_change_comes_from_summed_counts(small_frame: pl.DataFrame) -> None:
    row = county_row(aggregate(small_frame), "01", 2024)
    # Counts moved +20 and -30 from 80 and 330: -10 on a base of 410, not the
    # average of +25% and -9.1%.
    assert row["pct_chg_1y"] == pytest.approx(-10 / 410)


def test_county_with_no_scored_occupations_has_null_exposure(
    small_frame: pl.DataFrame,
) -> None:
    row = county_row(aggregate(small_frame), "03", 2024)
    assert row["exposure"] is None
    assert row["employment"] == 70


def test_sex_filter(small_frame: pl.DataFrame) -> None:
    women = county_row(aggregate(small_frame, sex="women"), "01", 2024)
    both = county_row(aggregate(small_frame, sex="all"), "01", 2024)
    assert women["employment"] == 50
    assert women["exposure"] == pytest.approx(40.0)
    assert both["employment"] == 100 + 300 + 600 + 50


def test_group_filter_matches_code_prefix(small_frame: pl.DataFrame) -> None:
    row = county_row(aggregate(small_frame, group="2"), "01", 2024)
    assert row["employment"] == 300
    assert row["exposure"] == pytest.approx(20.0)


def test_only_the_requested_level_is_aggregated(small_frame: pl.DataFrame) -> None:
    ssyk1 = data.aggregate(small_frame, "SSYK1", BY_COUNTY, "men", "all", SUBINDEX)
    assert ssyk1["employment"].to_list() == [500]


def test_result_is_sorted_by_group_then_year(small_frame: pl.DataFrame) -> None:
    result = aggregate(small_frame)
    assert result.select("county_code", "year").rows() == sorted(
        result.select("county_code", "year").rows()
    )


def test_occupation_choices_lead_with_all(small_frame: pl.DataFrame) -> None:
    choices = data.occupation_choices(small_frame, "SSYK4")
    assert list(choices)[0] == "all"
    assert choices["1111"] == "1111 Legislators"
    assert "1" not in choices


def test_year_bounds(small_frame: pl.DataFrame) -> None:
    assert data.year_bounds(small_frame) == (2023, 2024)
