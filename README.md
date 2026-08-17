# AI-SCB Year and Regions — `daioe_pull` branch

Second stage of the data pipeline: merges AI occupational exposure scores
(DAIOE) with the SCB employment data aggregated on `scb_pull`, across
SSYK2012 levels, county, sex, and year. For the full four-branch pipeline
and the final merged dataset, see the `development` branch's README.

## What this branch does

`main.py` performs the merge:

1. Loads DAIOE scores from
   [`joseph-data/07_translate_ssyk`](https://github.com/joseph-data/07_translate_ssyk)
   (`daioe_ssyk2012_translated.csv`) and this branch's own
   `data/processed/ssyk12_aggregated_ssyk4_to_ssyk1.parquet` (committed here
   by `scb_pull`'s workflow) lazily.
2. Computes 1/3/5-year employment changes per occupation/county/sex group.
3. Derives SSYK2012 hierarchy codes (`code_1`…`code_4`) from the 4-digit
   DAIOE occupation code, filtered to 2014 onward (first year of SSYK2012
   publication).
4. Extends the DAIOE series forward to match SCB's latest year by repeating
   the last known year's occupation-level scores unchanged (frozen, not
   forecast) — DAIOE's own coverage lags SCB's.
5. Joins DAIOE to SCB SSYK4 employment counts, used as aggregation weights.
6. Aggregates DAIOE metrics (11 AI-application domains, e.g. `imgrec`,
   `translat`, `genai` — see `development`'s README for the full list) to
   all four SSYK2012 levels, each with a simple mean and an
   employment-weighted mean, plus within-year percentile ranks.
7. Converts weighted percentile ranks into 1–5 exposure-level buckets
   (quintiles) per metric.
8. Left-joins onto SCB's employment-change table and exports
   `data/daioe_scb_years_all_levels.parquet`.

`ssyk2012_daioe_yr_regions.ipynb` is the exploratory notebook this pipeline
was developed from; `main.py` is the maintained version.

## Automation

Workflow `02_daioe_pull_to_development.yml` runs `main.py` daily
(00:00 UTC) and on push to `daioe_pull`, then commits and pushes the merged
parquet to the `development` branch, where it's joined with county
coordinates (from `geo_pull`) to produce the final dataset.
