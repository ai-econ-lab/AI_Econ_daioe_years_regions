"""The dataset gate in daioe_regions.pipeline.validate."""

import polars as pl
import pytest

from daioe_regions.pipeline import validate


def failures(df: pl.DataFrame) -> list[str]:
    """Failures as the command line gate reports them."""
    return validate.check_dataset(df)


def test_valid_dataset_passes(valid_dataset: pl.DataFrame) -> None:
    assert failures(valid_dataset) == []


def test_missing_columns_are_reported(valid_dataset: pl.DataFrame) -> None:
    result = validate.check_schema(valid_dataset.drop("county_lat"))
    assert len(result) == 1
    assert "missing columns" in result[0]
    assert "county_lat" in result[0]


def test_unexpected_columns_are_reported(valid_dataset: pl.DataFrame) -> None:
    result = validate.check_schema(valid_dataset.with_columns(pl.lit(1).alias("extra")))
    assert len(result) == 1
    assert "unexpected columns" in result[0]
    assert "extra" in result[0]


def test_wrong_dtype_is_reported(valid_dataset: pl.DataFrame) -> None:
    result = validate.check_schema(
        valid_dataset.with_columns(pl.col("year").cast(pl.Int32))
    )
    assert result == ["year: dtype Int32, expected Int64"]


def test_stages_stop_at_the_first_failing_one(valid_dataset: pl.DataFrame) -> None:
    broken = valid_dataset.drop("county_lat").with_columns(
        pl.lit(150.0).alias("pctl_daioe_allapps_wavg")
    )
    assert all("county_lat" in message for message in failures(broken))


def test_null_in_a_required_column_fails(valid_dataset: pl.DataFrame) -> None:
    broken = valid_dataset.with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(None)
        .otherwise(pl.col("emp_count"))
        .alias("emp_count")
    )
    assert "emp_count: 1 null values" in validate.check_values(broken)


def test_null_in_a_nullable_column_passes(valid_dataset: pl.DataFrame) -> None:
    nulled = valid_dataset.with_columns(pl.lit(None, dtype=pl.Int64).alias("chg_1y"))
    assert validate.check_values(nulled) == []


def test_negative_employment_fails(valid_dataset: pl.DataFrame) -> None:
    broken = valid_dataset.with_columns(pl.lit(-1).cast(pl.Int64).alias("emp_count"))
    assert any(
        m.startswith("emp_count: outside 0-inf") for m in validate.check_values(broken)
    )


def test_percentage_change_below_minus_100_fails(valid_dataset: pl.DataFrame) -> None:
    broken = valid_dataset.with_columns(pl.lit(-150.0).alias("pct_chg_1y"))
    assert any(
        m.startswith("pct_chg_1y: outside -100-inf")
        for m in validate.check_values(broken)
    )


def test_duplicate_keys_fail(valid_dataset: pl.DataFrame) -> None:
    result = validate.check_structure(pl.concat([valid_dataset, valid_dataset.head(1)]))
    assert any("duplicate rows" in message for message in result)


def test_wrong_county_count_fails(valid_dataset: pl.DataFrame) -> None:
    result = validate.check_structure(
        valid_dataset.filter(pl.col("county_code") != "21")
    )
    assert any("20 counties, expected 21" in message for message in result)


def test_missing_level_fails(valid_dataset: pl.DataFrame) -> None:
    result = validate.check_structure(valid_dataset.filter(pl.col("level") != "SSYK3"))
    assert any("levels are" in message for message in result)


def test_gap_in_years_fails(valid_dataset: pl.DataFrame) -> None:
    gap = valid_dataset.with_columns(
        pl.when(pl.col("year") == 2024)
        .then(2026)
        .otherwise(pl.col("year"))
        .alias("year")
    )
    assert any("not contiguous" in message for message in validate.check_structure(gap))


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nan_and_inf_fail(valid_dataset: pl.DataFrame, bad: float) -> None:
    broken = valid_dataset.with_columns(
        pl.when(pl.col("ssyk_code") == "1111")
        .then(bad)
        .otherwise(pl.col("daioe_allapps_wavg"))
        .alias("daioe_allapps_wavg")
    )
    assert any("NaN/inf" in message for message in validate.check_values(broken))


def test_percentile_outside_range_fails(valid_dataset: pl.DataFrame) -> None:
    broken = valid_dataset.with_columns(pl.lit(150.0).alias("pctl_daioe_allapps_wavg"))
    assert any("outside 0-100" in message for message in validate.check_values(broken))


def test_exposure_level_outside_range_fails(valid_dataset: pl.DataFrame) -> None:
    broken = valid_dataset.with_columns(pl.lit(6).alias("daioe_allapps_Level_Exposure"))
    assert any("outside 1-5" in message for message in validate.check_values(broken))


def test_null_coordinates_fail(valid_dataset: pl.DataFrame) -> None:
    broken = valid_dataset.with_columns(
        pl.lit(None, dtype=pl.Float64).alias("county_lon")
    )
    assert any("county_lon: " in message for message in validate.check_values(broken))


def test_unscored_ordinary_group_fails_but_armed_forces_pass(
    valid_dataset: pl.DataFrame,
) -> None:
    # Group 0 is already null in the fixture and passes; nulling group 1 must fail.
    broken = valid_dataset.with_columns(
        pl.when((pl.col("level") == "SSYK1") & (pl.col("ssyk_code") == "1"))
        .then(None)
        .otherwise(pl.col("daioe_allapps_wavg"))
        .alias("daioe_allapps_wavg")
    )
    assert any("have no score" in message for message in validate.check_values(broken))


def test_shrunk_dataset_fails_against_previous(valid_dataset: pl.DataFrame) -> None:
    result = validate.check_against_previous(valid_dataset.head(100), valid_dataset)
    assert any("fewer than previous" in message for message in result)
    assert validate.check_against_previous(valid_dataset, valid_dataset) == []


def test_lost_columns_and_older_year_fail_against_previous(
    valid_dataset: pl.DataFrame,
) -> None:
    older = valid_dataset.filter(pl.col("year") == 2023).drop("emp_count")
    result = validate.check_against_previous(older, valid_dataset)
    assert any("columns missing" in message for message in result)
    assert any("older than previous" in message for message in result)
