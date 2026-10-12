# Interactive county map of AI exposure (DAIOE) and employment, built with Altair.
# This is a comment, not a docstring: Express would render a top-level string as
# a stray child of the navbar.
import faicons as fa
import polars as pl
from shiny import reactive
from shiny.express import app_opts, input, ui
from shinywidgets import render_altair

from daioe_regions import charts, data
from daioe_regions.config import APP_TEXT, MAP_STYLE, PATHS, TAXONOMY

DATASET = data.load_dataset()
BOUNDARIES = data.load_boundaries()
FIRST_YEAR, LATEST_YEAR = data.year_bounds(DATASET)

app_opts(static_assets={"/logos": PATHS.logos})

ui.page_opts(
    title=APP_TEXT.page_title,
    fillable=True,
    theme=ui.Theme.from_brand(__file__),
)

# Vega's hover tooltip is appended to the page body, so it needs page level CSS.
ui.head_content(
    ui.tags.style(
        "#vg-tooltip-element, #vg-tooltip-element td "
        f"{{ font-size: {MAP_STYLE.tooltip_font_size}px; }}"
    )
)

HINT = "text-muted small mt-n1 mb-2"

with ui.sidebar(title="Controls", width=300):
    ui.img(
        src="/logos/lab.svg",
        alt=APP_TEXT.logo_alt,
        style="width:100%; max-width:180px; display:block; margin:0 auto 0.5rem;",
    )
    ui.p(APP_TEXT.intro, class_="text-muted small")
    ui.hr()
    ui.input_select("subindex", "DAIOE sub-index", TAXONOMY.subindices)
    ui.p(APP_TEXT.subindex_hint, class_=HINT)
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
    ui.input_radio_buttons("sex", "Sex", TAXONOMY.sex_labels, inline=True)
    ui.input_radio_buttons("level", "Occupation level", TAXONOMY.occupation_levels)
    ui.p(APP_TEXT.level_hint, class_=HINT)
    ui.input_selectize(
        "group", "Occupation group", data.occupation_choices(DATASET, "SSYK1")
    )
    ui.p(APP_TEXT.group_hint, class_=HINT)


@reactive.effect
@reactive.event(input.level)
def _refresh_group_choices() -> None:
    """Offer the groups of the chosen SSYK level and reset to all occupations."""
    ui.update_selectize(
        "group",
        choices=data.occupation_choices(DATASET, input.level()),
        selected=TAXONOMY.all_key,
    )


@reactive.calc
def county_frame() -> pl.DataFrame:
    """County x year metrics for the current filters (SSYK4 keeps the full mix)."""
    return data.aggregate(
        DATASET,
        "SSYK4",
        ["county_code", "county"],
        input.sex(),
        input.group(),
        input.subindex(),
    )


with ui.card(full_screen=True):
    with ui.card_header(class_="d-flex align-items-center gap-2"):
        ui.span(APP_TEXT.card_title)
        with ui.popover(placement="bottom"):
            fa.icon_svg("circle-info", height="1.2em")
            APP_TEXT.popover  # noqa: B018 (Express displays bare expressions)

    @render_altair
    def county_map():
        """Render the county choropleth for the current controls."""
        # The group briefly outlives a level switch, so it may not be in the choices.
        occupation = data.occupation_choices(DATASET, input.level()).get(
            input.group(), TAXONOMY.all_label
        )
        return charts.build_map(
            BOUNDARIES,
            TAXONOMY.subindices[input.subindex()],
            occupation,
            input.year(),
            county_frame(),
        )
