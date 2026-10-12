"""Data loading and polars aggregations behind the county app."""

import json
from pathlib import Path

import polars as pl
import polars.selectors as cs

APP_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = APP_DIR / "data" / "daioe_scb_years_all_levels_geo.parquet"
BOUNDARIES_PATH = APP_DIR / "data" / "sweden_counties.geojson"

DATA = pl.read_parquet(DATA_PATH)
BOUNDARIES = json.loads(BOUNDARIES_PATH.read_text())
YEARS = DATA.get_column("year").unique().sort()
FIRST_YEAR, LATEST_YEAR = YEARS.min(), YEARS.max()

SUBINDICES = {
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

OCCUPATION_LEVELS = {
    "SSYK1": "SSYK1 (10 groups)",
    "SSYK2": "SSYK2 (46 groups)",
    "SSYK3": "SSYK3 (148 groups)",
    "SSYK4": "SSYK4 (429 groups)",
}


def occupation_choices(level: str) -> dict[str, str]:
    """Occupation group choices at one SSYK level, led by the all-occupations option."""
    groups = (
        DATA.filter(pl.col("level") == level)
        .select("ssyk_code", "occupation")
        .unique()
        .sort("ssyk_code")
    )
    return {
        "all": "All occupations",
        **{
            row["ssyk_code"]: f"{row['ssyk_code']} {row['occupation']}"
            for row in groups.iter_rows(named=True)
        },
    }


SEX_FILTERS = {"all": ["men", "women"], "men": ["men"], "women": ["women"]}


def filter_rows(level: str, sex: str, group: str) -> pl.DataFrame:
    """Rows at one SSYK level for the chosen sex and occupation group prefix."""
    frame = DATA.filter(
        (pl.col("level") == level) & pl.col("sex").is_in(SEX_FILTERS[sex]),
    )
    if group != "all":
        frame = frame.filter(pl.col("ssyk_code").str.starts_with(group))
    return frame


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

    return (
        filter_rows(level, sex, group)
        .group_by([*by, "year"])
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
