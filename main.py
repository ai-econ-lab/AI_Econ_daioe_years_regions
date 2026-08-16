"""
county_coordinates.py.
-----------------------
Builds the county geodata artifact consumed by the `development` branch.

Reads the checked-in `county_coordinates.csv` reference table (county
administrative-capital coordinates for Sweden's 21 SCB län codes),
validates it, and writes `data/county_coordinates.parquet`.

Kept as a standalone step so a real coordinate source (e.g. a geocoding
API or official geometry file) can later replace the CSV read without
touching the rest of the pipeline.
"""

from pathlib import Path

import polars as pl

ROOT = Path.cwd().resolve()
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

SOURCE_PATH = ROOT / "county_coordinates.csv"
OUTPUT_PATH = DATA_DIR / "county_coordinates.parquet"

EXPECTED_COUNTY_COUNT = 21


def load_county_coordinates(path: Path) -> pl.DataFrame:
    """Load and validate the county_code -> lat/lon reference table."""
    df = pl.read_csv(
        path,
        schema_overrides={
            "county_code": pl.Utf8,
            "county": pl.Utf8,
            "county_lat": pl.Float64,
            "county_lon": pl.Float64,
        },
    ).select(["county_code", "county", "county_lat", "county_lon"])

    if df.height != EXPECTED_COUNTY_COUNT:
        msg = f"Expected {EXPECTED_COUNTY_COUNT} counties, found {df.height}"
        raise ValueError(msg)

    if df.select(pl.col("county_lat", "county_lon").is_null().any()).row(0) != (
        False,
        False,
    ):
        msg = "county_coordinates.csv contains null coordinates"
        raise ValueError(msg)

    return df


def main() -> None:
    coords = load_county_coordinates(SOURCE_PATH)
    coords.write_parquet(OUTPUT_PATH)
    print(f"Exported {coords.height} counties to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
