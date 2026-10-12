"""Data loading and polars aggregations behind the county app."""

import json
from functools import cache
from pathlib import Path
from typing import Any, cast

import polars as pl
import polars.selectors as cs

from daioe_regions.config import PATHS, TAXONOMY


@cache
def load_dataset(path: Path = PATHS.dataset) -> pl.DataFrame:
    """Read the merged daioe/SCB/geo parquet once per path."""
    return pl.read_parquet(path)


@cache
def load_boundaries(path: Path = PATHS.boundaries) -> dict[str, Any]:
    """Read the county boundary GeoJSON once per path."""
    return json.loads(path.read_text())


def year_bounds(df: pl.DataFrame) -> tuple[int, int]:
    """First and latest year present in the dataset."""
    years = df.get_column("year")
    return cast(int, years.min()), cast(int, years.max())


def level_labels(df: pl.DataFrame) -> dict[str, str]:
    """SSYK level choices labelled with how many groups each level has."""
    counts = (
        df.group_by("level")
        .agg(pl.col("ssyk_code").n_unique().alias("groups"))
        .sort("level")
    )
    return {
        row["level"]: f"{row['level']} ({row['groups']} groups)"
        for row in counts.iter_rows(named=True)
    }


def occupation_choices(df: pl.DataFrame, level: str) -> dict[str, str]:
    """Occupation group choices at one SSYK level, led by the all-occupations option."""
    groups = (
        df.filter(pl.col("level") == level)
        .select("ssyk_code", "occupation")
        .unique()
        .sort("ssyk_code")
    )
    return {
        TAXONOMY.all_key: TAXONOMY.all_label,
        **{
            row["ssyk_code"]: f"{row['ssyk_code']} {row['occupation']}"
            for row in groups.iter_rows(named=True)
        },
    }


def filter_rows(df: pl.DataFrame, level: str, sex: str, group: str) -> pl.DataFrame:
    """Rows at one SSYK level for the chosen sex and occupation group prefix."""
    frame = df.filter(
        (pl.col("level") == level) & pl.col("sex").is_in(TAXONOMY.sex_filters[sex]),
    )
    if group != TAXONOMY.all_key:
        frame = frame.filter(pl.col("ssyk_code").str.starts_with(group))
    return frame


def aggregate(
    df: pl.DataFrame,
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
        filter_rows(df, level, sex, group)
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
