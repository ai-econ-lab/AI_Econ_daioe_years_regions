# AI-SCB Year and Regions — `scb_pull` branch

First stage of the data pipeline: pulls raw employment statistics from
Statistics Sweden (SCB) and aggregates them across SSYK2012 occupation
levels. For the full four-branch pipeline and the final merged dataset,
see the `development` branch's README.

## What this branch does

1. `scripts/pull_merge.py` — fetches employment counts from SCB's
   statistics API (table group `AM0208`) via `pyscbwrapper`, for county-level
   regions, sex (men/women), 4-digit SSYK2012 occupations, and year. Three
   table-ID vintages are queried concurrently and combined, since SCB
   changed the table ID over time:

   | Table code | Years covered |
   |---|---|
   | `YREG60` | up to 2018 |
   | `YREG60N` | 2019–2021 |
   | `YREG60BAS` | 2020–2024 |

   Where years overlap between vintages, the more recent table's rows win
   (dedup on `code_4` × `county_code` × `sex` × `year`). National totals and
   unspecified-occupation rows are dropped. Output: `data/scb_yr_regions.parquet`.

2. `scripts/aggregate.py` — reads that parquet, derives SSYK2012 levels 1–3
   by slicing the 4-digit code, aggregates employment (`value`) to each
   level (SSYK1–SSYK4) by county/sex/year, and left-joins occupation names
   from `structure_ssyk12.csv`. Output:
   `data/processed/ssyk12_aggregated_ssyk4_to_ssyk1.parquet`.

`scb_yr_regions_14_to_24.ipynb` is the exploratory notebook this pipeline
was developed from; the scripts under `scripts/` are the maintained version.

## Automation

Workflow `01_scb_pull_to_daioe_pull.yml` runs both scripts daily
(00:00 UTC) and on push to `scb_pull`, then commits and pushes the
aggregated parquet to the `daioe_pull` branch, where it becomes an input to
the next pipeline stage.
