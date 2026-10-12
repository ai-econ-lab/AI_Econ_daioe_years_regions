# Interactive county map of AI exposure (DAIOE) and employment, built with Altair.
# This is a comment, not a docstring: Express would render a top-level string as
# a stray child of the navbar.
import faicons as fa
import polars as pl
from shiny import reactive
from shiny.express import app_opts, input, ui
from shinywidgets import render_altair

from src import charts, data

app_opts(static_assets={"/logos": data.APP_DIR / "logos"})

ui.page_opts(
    title="AI exposure by county",
    fillable=True,
    theme=ui.Theme.from_brand(__file__),
)

# Vega's hover tooltip is appended to the page body, so it needs page level CSS.
ui.head_content(
    ui.tags.style("#vg-tooltip-element, #vg-tooltip-element td { font-size: 16px; }")
)

HINT = "text-muted small mt-n1 mb-2"

with ui.sidebar(title="Controls", width=300):
    ui.img(
        src="/logos/lab.svg",
        alt="AI-Econ Lab logo",
        style="width:100%; max-width:180px; display:block; margin:0 auto 0.5rem;",
    )
    ui.p(
        "How exposed each Swedish county's workforce is to AI: DAIOE scores "
        "weighted by employment across SSYK 2012 occupations.",
        class_="text-muted small",
    )
    ui.hr()
    ui.input_select("subindex", "DAIOE sub-index", data.SUBINDICES)
    ui.p("The AI application the exposure score refers to.", class_=HINT)
    ui.input_slider(
        "year",
        "Year",
        min=data.FIRST_YEAR,
        max=data.LATEST_YEAR,
        value=data.LATEST_YEAR,
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
    ui.input_radio_buttons("level", "Occupation level", data.OCCUPATION_LEVELS)
    ui.p("Sets how detailed the occupation list below is.", class_=HINT)
    ui.input_selectize("group", "Occupation group", data.occupation_choices("SSYK1"))
    ui.p(
        "Restricts the map to one group; 'All occupations' covers the whole workforce.",
        class_=HINT,
    )


@reactive.effect
@reactive.event(input.level)
def _refresh_group_choices() -> None:
    """Offer the groups of the chosen SSYK level and reset to all occupations."""
    ui.update_selectize(
        "group", choices=data.occupation_choices(input.level()), selected="all"
    )


@reactive.calc
def county_frame() -> pl.DataFrame:
    """County x year metrics for the current filters (SSYK4 keeps the full mix)."""
    return data.aggregate(
        "SSYK4",
        ["county_code", "county"],
        input.sex(),
        input.group(),
        input.subindex(),
    )


with ui.card(full_screen=True):
    with ui.card_header(class_="d-flex align-items-center gap-2"):
        ui.span("Employment weighted AI exposure")
        with ui.popover(placement="bottom"):
            fa.icon_svg("circle-info", height="1.2em")
            (
                "Each county's colour is the average DAIOE exposure of its workers, "
                "weighted by employment across the SSYK4 occupations in the chosen "
                "group. The scale is refitted each year, so shades compare counties "
                "within a year, not across years."
            )

    @render_altair
    def county_map():
        """Render the county choropleth for the current controls."""
        # The group briefly outlives a level switch, so it may not be in the choices.
        occupation = data.occupation_choices(input.level()).get(
            input.group(), "All occupations"
        )
        return charts.build_map(
            data.SUBINDICES[input.subindex()], occupation, input.year(), county_frame()
        )
