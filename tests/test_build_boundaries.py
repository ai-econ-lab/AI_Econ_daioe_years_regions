"""The county code mapping in daioe_regions.pipeline.build_boundaries."""

import json

import polars as pl
import pytest

from daioe_regions.config import PATHS
from daioe_regions.pipeline.build_boundaries import ISO_TO_SCB, check_county_codes

SCB_CODES = sorted(ISO_TO_SCB.values())


def test_mapping_covers_21_distinct_counties() -> None:
    assert len(ISO_TO_SCB) == 21
    assert len(set(ISO_TO_SCB.values())) == 21


def test_complete_mapping_passes() -> None:
    check_county_codes(SCB_CODES, SCB_CODES)


def test_unmapped_county_fails() -> None:
    with pytest.raises(ValueError, match="Expected 21 mapped"):
        check_county_codes([*SCB_CODES[:-1], None], SCB_CODES)


def test_wrong_count_fails() -> None:
    with pytest.raises(ValueError, match="Expected 21 mapped"):
        check_county_codes(SCB_CODES[:-1], SCB_CODES)


def test_codes_must_match_the_dataset() -> None:
    other = [*SCB_CODES[:-1], "99"]
    with pytest.raises(ValueError, match="do not match"):
        check_county_codes(SCB_CODES, other)


@pytest.mark.skipif(not PATHS.dataset.exists(), reason="tracked dataset not present")
def test_mapping_and_tracked_boundaries_match_the_dataset() -> None:
    dataset_codes = (
        pl.read_parquet(PATHS.dataset, columns=["county_code"])
        .get_column("county_code")
        .unique()
        .to_list()
    )
    boundary_codes = [
        feature["properties"]["county_code"]
        for feature in json.loads(PATHS.boundaries.read_text())["features"]
    ]
    check_county_codes(boundary_codes, dataset_codes)
    assert sorted(dataset_codes) == SCB_CODES
