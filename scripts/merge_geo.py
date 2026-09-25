"""
merge_geo.py.
-------------
Joins county coordinates onto the daioe/SCB dataset that lives on this
branch's data/ folder, producing the file the Shiny app reads.

Runs once per pipeline run, in 04_development_to_main.yml, which both
02_daioe_pull_to_development.yml and 03_geo_pull_to_development.yml trigger
after publishing their intermediate to the pipeline-data-latest release.

Idempotent: purely a function of the two current files in data/, so it's
safe to re-run regardless of which producer triggered it. Fails if
county_coordinates.parquet is missing, since a dataset without coordinates
is not the published product.
"""

from pathlib import Path

import polars as pl

ROOT = Path.cwd().resolve()
DATA_DIR = ROOT / "data"

DAIOE_PATH = DATA_DIR / "daioe_scb_years_all_levels.parquet"
COORDS_PATH = DATA_DIR / "county_coordinates.parquet"
OUTPUT_PATH = DATA_DIR / "daioe_scb_years_all_levels_geo.parquet"

# Canonical row order so identical data always serialises to identical
# bytes; without this, unstable ordering upstream reshuffled every write and
# made every run look like a data change to git.
SORT_KEY = ["year", "county_code", "level", "ssyk_code", "sex"]


def main() -> None:
    """Join county coordinates onto the daioe dataset and write the result."""
    if not COORDS_PATH.exists():
        msg = f"{COORDS_PATH} not found; run geo_pull first"
        raise FileNotFoundError(msg)

    daioe = pl.scan_parquet(DAIOE_PATH)
    coords = pl.scan_parquet(COORDS_PATH).select(
        ["county_code", "county_lat", "county_lon"],
    )
    merged = daioe.join(coords, on="county_code", how="left")
    merged.sort(SORT_KEY).sink_parquet(OUTPUT_PATH)
    print(f"Exported merged dataset to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
