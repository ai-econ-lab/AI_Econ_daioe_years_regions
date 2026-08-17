# AI-SCB Year and Regions

AI occupational exposure (DAIOE) merged with Swedish employment data (SCB),
broken down by SSYK2012 occupation, county, sex and year, with county
coordinates attached for mapping.

This branch (`main`) holds **only the published dataset**. It is updated
automatically once a day by the project's data pipeline; there is no app
here at present. An app built on this data is under active development on
the project's `development` branch and will be published here once it's
ready.

## Data sources

### Employment counts — Statistics Sweden (SCB)

Pulled from SCB's statistics database (table group `AM0208`, occupational
statistics). Three vintages of the underlying SCB table are combined
because SCB revised its table ID over time:

| Table code | Years covered |
|---|---|
| `YREG60` | up to 2018 |
| `YREG60N` | 2019–2021 |
| `YREG60BAS` | 2020–2024 |

Where vintages overlap, rows from the more recent table win (dedup on
`code_4` × `county_code` × `sex` × `year`). Each row is an employment count
for a 4-digit SSYK2012 occupation, county, sex (men/women) and year;
national totals and unspecified-occupation rows are dropped. County-level
(not municipality) regions only.

### AI exposure scores — DAIOE

Sourced from
[`joseph-data/07_translate_ssyk`](https://github.com/joseph-data/07_translate_ssyk),
which translates occupational AI-exposure scores onto SSYK2012 4-digit
codes. Scores are provided per year and per AI application/benchmark domain
(columns prefixed `daioe_`):

`allapps` (combined), `stratgames` (strategic games), `videogames`,
`imgrec` (image recognition), `imgcompr` (image comprehension), `imggen`
(image generation), `readcompr` (reading comprehension), `lngmod`
(language modelling), `translat` (translation), `speechrec` (speech
recognition), `genai` (generative AI).

The DAIOE source only covers a limited span of years; the pipeline extends
the series forward to match the latest SCB year by repeating the last known
year's occupation-level scores unchanged (scores are frozen at their most
recent value, not forecast).

### County coordinates

One point per Swedish county (SCB län code `01`–`25`, 21 counties) at that
county's administrative-capital city centre — **not** a computed area
centroid. County/capital mappings come from
[SCB, Counties and municipalities in Sweden](https://www.scb.se/en/finding-statistics/regional-statistics-and-maps/regional-divisions/counties-and-municipalities/),
cross-checked against Wikipedia's "Counties of Sweden"; coordinates were
compiled from commonly published city-centre coordinates (e.g. Wikipedia,
[geodatos.net](https://www.geodatos.net/en/coordinates/sweden)), spot-checked
August 2026. This is intentionally approximate and suitable for map
markers, not survey-grade geodata.

## How the dataset is built

1. Employment counts are pulled from SCB and aggregated across SSYK2012
   levels 1–4 (national, occupation-level counts used as weights).
2. 1/3/5-year employment changes are computed per occupation/county/sex
   group.
3. DAIOE exposure scores are joined onto SSYK2012 occupations, then
   aggregated to each SSYK level as both a simple mean and an
   employment-weighted mean, with within-year percentile ranks and 1–5
   exposure-level buckets (quintiles) derived from those ranks.
4. County coordinates are left-joined on by `county_code`.

The full pipeline (four upstream branches, one script per stage) is
documented on the project's `development` branch.

## Dataset schema

`data/daioe_scb_years_all_levels_geo.parquet` — 292,446 rows × 72 columns,
years 2014–2024, 21 counties, sex = men/women, `level` ∈
{SSYK1, SSYK2, SSYK3, SSYK4}.

| Column group | Columns | Notes |
|---|---|---|
| Identifiers | `level`, `ssyk_code`, `occupation`, `county_code`, `county`, `sex`, `year` | `ssyk_code` length matches `level` (1–4 digits) |
| Employment | `emp_count`, `chg_1y`/`chg_3y`/`chg_5y`, `pct_chg_1y`/`pct_chg_3y`/`pct_chg_5y`, `weight_sum` | `weight_sum` is a national SSYK4 total, repeated per SSYK code — not county-specific |
| DAIOE (per domain, 11 domains) | `daioe_<domain>_avg`, `daioe_<domain>_wavg` | Simple mean vs. employment-weighted mean across the level's constituent SSYK4 codes |
| DAIOE percentiles | `pctl_daioe_<domain>_avg`, `pctl_daioe_<domain>_wavg` | 0–100, within `year` × `level` |
| DAIOE exposure buckets | `daioe_<domain>_Level_Exposure` | 1 (least exposed) – 5 (most exposed), quintiles of the weighted percentile |
| Geography | `county_lat`, `county_lon` | See county-coordinates caveat above |

Note: some upstream DAIOE rows carry a literal float `NaN` rather than a
proper null; coerce `NaN → null` before aggregating, or weighted averages
will silently propagate `NaN`.

## Repository layout on this branch

```
data/daioe_scb_years_all_levels_geo.parquet   The dataset (only file kept in sync)
```
