"""One-off build of data/sweden_counties.geojson for the Altair map.

Simplified boundaries for Sweden's 21 counties (lan), keyed by SCB county_code.

Boundaries don't change, so this is not part of the pipeline. geopandas lives in
its own dependency group so it stays out of the app's dependencies:

    uv run --group boundaries python -m daioe_regions.pipeline.build_boundaries

Source: Natural Earth 10m admin-1 (public domain).
"""

import argparse
from collections.abc import Collection
from pathlib import Path

import polars as pl

from daioe_regions.config import PATHS

NATURAL_EARTH_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_10m_admin_1_states_provinces.geojson"
)

# ISO 3166-2:SE letter codes to SCB numeric county codes.
ISO_TO_SCB = {
    "SE-AB": "01",
    "SE-C": "03",
    "SE-D": "04",
    "SE-E": "05",
    "SE-F": "06",
    "SE-G": "07",
    "SE-H": "08",
    "SE-I": "09",
    "SE-K": "10",
    "SE-M": "12",
    "SE-N": "13",
    "SE-O": "14",
    "SE-S": "17",
    "SE-T": "18",
    "SE-U": "19",
    "SE-W": "20",
    "SE-X": "21",
    "SE-Y": "22",
    "SE-Z": "23",
    "SE-AC": "24",
    "SE-BD": "25",
}


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--source", default=NATURAL_EARTH_URL)
    parser.add_argument("--output", type=Path, default=PATHS.boundaries)
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Simplification tolerance in degrees.",
    )
    return parser.parse_args()


def check_county_codes(
    codes: Collection[str | None], dataset_codes: Collection[str]
) -> None:
    """Raise unless the boundaries are exactly the mapped counties of the dataset."""
    if None in codes or len(codes) != len(ISO_TO_SCB):
        msg = f"Expected {len(ISO_TO_SCB)} mapped Swedish counties, got {len(codes)}"
        raise ValueError(msg)
    if set(codes) != set(dataset_codes):
        msg = "Boundary county codes do not match the dataset's county codes"
        raise ValueError(msg)


def main() -> None:
    """Build the simplified county boundary GeoJSON and check it against the data."""
    import geopandas as gpd  # ty: ignore[unresolved-import]  # optional group

    args = parse_args()

    admin1 = gpd.read_file(args.source)
    sweden = admin1[admin1["iso_a2"] == "SE"].copy()
    sweden["county_code"] = sweden["iso_3166_2"].map(ISO_TO_SCB)

    dataset_codes = (
        pl.read_parquet(PATHS.dataset, columns=["county_code"])
        .get_column("county_code")
        .unique()
        .to_list()
    )
    check_county_codes(sweden["county_code"].tolist(), dataset_codes)

    sweden = sweden[["county_code", "geometry"]].sort_values("county_code")
    sweden["geometry"] = sweden.geometry.simplify(
        args.tolerance,
        preserve_topology=True,
    )
    sweden.to_file(args.output, driver="GeoJSON", COORDINATE_PRECISION=3)
    print(f"Wrote {args.output} ({args.output.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
