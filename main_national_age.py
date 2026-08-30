"""
main_national_age.py.
----------------------
Merges DAIOE AI-exposure scores with the national occupation x age x sex
employment table (`scb_pull/scripts/pull_national_age.py` +
`aggregate_national_age.py`), for Magnus's item 5: SCB only crosses age
with occupation at the national level, never at region, so this is a
separate cut alongside the regional one `main.py` already produces.

Reuses main.py's DAIOE-aggregation pipeline unchanged: the unweighted
daioe_*_avg metrics it computes are already a pure function of (year,
ssyk_code, level), independent of whether the final output is cross-cut
by region (main.py) or age (here). The *weighted* daioe_*_wavg metrics
(and everything derived from them: percentiles, 1-5 exposure levels) also
need to match exactly between the two datasets, so this script weights
by the regional table's national SSYK4 employment count (main.py's own
SCB_SOURCE, imported as REGIONAL_SCB_SOURCE below) rather than computing
its own from the age table's SCB source: the two table families
(AM0208M regional vs AM0208E age) don't perfectly agree (median
difference ~1 worker nationally), which would otherwise nudge the
weighted metrics for a handful of occupations depending on which dataset
you looked at them in. Only the employment-side input for
build_scb_employment_changes and the final sort key change.
"""

from pathlib import Path

import polars as pl

from main import (
    DAIOE_SOURCE,
    aggregate_daioe_level,
    build_daioe_ssyk12,
    build_exposure_levels,
    build_scb_employment_changes,
    build_scb_level4_counts,
    extend_daioe_years,
)
from main import SCB_SOURCE as REGIONAL_SCB_SOURCE

ROOT = Path.cwd().resolve()
DATA_DIR = ROOT / "data"
SCB_SOURCE = (
    DATA_DIR / "processed" / "ssyk12_national_age_aggregated_ssyk4_to_ssyk1.parquet"
)
OUTPUT_PATH = DATA_DIR / "daioe_scb_national_age.parquet"

# Canonical row order, same reasoning as main.py's SORT_KEY: without this,
# unstable join/group_by order makes every write look like a data change.
SORT_KEY = ["level", "ssyk_code", "age", "sex", "year"]


def main() -> None:
    # --- 1. Load sources lazily ---
    daioe_lf = pl.scan_csv(DAIOE_SOURCE)
    scb_lf = pl.scan_parquet(SCB_SOURCE)

    # --- 2. SCB: employment changes (grouped by whatever dims are present,
    #     here level/ssyk_code/occupation/age/sex instead of county) ---
    scb_changes = build_scb_employment_changes(scb_lf)

    # --- 3. DAIOE: derive SSYK2012 hierarchy codes ---
    daioe_ssyk12 = build_daioe_ssyk12(daioe_lf)

    # --- 4. Extend DAIOE years to match SCB coverage ---
    daioe_extended = extend_daioe_years(daioe_ssyk12, scb_lf)

    # --- 5. SCB SSYK4 counts for weighting: from the regional table, not
    #     this script's own age data, so weighted exposure metrics match
    #     main.py's regional output exactly for the same occupation ---
    regional_scb_lf = pl.scan_parquet(REGIONAL_SCB_SOURCE)
    scb_level4 = build_scb_level4_counts(regional_scb_lf)

    # Join DAIOE with SCB SSYK4 employment counts (for weighted aggregation)
    daioe_scb = daioe_extended.join(
        scb_level4,
        left_on=["year", "code_4"],
        right_on=["year", "ssyk_code"],
        how="left",
    )

    # --- 6. Aggregate DAIOE metrics across all SSYK levels ---
    levels_map = {
        "code_4": "SSYK4",
        "code_3": "SSYK3",
        "code_2": "SSYK2",
        "code_1": "SSYK1",
    }

    daioe_all_levels = pl.concat(
        [
            aggregate_daioe_level(daioe_scb, col, label)
            for col, label in levels_map.items()
        ],
    ).sort(["level", "year", "ssyk_code"])

    # --- 7. Build 1-5 exposure level columns ---
    daioe_all_levels = build_exposure_levels(daioe_all_levels)

    # --- 8. Final merge: SCB changes + DAIOE exposure ---
    final = (
        scb_changes.join(
            daioe_all_levels,
            on=["year", "ssyk_code"],
            how="left",
        )
        .drop("level_right")
        .sort(SORT_KEY)
    )

    # --- Export ---
    final.sink_parquet(OUTPUT_PATH)
    print(f"Exported to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
