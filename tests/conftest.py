"""Shared fixtures: a hand built frame for aggregation maths and a valid dataset."""

from typing import Any

import polars as pl
import pytest

from daioe_regions.schema import COLUMNS, SCHEMA, Column

SUBINDEX = "genai"


def make_row(**overrides: Any) -> dict[str, Any]:
    """One SSYK4 row with neutral defaults; tests override only what matters."""
    row: dict[str, Any] = {
        "level": "SSYK4",
        "ssyk_code": "1111",
        "occupation": "Legislators",
        "county_code": "01",
        "county": "Stockholm county",
        "sex": "men",
        "year": 2024,
        "emp_count": 100,
        "chg_1y": None,
        "chg_3y": None,
        "chg_5y": None,
        f"daioe_{SUBINDEX}_wavg": 10.0,
        f"daioe_{SUBINDEX}_Level_Exposure": 2,
    }
    return row | overrides


@pytest.fixture
def small_frame() -> pl.DataFrame:
    """Two Stockholm occupations (men and women), one null score, one bare county.

    Hand checked numbers for county 01 in 2024, men only:
    exposure (100 * 10 + 300 * 20) / 400 = 17.5; employment 400 (the null scored
    occupation adds 600 to employment but not to the weighting).
    """
    rows = [
        make_row(
            emp_count=100,
            chg_1y=20,
            **{f"daioe_{SUBINDEX}_wavg": 10.0, f"daioe_{SUBINDEX}_Level_Exposure": 5},
        ),
        make_row(
            ssyk_code="2222",
            occupation="Engineers",
            emp_count=300,
            chg_1y=-30,
            **{f"daioe_{SUBINDEX}_wavg": 20.0, f"daioe_{SUBINDEX}_Level_Exposure": 2},
        ),
        make_row(
            ssyk_code="3333",
            occupation="Unscored",
            emp_count=600,
            **{
                f"daioe_{SUBINDEX}_wavg": None,
                f"daioe_{SUBINDEX}_Level_Exposure": None,
            },
        ),
        make_row(
            sex="women",
            emp_count=50,
            **{f"daioe_{SUBINDEX}_wavg": 40.0, f"daioe_{SUBINDEX}_Level_Exposure": 4},
        ),
        make_row(
            county_code="03",
            county="Uppsala county",
            ssyk_code="3333",
            occupation="Unscored",
            emp_count=70,
            **{
                f"daioe_{SUBINDEX}_wavg": None,
                f"daioe_{SUBINDEX}_Level_Exposure": None,
            },
        ),
        make_row(year=2023, emp_count=90),
        make_row(level="SSYK1", ssyk_code="1", occupation="Managers", emp_count=500),
    ]
    schema_overrides = {
        "chg_1y": pl.Int64,
        "chg_3y": pl.Int64,
        "chg_5y": pl.Int64,
        f"daioe_{SUBINDEX}_wavg": pl.Float64,
        f"daioe_{SUBINDEX}_Level_Exposure": pl.Int64,
    }
    return pl.DataFrame(rows, schema_overrides=schema_overrides)


def schema_default(column: Column) -> Any:
    """A value that satisfies the column's dtype and range."""
    if column.dtype == pl.String:
        return "x"
    if column.dtype == pl.Float64:
        return 5.0
    return max(column.minimum or 0, 3 if column.dtype == pl.Int8 else 100)


@pytest.fixture
def valid_dataset() -> pl.DataFrame:
    """A dataset that satisfies the whole schema (21 counties, 2 years)."""
    codes = {
        "SSYK1": ["0", "1"],
        "SSYK2": ["11"],
        "SSYK3": ["111"],
        "SSYK4": ["1111"],
    }
    base = {column.name: schema_default(column) for column in COLUMNS}
    rows = []
    for level, level_codes in codes.items():
        for code in level_codes:
            # Armed forces (SSYK1 group 0) legitimately has no DAIOE scores.
            unscored = {
                column.name: None
                for column in COLUMNS
                if code == "0" and column.name.startswith(("daioe_", "pctl_"))
            }
            for county in range(1, 22):
                for sex in ("men", "women"):
                    for year in (2023, 2024):
                        rows.append(
                            base
                            | unscored
                            | {
                                "level": level,
                                "ssyk_code": code,
                                "county_code": f"{county:02d}",
                                "sex": sex,
                                "year": year,
                            }
                        )
    return pl.DataFrame(rows, schema=SCHEMA)
