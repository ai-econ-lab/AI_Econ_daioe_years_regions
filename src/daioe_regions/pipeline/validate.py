"""Gate for the merged daioe/SCB/geo dataset.

Runs in 04_development_to_main.yml before anything is committed or published,
and exits non-zero (listing every failed check) so a bad build never reaches
`development` or `dataset-latest`.

Usage:
    daioe-validate data/daioe_scb_years_all_levels_geo.parquet
    daioe-validate NEW.parquet --previous PUBLISHED.parquet
"""

import argparse
import sys
from pathlib import Path
from typing import cast

import polars as pl
import polars.selectors as cs

from daioe_regions.config import VALIDATION
from daioe_regions.schema import COLUMNS, SCHEMA


def column_range(df: pl.DataFrame, column: str) -> tuple[float, float] | None:
    """Minimum and maximum of a numeric column, or None when it is all null."""
    low, high = df[column].min(), df[column].max()
    if low is None or high is None:
        return None
    return cast(float, low), cast(float, high)


def check_schema(df: pl.DataFrame) -> list[str]:
    """Check the columns and dtypes match the typed schema exactly."""
    failures = []

    missing = [name for name in SCHEMA if name not in df.columns]
    if missing:
        failures.append(f"missing columns: {missing}")

    unexpected = [name for name in df.columns if name not in SCHEMA]
    if unexpected:
        failures.append(
            f"unexpected columns (add them to daioe_regions/schema.py): {unexpected}"
        )

    for name, dtype in SCHEMA.items():
        if name in df.columns and df.schema[name] != dtype:
            failures.append(f"{name}: dtype {df.schema[name]}, expected {dtype}")

    return failures


def check_structure(df: pl.DataFrame) -> list[str]:
    """Check keys, dimensions and year coverage (assumes the schema check passed)."""
    failures = []

    duplicates = df.height - df.select(list(VALIDATION.key)).unique().height
    if duplicates:
        failures.append(f"{duplicates} duplicate rows on key {list(VALIDATION.key)}")

    levels = set(df["level"].unique())
    expected = VALIDATION.expected_levels
    if levels != expected:
        failures.append(f"levels are {sorted(levels)}, expected {sorted(expected)}")

    counties = df["county_code"].n_unique()
    if counties != VALIDATION.expected_counties:
        failures.append(f"{counties} counties, expected {VALIDATION.expected_counties}")

    sexes = df["sex"].n_unique()
    if sexes != VALIDATION.expected_sexes:
        failures.append(f"{sexes} sex categories, expected {VALIDATION.expected_sexes}")

    years = sorted(df["year"].unique())
    if years != list(range(years[0], years[-1] + 1)):
        failures.append(f"years are not contiguous: {years}")

    return failures


def check_values(df: pl.DataFrame) -> list[str]:
    """Check NaN/inf, nulls in non-nullable columns and out-of-range values."""
    failures = []

    for column in df.select(cs.float()).columns:
        bad = df.select(
            (pl.col(column).is_nan() | pl.col(column).is_infinite()).sum(),
        ).item()
        if bad:
            failures.append(f"{column}: {bad} NaN/inf values")

    for column in COLUMNS:
        nulls = df[column.name].null_count()
        if nulls and not column.nullable:
            failures.append(f"{column.name}: {nulls} null values")

        bounds = column_range(df, column.name) if column.dtype.is_numeric() else None
        if bounds is None:
            continue
        low, high = column.minimum, column.maximum
        if (low is not None and bounds[0] < low) or (
            high is not None and bounds[1] > high
        ):
            allowed = f"{'-inf' if low is None else f'{low:g}'}-"
            allowed += "inf" if high is None else f"{high:g}"
            failures.append(
                f"{column.name}: outside {allowed} (min {bounds[0]}, max {bounds[1]})"
            )

    guard = VALIDATION.guard_metric
    if guard in df.columns:
        unscored = df.filter(
            (pl.col("level") == "SSYK1") & (pl.col("ssyk_code") != "0"),
        )[guard].null_count()
        if unscored:
            failures.append(
                f"{guard}: {unscored} SSYK1 rows (groups 1-9) have no score",
            )

    return failures


def check_against_previous(df: pl.DataFrame, previous: pl.DataFrame) -> list[str]:
    """Check the new dataset has not shrunk or lost columns or years."""
    failures = []

    lost = sorted(set(previous.columns) - set(df.columns))
    if lost:
        failures.append(f"columns missing versus previous release: {lost}")

    if df.height < previous.height:
        failures.append(f"{df.height} rows, fewer than previous {previous.height}")

    latest, previous_latest = df["year"].max(), previous["year"].max()
    if cast(int, latest) < cast(int, previous_latest):
        failures.append(
            f"latest year {latest} is older than previous {previous_latest}",
        )

    return failures


def check_dataset(df: pl.DataFrame) -> list[str]:
    """Run the schema, structure and value checks, stopping at the first failure."""
    for check in (check_schema, check_structure, check_values):
        if failures := check(df):
            return failures
    return []


def main() -> None:
    """Validate a dataset and exit non-zero if any check fails."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("path", type=Path, help="parquet file to validate")
    parser.add_argument("--previous", type=Path, help="previously published parquet")
    args = parser.parse_args()

    df = pl.read_parquet(args.path)
    failures = check_dataset(df)
    if args.previous is not None:
        failures += check_against_previous(df, pl.read_parquet(args.previous))

    if failures:
        print(f"FAILED: {len(failures)} check(s) on {args.path}")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)
    print(f"OK: {args.path} passed all checks ({df.height} rows)")


if __name__ == "__main__":
    main()
