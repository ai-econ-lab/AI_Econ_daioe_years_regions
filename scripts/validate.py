"""
validate.py.
------------
Gate for the merged daioe/SCB/geo dataset. Runs in 04_development_to_main.yml
before anything is committed or published, and exits non-zero (listing every
failed check) so a bad build never reaches `development` or `dataset-latest`.

Usage:
    python scripts/validate.py data/daioe_scb_years_all_levels_geo.parquet
    python scripts/validate.py NEW.parquet --previous PUBLISHED.parquet
"""

import argparse
import sys
from pathlib import Path

import polars as pl
import polars.selectors as cs

KEY = ["level", "ssyk_code", "county_code", "sex", "year"]
EXPECTED_LEVELS = {"SSYK1", "SSYK2", "SSYK3", "SSYK4"}
EXPECTED_COUNTIES = 21
EXPECTED_SEXES = 2
COORD_COLUMNS = ["county_lat", "county_lon"]

# SSYK1 group 0 (armed forces) has no DAIOE scores, so it is legitimately
# null. Every other major group must have a finite exposure score; a null
# here means NaN scores are propagating through the aggregation again.
GUARD_METRIC = "daioe_allapps_wavg"


def check_structure(df: pl.DataFrame) -> list[str]:
    """Check keys, dimensions and year coverage."""
    failures = []

    missing = [c for c in [*KEY, "emp_count", *COORD_COLUMNS] if c not in df.columns]
    if missing:
        return [f"missing required columns: {missing}"]

    duplicates = df.height - df.select(KEY).unique().height
    if duplicates:
        failures.append(f"{duplicates} duplicate rows on key {KEY}")

    levels = set(df["level"].unique())
    if levels != EXPECTED_LEVELS:
        failures.append(
            f"levels are {sorted(levels)}, expected {sorted(EXPECTED_LEVELS)}"
        )

    counties = df["county_code"].n_unique()
    if counties != EXPECTED_COUNTIES:
        failures.append(f"{counties} counties, expected {EXPECTED_COUNTIES}")

    sexes = df["sex"].n_unique()
    if sexes != EXPECTED_SEXES:
        failures.append(f"{sexes} sex categories, expected {EXPECTED_SEXES}")

    years = sorted(df["year"].unique())
    if years != list(range(years[0], years[-1] + 1)):
        failures.append(f"years are not contiguous: {years}")

    return failures


def check_values(df: pl.DataFrame) -> list[str]:
    """Check for NaN/inf, nulls in required columns, and out-of-range values."""
    failures = []

    for column in df.select(cs.float()).columns:
        bad = df.select(
            (pl.col(column).is_nan() | pl.col(column).is_infinite()).sum(),
        ).item()
        if bad:
            failures.append(f"{column}: {bad} NaN/inf values")

    for column in ["emp_count", *COORD_COLUMNS]:
        nulls = df[column].null_count()
        if nulls:
            failures.append(f"{column}: {nulls} null values")

    if (df["emp_count"] < 0).any():
        failures.append("emp_count has negative values")

    for column in df.select(cs.starts_with("pctl_")).columns:
        low, high = df[column].min(), df[column].max()
        if low is not None and not (0 <= low and high <= 100):
            failures.append(f"{column}: outside 0-100 (min {low}, max {high})")

    for column in df.select(cs.ends_with("_Level_Exposure")).columns:
        low, high = df[column].min(), df[column].max()
        if low is not None and not (1 <= low and high <= 5):
            failures.append(f"{column}: outside 1-5 (min {low}, max {high})")

    if GUARD_METRIC in df.columns:
        unscored = df.filter(
            (pl.col("level") == "SSYK1") & (pl.col("ssyk_code") != "0"),
        )[GUARD_METRIC].null_count()
        if unscored:
            failures.append(
                f"{GUARD_METRIC}: {unscored} SSYK1 rows (groups 1-9) have no score",
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

    if df["year"].max() < previous["year"].max():
        failures.append(
            f"latest year {df['year'].max()} is older than previous "
            f"{previous['year'].max()}",
        )

    return failures


def main() -> None:
    """Validate a dataset and exit non-zero if any check fails."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("path", type=Path, help="parquet file to validate")
    parser.add_argument("--previous", type=Path, help="previously published parquet")
    args = parser.parse_args()

    df = pl.read_parquet(args.path)
    failures = check_structure(df)
    if not failures:
        failures = check_values(df)
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
