"""Join county coordinates onto the daioe/SCB dataset in the data folder.

Produces the file the Shiny app reads. Runs once per pipeline run, in
04_development_to_main.yml, which both 02_daioe_pull_to_development.yml and
03_geo_pull_to_development.yml trigger after publishing their intermediate to
the pipeline-data-latest release.

Idempotent: purely a function of the two current files in the data folder, so
it is safe to re-run regardless of which producer triggered it. Fails if
county_coordinates.parquet is missing, since a dataset without coordinates is
not the published product.
"""

import argparse
from pathlib import Path

import polars as pl

from daioe_regions.config import MERGE, PATHS


def merge(daioe: pl.LazyFrame, coordinates: pl.LazyFrame) -> pl.LazyFrame:
    """Left join county coordinates onto the dataset in canonical row order."""
    coords = coordinates.select(list(MERGE.coord_columns))
    return daioe.join(coords, on="county_code", how="left").sort(list(MERGE.sort_key))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PATHS.data_dir,
        help="Folder holding the intermediates; the merged file is written here.",
    )
    return parser.parse_args()


def main() -> None:
    """Join county coordinates onto the daioe dataset and write the result."""
    data_dir = parse_args().data_dir
    daioe_path = data_dir / PATHS.daioe_intermediate.name
    coords_path = data_dir / PATHS.coordinates.name
    output_path = data_dir / PATHS.dataset.name

    if not coords_path.exists():
        msg = f"{coords_path} not found; run geo_pull first"
        raise FileNotFoundError(msg)

    merged = merge(pl.scan_parquet(daioe_path), pl.scan_parquet(coords_path))
    merged.sink_parquet(output_path)
    print(f"Exported merged dataset to {output_path}")


if __name__ == "__main__":
    main()
