"""Typed schema of the published dataset: the single definition of its columns.

`daioe-validate` enforces it (names, dtypes, nullability, ranges), the tests build
their fixtures from it, and the README table describes the same columns.
"""

from dataclasses import dataclass

import polars as pl

from daioe_regions.config import TAXONOMY


@dataclass(frozen=True, slots=True)
class Column:
    """One dataset column: its dtype, whether it may be null, and its value range."""

    name: str
    dtype: type[pl.DataType]
    description: str
    nullable: bool = False
    minimum: float | None = None
    maximum: float | None = None


IDENTIFIERS = (
    Column("level", pl.String, "SSYK level: SSYK1 to SSYK4"),
    Column("ssyk_code", pl.String, "SSYK 2012 code, 1 to 4 digits matching `level`"),
    Column("occupation", pl.String, "English occupation name"),
    Column("county_code", pl.String, "SCB county code, two digits"),
    Column("county", pl.String, "County name"),
    Column("sex", pl.String, "men or women"),
    Column("year", pl.Int64, "Calendar year"),
)

EMPLOYMENT = (
    Column("emp_count", pl.Int64, "Employed people (SCB)", minimum=0),
    Column("chg_1y", pl.Int64, "Change in emp_count over 1 year", nullable=True),
    Column("chg_3y", pl.Int64, "Change in emp_count over 3 years", nullable=True),
    Column("chg_5y", pl.Int64, "Change in emp_count over 5 years", nullable=True),
    Column(
        "pct_chg_1y",
        pl.Float64,
        "Percentage change over 1 year, in percent (-100 means all jobs lost)",
        nullable=True,
        minimum=-100,
    ),
    Column(
        "pct_chg_3y",
        pl.Float64,
        "Percentage change over 3 years, in percent",
        nullable=True,
        minimum=-100,
    ),
    Column(
        "pct_chg_5y",
        pl.Float64,
        "Percentage change over 5 years, in percent",
        nullable=True,
        minimum=-100,
    ),
    Column(
        "weight_sum",
        pl.Int64,
        "National SSYK4 total repeated per SSYK code, not county specific",
        minimum=0,
    ),
)

GEOGRAPHY = (
    Column("county_lat", pl.Float64, "County centroid latitude"),
    Column("county_lon", pl.Float64, "County centroid longitude"),
)


def domain_columns(domain: str) -> tuple[Column, ...]:
    """Return the five DAIOE columns that each sub-index (domain) contributes."""
    return (
        Column(
            f"daioe_{domain}_avg",
            pl.Float64,
            f"Simple mean {domain} score over the group's SSYK4 codes",
            nullable=True,
            minimum=0,
        ),
        Column(
            f"daioe_{domain}_wavg",
            pl.Float64,
            f"Employment weighted mean {domain} score over the group's SSYK4 codes",
            nullable=True,
            minimum=0,
        ),
        Column(
            f"pctl_daioe_{domain}_avg",
            pl.Float64,
            f"Percentile of daioe_{domain}_avg within year and level",
            nullable=True,
            minimum=0,
            maximum=100,
        ),
        Column(
            f"pctl_daioe_{domain}_wavg",
            pl.Float64,
            f"Percentile of daioe_{domain}_wavg within year and level",
            nullable=True,
            minimum=0,
            maximum=100,
        ),
        Column(
            f"daioe_{domain}_Level_Exposure",
            pl.Int8,
            f"Exposure quintile of pctl_daioe_{domain}_wavg, 1 least to 5 most exposed",
            nullable=True,
            minimum=1,
            maximum=5,
        ),
    )


COLUMNS: tuple[Column, ...] = (
    *IDENTIFIERS,
    *EMPLOYMENT,
    *(col for domain in TAXONOMY.subindices for col in domain_columns(domain)),
    *GEOGRAPHY,
)
SCHEMA: dict[str, type[pl.DataType]] = {col.name: col.dtype for col in COLUMNS}
