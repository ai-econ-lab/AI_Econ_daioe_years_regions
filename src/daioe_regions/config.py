"""Constants shared across the app, charts and pipeline, as frozen dataclasses."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Paths:
    """Locations of the project's data and static assets."""

    root: Path

    @property
    def data_dir(self) -> Path:
        """Folder holding the dataset, intermediates and boundaries."""
        return self.root / "data"

    @property
    def dataset(self) -> Path:
        """The merged parquet the app reads."""
        return self.data_dir / "daioe_scb_years_all_levels_geo.parquet"

    @property
    def daioe_intermediate(self) -> Path:
        """The daioe/SCB intermediate published by the daioe_pull branch."""
        return self.data_dir / "daioe_scb_years_all_levels.parquet"

    @property
    def coordinates(self) -> Path:
        """County centroid coordinates published by the geo_pull branch."""
        return self.data_dir / "county_coordinates.parquet"

    @property
    def boundaries(self) -> Path:
        """Simplified county boundary GeoJSON drawn by the map."""
        return self.data_dir / "sweden_counties.geojson"

    @property
    def logos(self) -> Path:
        """Folder served as static assets for the app."""
        return self.root / "logos"


@dataclass(frozen=True, slots=True)
class Taxonomy:
    """Labels and filters for DAIOE sub-indices and sex."""

    subindices: dict[str, str] = field(
        default_factory=lambda: {
            "allapps": "📚 All applications",
            "genai": "🧠 Generative AI",
            "lngmod": "✍️ Language modelling",
            "readcompr": "📖 Reading comprehension",
            "translat": "🌐 Translation",
            "speechrec": "🗣️ Speech recognition",
            "imgrec": "🔎 Image recognition",
            "imggen": "🖌️ Image generation",
            "imgcompr": "🧩 Image comprehension",
            "stratgames": "♟️ Strategy games",
            "videogames": "🎮 Video games (real time)",
        }
    )
    sex_filters: dict[str, list[str]] = field(
        default_factory=lambda: {
            "all": ["men", "women"],
            "men": ["men"],
            "women": ["women"],
        }
    )
    sex_labels: dict[str, str] = field(
        default_factory=lambda: {"all": "All", "men": "Men", "women": "Women"}
    )
    all_key: str = "all"
    all_label: str = "All occupations"


@dataclass(frozen=True, slots=True)
class MapStyle:
    """Colours, sizes and projection of the county choropleth."""

    blue: str = "#0072b2"
    blue_tint: str = "#d6e8f5"
    height: str = "container"
    legend_label_size: int = 14
    legend_title_size: int = 15
    legend_gradient_length: int = 260
    legend_title_limit: int = 300
    tooltip_font_size: int = 16
    projection: str = "transverseMercator"
    rotation: tuple[int, int, int] = (-15, 0, 0)
    hover_stroke_width: float = 2
    base_stroke_width: float = 0.5


@dataclass(frozen=True, slots=True)
class AppText:
    """User facing text of the Shiny app."""

    page_title: str = "AI exposure by county"
    logo_alt: str = "AI-Econ Lab logo"
    intro: str = (
        "How exposed each Swedish county's workforce is to AI: DAIOE scores "
        "weighted by employment across SSYK 2012 occupations."
    )
    subindex_hint: str = "The AI application the exposure score refers to."
    level_hint: str = "Sets how detailed the occupation list below is."
    group_hint: str = (
        "Restricts the map to one group; 'All occupations' covers the whole workforce."
    )
    card_title: str = "Employment weighted AI exposure"
    popover: str = (
        "Each county's colour is the average DAIOE exposure of its workers, "
        "weighted by employment across the SSYK4 occupations in the chosen "
        "group. The scale is refitted each year, so shades compare counties "
        "within a year, not across years."
    )


@dataclass(frozen=True, slots=True)
class ValidationRules:
    """Expectations the published dataset must meet before it is released."""

    key: tuple[str, ...] = ("level", "ssyk_code", "county_code", "sex", "year")
    expected_levels: frozenset[str] = frozenset({"SSYK1", "SSYK2", "SSYK3", "SSYK4"})
    expected_counties: int = 21
    expected_sexes: int = 2
    # SSYK1 group 0 (armed forces) has no DAIOE scores, so it is legitimately
    # null. Every other major group must have a finite score; a null here means
    # NaN scores are propagating through the aggregation again.
    guard_metric: str = "daioe_allapps_wavg"


@dataclass(frozen=True, slots=True)
class MergeSpec:
    """How the geodata merge orders its output."""

    # Canonical row order so identical data always serialises to identical
    # bytes; without it, unstable ordering upstream reshuffled every write and
    # made every run look like a data change to git.
    sort_key: tuple[str, ...] = ("year", "county_code", "level", "ssyk_code", "sex")
    coord_columns: tuple[str, ...] = ("county_code", "county_lat", "county_lon")


PATHS = Paths(root=Path(__file__).resolve().parents[2])
TAXONOMY = Taxonomy()
MAP_STYLE = MapStyle()
APP_TEXT = AppText()
VALIDATION = ValidationRules()
MERGE = MergeSpec()
