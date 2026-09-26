"""Interactive county map of AI exposure (DAIOE) and employment, built with Altair."""

import json
from pathlib import Path

import altair as alt
import polars as pl
import polars.selectors as cs
from shiny import reactive
from shiny.express import input, ui
from shinywidgets import render_altair

APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / "data" / "daioe_scb_years_all_levels_geo.parquet"
BOUNDARIES_PATH = APP_DIR / "data" / "sweden_counties.geojson"

DATA = pl.read_parquet(DATA_PATH)
BOUNDARIES = json.loads(BOUNDARIES_PATH.read_text())
YEARS = DATA.get_column("year").unique().sort()
FIRST_YEAR, LATEST_YEAR = YEARS.min(), YEARS.max()

# Palette from _brand.yml (Okabe-Ito CVD-safe ramp).
BLUE, ORANGE, MUTED, NAVY, INK = (
    "#0072b2",
    "#d55e00",
    "#65717f",
    "#232b65",
    "#161d2b",
)
BLUE_TINT = "#d6e8f5"
ORANGE_TINT = "#f6d9c4"

SUBINDICES = {
    "allapps": "All applications",
    "genai": "Generative AI",
    "lngmod": "Language modelling",
    "readcompr": "Reading comprehension",
    "translat": "Translation",
    "speechrec": "Speech recognition",
    "imgrec": "Image recognition",
    "imggen": "Image generation",
    "imgcompr": "Image compression",
    "stratgames": "Strategy games",
    "videogames": "Video games",
}

# Metric key -> (label, polars column, colour scale kind, tooltip format).
METRICS = {
    "exposure": ("AI exposure (weighted avg)", "exposure", "sequential", ".2f"),
    "high_share": (
        "Share in highest exposure level",
        "high_exposure_share",
        "sequential",
        ".1%",
    ),
    "employment": ("Employment", "employment", "sequential", ",d"),
    "pct_chg_1y": ("Employment change, 1 year", "pct_chg_1y", "diverging", "+.1%"),
    "pct_chg_3y": ("Employment change, 3 years", "pct_chg_3y", "diverging", "+.1%"),
    "pct_chg_5y": ("Employment change, 5 years", "pct_chg_5y", "diverging", "+.1%"),
}

OCCUPATION_GROUPS = {
    "all": "All occupations",
    **{
        row["ssyk_code"]: f"{row['ssyk_code']} {row['occupation']}"
        for row in DATA.filter(pl.col("level") == "SSYK1")
        .select("ssyk_code", "occupation")
        .unique()
        .sort("ssyk_code")
        .iter_rows(named=True)
    },
}

SEX_FILTERS = {"all": ["men", "women"], "men": ["men"], "women": ["women"]}


def aggregate(
    level: str,
    by: list[str],
    sex: str,
    group: str,
    subindex: str,
) -> pl.DataFrame:
    """Aggregate employment, exposure and change metrics over `by` and year.

    Exposure and the high-exposure share are employment weighted; percentage
    changes are computed from summed counts, never by averaging percentages.
    """
    exposure = pl.col(f"daioe_{subindex}_wavg")
    top_level = pl.col(f"daioe_{subindex}_Level_Exposure")

    def weighted_share(numerator: pl.Expr, valid: pl.Expr) -> pl.Expr:
        return numerator.sum() / pl.col("emp_count").filter(valid).sum()

    def pct_change(change: str) -> pl.Expr:
        valid = pl.col(change).is_not_null()
        summed = pl.col(change).sum()
        return summed / (pl.col("emp_count").filter(valid).sum() - summed)

    frame = DATA.filter(
        (pl.col("level") == level) & pl.col("sex").is_in(SEX_FILTERS[sex]),
    )
    if group != "all":
        frame = frame.filter(pl.col("ssyk_code").str.starts_with(group))

    return (
        frame.group_by([*by, "year"])
        .agg(
            pl.col("emp_count").sum().alias("employment"),
            weighted_share(
                (exposure * pl.col("emp_count")).filter(exposure.is_not_null()),
                exposure.is_not_null(),
            ).alias("exposure"),
            weighted_share(
                pl.col("emp_count").filter(top_level == 5),
                top_level.is_not_null(),
            ).alias("high_exposure_share"),
            pct_change("chg_1y").alias("pct_chg_1y"),
            pct_change("chg_3y").alias("pct_chg_3y"),
            pct_change("chg_5y").alias("pct_chg_5y"),
        )
        .with_columns(cs.float().fill_nan(None))
        .sort([*by, "year"])
    )


