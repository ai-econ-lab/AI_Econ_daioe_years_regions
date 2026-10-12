"""The typed schema in daioe_regions.schema."""

import json
import sys
from pathlib import Path

import polars as pl
import pytest

from daioe_regions.config import PATHS, TAXONOMY
from daioe_regions.pipeline import export_schema
from daioe_regions.schema import COLUMNS, SCHEMA, domain_columns


def test_column_names_are_unique() -> None:
    assert len({column.name for column in COLUMNS}) == len(COLUMNS)


def test_every_subindex_contributes_five_columns() -> None:
    assert len(COLUMNS) == 7 + 8 + 5 * len(TAXONOMY.subindices) + 2
    for domain in TAXONOMY.subindices:
        assert len(domain_columns(domain)) == 5


def test_bounds_are_ordered() -> None:
    for column in COLUMNS:
        if column.minimum is not None and column.maximum is not None:
            assert column.minimum < column.maximum


def test_schema_maps_names_to_dtypes() -> None:
    assert SCHEMA["year"] == pl.Int64
    assert SCHEMA["daioe_genai_Level_Exposure"] == pl.Int8
    assert SCHEMA["pctl_daioe_genai_wavg"] == pl.Float64


def test_only_scores_and_changes_are_nullable() -> None:
    required = {c.name for c in COLUMNS if not c.nullable}
    assert {"emp_count", "weight_sum", "county_lat", "county_lon", "year"} <= required
    assert not any(name.startswith(("daioe_", "pctl_", "chg_")) for name in required)


@pytest.mark.skipif(
    not (PATHS.root / "README.md").exists(), reason="README not present"
)
def test_readme_describes_every_column() -> None:
    readme = Path(PATHS.root / "README.md").read_text()
    section = readme.split("## Final dataset schema")[1].split("### Missing values")[0]
    for column in COLUMNS:
        pattern = column.name
        for domain in TAXONOMY.subindices:
            pattern = pattern.replace(f"_{domain}_", "_<domain>_")
        assert pattern in section, f"README schema table does not mention {pattern}"


def test_schema_json_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "schema.json"
    monkeypatch.setattr(sys, "argv", ["daioe-schema", "--output", str(target)])
    export_schema.main()
    document = json.loads(target.read_text())
    assert document == export_schema.build_document()
    assert [c["name"] for c in document["columns"]] == [c.name for c in COLUMNS]
    assert document["rules"]["counties"] == 21
    year = next(c for c in document["columns"] if c["name"] == "year")
    assert year["dtype"] == "Int64"
    assert year["nullable"] is False
