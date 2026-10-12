"""Map chart construction in daioe_regions.charts."""

import polars as pl
import pytest

from daioe_regions import charts
from daioe_regions.config import MAP_STYLE

BOUNDARIES = {
    "features": [
        {
            "type": "Feature",
            "properties": {"county_code": code},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[x, 59], [x + 1, 59], [x + 1, 60], [x, 59]]],
            },
        }
        for code, x in (("01", 17), ("03", 18))
    ],
}


@pytest.fixture
def counties() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "county_code": ["01", "03", "01"],
            "county": ["Stockholm county", "Uppsala county", "Stockholm county"],
            "year": [2024, 2024, 2023],
            "employment": [1000, 400, 900],
            "exposure": [30.0, 20.0, 99.0],
        }
    )


def build(counties: pl.DataFrame, year: int = 2024) -> dict:
    return charts.build_map(
        BOUNDARIES, "Generative AI", "23 Teachers", year, counties
    ).to_dict()


def test_legend_title_names_subindex_and_occupation(counties: pl.DataFrame) -> None:
    legend = build(counties)["encoding"]["color"]["legend"]
    assert legend["title"] == [
        "Generative AI exposure (weighted avg)",
        "23 Teachers",
    ]


def test_colour_scale_is_fitted_to_the_selected_year(counties: pl.DataFrame) -> None:
    scale = build(counties)["encoding"]["color"]["scale"]
    assert scale["domain"] == [20.0, 30.0]
    assert scale["range"] == [MAP_STYLE.blue_tint, MAP_STYLE.blue]


def test_colour_scale_falls_back_when_the_year_has_no_values(
    counties: pl.DataFrame,
) -> None:
    scale = build(counties, year=1999)["encoding"]["color"]["scale"]
    assert scale["domain"] == [0.0, 1.0]


def test_colour_scale_ignores_nulls() -> None:
    scale = charts.colour_scale(
        pl.Series([None, 5.0, 7.0], dtype=pl.Float64).drop_nulls()
    )
    assert scale.domain == [5.0, 7.0]


def test_only_the_selected_year_reaches_the_lookup(counties: pl.DataFrame) -> None:
    spec = build(counties)
    lookup = spec["transform"][0]["from"]["data"]["name"]
    rows = spec["datasets"][lookup]
    assert {row["value"] for row in rows} == {30.0, 20.0}
