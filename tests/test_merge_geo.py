"""The geodata merge in daioe_regions.pipeline.merge_geo."""

import sys
from pathlib import Path

import polars as pl
import pytest

from daioe_regions.config import MERGE, PATHS
from daioe_regions.pipeline import merge_geo


def daioe_frame() -> pl.DataFrame:
    """Rows deliberately out of canonical order, one county without coordinates."""
    return pl.DataFrame(
        {
            "year": [2024, 2023, 2024, 2023],
            "county_code": ["03", "01", "01", "99"],
            "level": ["SSYK1"] * 4,
            "ssyk_code": ["1"] * 4,
            "sex": ["men"] * 4,
            "emp_count": [1, 2, 3, 4],
        }
    )


def coordinates_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "county_code": ["01", "03"],
            "county_lat": [59.3, 59.9],
            "county_lon": [18.0, 17.6],
            "county_name": ["Stockholm", "Uppsala"],
        }
    )


def test_merge_adds_coordinates_and_keeps_every_row() -> None:
    merged = merge_geo.merge(daioe_frame().lazy(), coordinates_frame().lazy()).collect()
    assert merged.height == 4
    assert {"county_lat", "county_lon"} <= set(merged.columns)
    assert "county_name" not in merged.columns
    unmatched = merged.filter(pl.col("county_code") == "99")
    assert unmatched["county_lat"].to_list() == [None]


def test_merge_orders_rows_canonically() -> None:
    merged = merge_geo.merge(daioe_frame().lazy(), coordinates_frame().lazy()).collect()
    keys = merged.select(list(MERGE.sort_key)).rows()
    assert keys == sorted(keys)


def test_main_writes_the_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daioe_frame().write_parquet(tmp_path / PATHS.daioe_intermediate.name)
    coordinates_frame().write_parquet(tmp_path / PATHS.coordinates.name)
    monkeypatch.setattr(sys, "argv", ["daioe-merge-geo", "--data-dir", str(tmp_path)])
    merge_geo.main()
    assert pl.read_parquet(tmp_path / PATHS.dataset.name).height == 4


def test_main_fails_without_coordinates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daioe_frame().write_parquet(tmp_path / PATHS.daioe_intermediate.name)
    monkeypatch.setattr(sys, "argv", ["daioe-merge-geo", "--data-dir", str(tmp_path)])
    with pytest.raises(FileNotFoundError, match="geo_pull"):
        merge_geo.main()