def occupation_mix(sex: str, subindex: str) -> pl.DataFrame:
    """SSYK1 employment share and exposure per county and year, plus Sweden's share."""
    by_group = aggregate(
        "SSYK1",
        ["county_code", "ssyk_code", "occupation"],
        sex,
        "all",
        subindex,
    ).with_columns(
        (
            pl.col("employment")
            / pl.col("employment").sum().over("county_code", "year")
        ).alias(
            "share",
        ),
    )
    national = aggregate("SSYK1", ["ssyk_code"], sex, "all", subindex).select(
        "ssyk_code",
        "year",
        (pl.col("employment") / pl.col("employment").sum().over("year")).alias(
            "national_share",
        ),
    )
    return by_group.join(national, on=["ssyk_code", "year"])


def colour_scale(kind: str, values: pl.Series) -> alt.Scale:
    """Colour scale fitted to the selected year, so county contrast stays visible."""
    low, high = values.min(), values.max()
    if kind == "diverging":
        limit = max(abs(low), abs(high))
        return alt.Scale(
            domain=[-limit, 0, limit],
            range=[ORANGE, "#f3f5f8", BLUE],
            interpolate="lab",
        )
    return alt.Scale(domain=[low, high], range=[BLUE_TINT, BLUE], interpolate="lab")


