"""Altair chart builders for the county app; each returns one chart."""

import altair as alt
import polars as pl

from src.data import BOUNDARIES

# Palette from _brand.yml (Okabe-Ito CVD-safe ramp).
BLUE = "#0072b2"
BLUE_TINT = "#d6e8f5"


def colour_scale(values: pl.Series) -> alt.Scale:
    """Colour scale fitted to the selected year, so county contrast stays visible."""
    low, high = (0.0, 1.0) if values.is_empty() else (values.min(), values.max())
    return alt.Scale(domain=[low, high], range=[BLUE_TINT, BLUE], interpolate="lab")


def build_map(
    subindex: str,
    occupation: str,
    year: int,
    counties: pl.DataFrame,
) -> alt.Chart:
    """County choropleth of AI exposure for one sub-index and occupation group."""
    label = [f"{subindex} exposure (weighted avg)", occupation]
    hovered = alt.selection_point(
        name="hover",
        fields=["county_code"],
        on="pointerover",
        clear="pointerout",
        empty=False,
    )
    map_values = counties.filter(pl.col("year") == year).select(
        "county_code",
        "county",
        "employment",
        pl.col("exposure").alias("value"),
    )
    return (
        alt.Chart(alt.Data(values=BOUNDARIES["features"]))
        .mark_geoshape(stroke="white")
        .transform_lookup(
            lookup="properties.county_code",
            from_=alt.LookupData(
                map_values,
                "county_code",
                ["county_code", "county", "employment", "value"],
            ),
        )
        .encode(
            color=alt.Color(
                "value:Q",
                scale=colour_scale(map_values.get_column("value").drop_nulls()),
                legend=alt.Legend(
                    title=label,
                    format=".2f",
                    orient="bottom",
                    gradientLength=260,
                    titleLimit=300,
                ),
            ),
            strokeWidth=alt.when(hovered).then(alt.value(2)).otherwise(alt.value(0.5)),
            tooltip=[
                alt.Tooltip("county:N", title="County"),
                alt.Tooltip("value:Q", title="AI exposure", format=".2f"),
                alt.Tooltip("employment:Q", title="Employment", format=",d"),
            ],
        )
        .add_params(hovered)
        .project(type="transverseMercator", rotate=[-15, 0, 0])
        .properties(width="container", height="container")
        .configure_view(stroke=None)
        .configure_legend(labelFontSize=14, titleFontSize=15)
    )
