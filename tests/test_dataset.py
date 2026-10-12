"""Checks on the tracked dataset the app actually reads."""

import polars as pl
import pytest

from daioe_regions.config import PATHS, TAXONOMY
from daioe_regions.pipeline import validate
from daioe_regions.schema import SCHEMA

pytestmark = pytest.mark.skipif(
    not PATHS.dataset.exists(), reason="tracked dataset not present"
)


@pytest.fixture(scope="module")
def dataset() -> pl.DataFrame:
    return pl.read_parquet(PATHS.dataset)


def test_tracked_dataset_passes_the_gate(dataset: pl.DataFrame) -> None:
    assert validate.check_dataset(dataset) == []


def test_tracked_dataset_matches_the_schema_exactly(dataset: pl.DataFrame) -> None:
    assert dict(dataset.schema) == SCHEMA


@pytest.mark.parametrize("subindex", list(TAXONOMY.subindices))
def test_every_subindex_has_its_columns(dataset: pl.DataFrame, subindex: str) -> None:
    assert f"daioe_{subindex}_wavg" in dataset.columns
    assert f"daioe_{subindex}_Level_Exposure" in dataset.columns


def test_boundaries_cover_every_county_in_the_dataset(dataset: pl.DataFrame) -> None:
    import json

    boundary_codes = {
        feature["properties"]["county_code"]
        for feature in json.loads(PATHS.boundaries.read_text())["features"]
    }
    assert boundary_codes == set(dataset["county_code"].unique())