def build_chart(
    metric: str,
    year: int,
    counties: pl.DataFrame,
    national: pl.DataFrame,
    mix: pl.DataFrame,
) -> alt.HConcatChart:
    """County choropleth linked to a trend chart and an occupation mix chart."""
    label, column, kind, fmt = METRICS[metric]

    selected = alt.selection_point(
        name="county",
        fields=["county_code"],
        value=[{"county_code": "01"}],
        empty=False,
    )
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
        pl.col(column).alias("value"),
    )
    shapes = (
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
                scale=colour_scale(kind, map_values.get_column("value").drop_nulls()),
                legend=alt.Legend(
                    title=label,
                    format=fmt,
                    orient="bottom",
                    gradientLength=260,
                    titleLimit=300,
                ),
            ),
            opacity=alt.when(selected).then(alt.value(1)).otherwise(alt.value(0.55)),
            strokeWidth=alt.when(hovered | selected)
            .then(alt.value(2))
            .otherwise(alt.value(0.5)),
            tooltip=[
                alt.Tooltip("county:N", title="County"),
                alt.Tooltip("value:Q", title=label, format=fmt),
                alt.Tooltip("employment:Q", title="Employment", format=",d"),
            ],
        )
        .add_params(selected, hovered)
        .project(type="transverseMercator", rotate=[-15, 0, 0])
        .properties(width=330, height=520, title=f"{label}, {year}")
    )

    trend_data = pl.concat(
        [
            counties.select(
                "county_code",
                "county",
                "year",
                pl.col(column).alias("value"),
            ),
            national.select(
                pl.lit("00").alias("county_code"),
                pl.lit("Sweden").alias("county"),
                "year",
                pl.col(column).alias("value"),
            ),
        ],
    )
    trend_axis = alt.Axis(format=fmt, title=None)
    year_axis = alt.X(
        "year:O", title=None, axis=alt.Axis(labelAngle=0, values=list(YEARS))
    )
    sweden_line = (
        alt.Chart(trend_data.filter(pl.col("county_code") == "00"))
        .mark_line(color=MUTED, strokeDash=[4, 3])
        .encode(year_axis, alt.Y("value:Q", axis=trend_axis))
    )
    county_line = (
        alt.Chart(trend_data.filter(pl.col("county_code") != "00"))
        .mark_line(color=BLUE, point=True)
        .encode(
            year_axis,
            alt.Y("value:Q", axis=trend_axis),
            tooltip=[
                alt.Tooltip("county:N", title="County"),
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip("value:Q", title=label, format=fmt),
            ],
        )
        .transform_filter(selected)
    )
    year_rule = (
        alt.Chart(pl.DataFrame({"year": [year]}))
        .mark_rule(color=NAVY, strokeDash=[2, 2])
        .encode(alt.X("year:O"))
    )
    trend = alt.layer(sweden_line, county_line, year_rule).properties(
        width=430,
        height=200,
        title=alt.Title(
            f"{label} over time",
            subtitle="Selected county (blue) vs Sweden (grey dashed). Click a county on the map.",
        ),
    )

    mix = mix.filter(pl.col("year") == year)
    mix_axis_y = alt.Y(
        "occupation:N",
        sort=alt.EncodingSortField("ssyk_code"),
        title=None,
        axis=alt.Axis(labelLimit=260),
    )
    mix_bars = (
        alt.Chart(mix)
        .mark_bar()
        .encode(
            mix_axis_y,
            alt.X("share:Q", title=None, axis=alt.Axis(format=".0%")),
            alt.Color(
                "exposure:Q",
                scale=alt.Scale(
                    domain=[mix["exposure"].min(), mix["exposure"].max()],
                    range=[BLUE_TINT, BLUE],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("county_code:N", title="County code"),
                alt.Tooltip("occupation:N", title="Occupation"),
                alt.Tooltip(
                    "share:Q", title="Share of county employment", format=".1%"
                ),
                alt.Tooltip("exposure:Q", title="AI exposure", format=".2f"),
            ],
        )
        .transform_filter(selected)
    )
    mix_national = (
        alt.Chart(mix.unique(subset="ssyk_code"))
        .mark_tick(color=INK, thickness=2, size=14)
        .encode(mix_axis_y, alt.X("national_share:Q"))
    )
    occupation_mix = alt.layer(mix_bars, mix_national).properties(
        width=430,
        height=230,
        title=alt.Title(
            f"Occupation mix, {year}",
            subtitle="Bars: selected county, shaded by AI exposure. Dark tick: Sweden.",
        ),
    )

    return (
        alt.hconcat(shapes, alt.vconcat(trend, occupation_mix))
        .resolve_scale(color="independent")
        .properties(padding={"left": 16, "right": 8, "top": 8, "bottom": 8})
        .configure_view(stroke=None)
        .configure_title(anchor="start", color=NAVY)
    )


ui.page_opts(
    title="AI exposure by county",
    fillable=True,
    theme=ui.Theme.from_brand(__file__),
)

with ui.sidebar(title="Map controls", width=300):
    ui.input_select(
        "metric",
        "Metric",
        {key: spec[0] for key, spec in METRICS.items()},
    )
    with ui.panel_conditional(
        "input.metric == 'exposure' || input.metric == 'high_share'"
    ):
        ui.input_select("subindex", "DAIOE sub-index", SUBINDICES)
    ui.input_slider(
        "year",
        "Year",
        min=FIRST_YEAR,
        max=LATEST_YEAR,
        value=LATEST_YEAR,
        step=1,
        sep="",
        animate=True,
    )
    ui.input_radio_buttons(
        "sex",
        "Sex",
        {"all": "All", "men": "Men", "women": "Women"},
        inline=True,
    )
    ui.input_select("group", "Occupation group", OCCUPATION_GROUPS)


@reactive.calc
def county_frame() -> pl.DataFrame:
    """County x year metrics for the current filters (SSYK4 keeps the full mix)."""
    return aggregate(
        "SSYK4",
        ["county_code", "county"],
        input.sex(),
        input.group(),
        input.subindex(),
    )


@reactive.calc
def national_frame() -> pl.DataFrame:
    """Sweden-wide year metrics for the current filters."""
    return aggregate("SSYK4", [], input.sex(), input.group(), input.subindex())


@reactive.calc
def mix_frame() -> pl.DataFrame:
    """SSYK1 mix per county and year for the current sex and sub-index."""
    return occupation_mix(input.sex(), input.subindex())


with ui.card(full_screen=True):

    @render_altair
    def county_map():
        """Render the linked county map for the current controls."""
        return build_chart(
            input.metric(),
            input.year(),
            county_frame(),
            national_frame(),
            mix_frame(),
        )
