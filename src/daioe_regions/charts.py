"""Altair chart builders for the county app; each returns one chart."""

from typing import Any, cast

import altair as alt
import polars as pl

from daioe_regions.config import MAP_STYLE


def colour_scale(values: pl.Series) -> alt.Scale:
    """Colour scale fitted to the selected year, so county contrast stays visible."""
    low, high = (
        (0.0, 1.0)
        if values.is_empty()
        else (cast(float, values.min()), cast(float, values.max()))
    )
    return alt.Scale(
        domain=[low, high],
        range=[MAP_STYLE.blue_tint, MAP_STYLE.blue],
        interpolate="lab",
    )


def build_map(
    boundaries: dict[str, Any],
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
        alt.Chart(alt.Data(values=boundaries["features"]))
        .mark_geoshape(stroke="white")
        .transform_lookup(  # ty: ignore[unresolved-attribute]
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
                    gradientLength=MAP_STYLE.legend_gradient_length,
                    titleLimit=MAP_STYLE.legend_title_limit,
                ),
            ),
            strokeWidth=alt.when(hovered)
            .then(alt.value(MAP_STYLE.hover_stroke_width))
            .otherwise(alt.value(MAP_STYLE.base_stroke_width)),
            tooltip=[
                alt.Tooltip("county:N", title="County"),
                alt.Tooltip("value:Q", title="AI exposure", format=".2f"),
                alt.Tooltip("employment:Q", title="Employment", format=",d"),
            ],
        )
        .add_params(hovered)
        .project(type=MAP_STYLE.projection, rotate=list(MAP_STYLE.rotation))
        .properties(width="container", height=MAP_STYLE.height)
        .configure_view(stroke=None)
        .configure_legend(
            labelFontSize=MAP_STYLE.legend_label_size,
            titleFontSize=MAP_STYLE.legend_title_size,
        )
    )
