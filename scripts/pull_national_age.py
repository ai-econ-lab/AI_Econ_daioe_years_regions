"""
pull_national_age.py.
----------------------
Pulls national-level SCB employment broken down by occupation, age and
sex (no region), for Magnus's item 5: SCB only crosses age with occupation
at 4-digit SSYK nationally, never at region, so this is a separate cut
from `pull_merge.py`'s regional (county x sex, no age) table.

Source: AM0208E / YREG51 family, which crosses occupation(4-digit) x age
x sex x year with an extra "level of education" dimension (8 categories,
including an unknown/"US" bucket, so no workers are lost). Querying every
dimension in one request (~344k cells) fails: the SCB API returns an empty
body. Fetching one education-level value at a time (~43k cells) works, so
each vintage is fetched as 8 chunks and the education dimension is summed
away afterward to recover a pure occupation x age x sex x year total.
"""

import concurrent.futures
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from pyscbwrapper import SCB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)

ROOT = Path.cwd().resolve()
DATA_DIR = ROOT / "data"
OUTPUT_PATH = DATA_DIR / "scb_national_age.parquet"
DEDUP_KEYS = ["code_4", "age", "sex", "year"]
SORT_KEY = ["code_4", "age", "sex", "year"]


# =========================== Config Table ================================ #


@dataclass(frozen=True)
class TableSpec:
    """Identifiers and dedup priority for a single SCB table vintage."""

    name: str
    ids: tuple[str, str, str, str, str]
    priority: int  # higher = more recent; wins on overlapping years


TABLE_SPECS = (
    TableSpec("nat_age_14_to_18", ("en", "AM", "AM0208", "AM0208E", "YREG51"), 1),
    TableSpec("nat_age_19_to_21", ("en", "AM", "AM0208", "AM0208E", "YREG51N"), 2),
    TableSpec("nat_age_20_to_24", ("en", "AM", "AM0208", "AM0208E", "YREG51BAS"), 3),
)


# ========================= Variable Helpers ================================ #


def find_variable(variables: list[dict], keyword: str) -> dict:
    keyword_lower = keyword.lower()
    for variable in variables:
        if keyword_lower in variable.get("text", "").lower():
            return variable
    available = [v.get("text") for v in variables]
    msg = f"No variable found containing {keyword!r}. Available: {available}"
    raise ValueError(msg)


def to_query_key(text: str) -> str:
    """Strip whitespace from a variable text to match pyscbwrapper's query key format."""
    return text.replace(" ", "")


def build_lookup(variable: dict) -> dict[str, str]:
    """Map SCB codes to their human-readable labels for a given variable."""
    return dict(zip(variable["values"], variable["valueTexts"], strict=True))


def build_key_positions(
    variables: list[dict],
    observations_code: str,
) -> dict[str, int]:
    keyword_map = {
        "occupation": "occupation",
        "education": "education",
        "sex": "sex",
        "year": "year",
    }
    positions: dict[str, int] = {}
    key_index = 0

    for variable in variables:
        if variable["code"] == observations_code:
            continue
        text = variable.get("text", "").lower()
        if variable["code"] == "Alder":
            positions["age"] = key_index
            key_index += 1
            continue
        for keyword, field in keyword_map.items():
            if keyword in text:
                positions[field] = key_index
                break
        key_index += 1

    missing = {"occupation", "education", "age", "sex", "year"} - positions.keys()
    if missing:
        msg = f"Missing key positions for: {', '.join(sorted(missing))}"
        raise ValueError(msg)

    return positions


# ======================= SCB Fetch (chunked by education level) ========== #


def fetch_with_retries(fn, *, retries: int = 3, label: str):
    """Call fn() with retries on empty/malformed SCB API responses."""
    result = None
    for attempt in range(1, retries + 1):
        try:
            result = fn()
        except Exception:  # noqa: BLE001 - the SCB client raises on malformed bodies
            result = None
        if result:
            return result
        log.warning(
            "%s: empty response (attempt %d/%d), retrying", label, attempt, retries
        )
        time.sleep(attempt * 2)

    msg = f"{label}: empty response after {retries} attempts"
    raise RuntimeError(msg)


def fetch_chunk(
    spec: TableSpec,
    variables: list[dict],
    education_value: str,
) -> pl.DataFrame:
    """
    Fetch one education-level chunk of a single SCB table vintage.

    Querying every dimension at once exceeds the SCB API's cell limit (an
    empty response body); one education value at a time (~43k cells) works.
    Retries on transient empty responses, which show up under concurrent
    load even when the same request succeeds in isolation. `variables` is
    the table's metadata, fetched once per vintage by the caller and reused
    across all 8 chunks rather than re-fetched per chunk.
    """
    scb = SCB(*spec.ids)

    occupation_var = find_variable(variables, "occupation")
    education_var = find_variable(variables, "education")
    age_var = next(v for v in variables if v["code"] == "Alder")
    sex_var = find_variable(variables, "sex")
    observations_var = find_variable(variables, "observations")

    scb.set_query(
        **{
            to_query_key(occupation_var["text"]): occupation_var["valueTexts"],
            to_query_key(education_var["text"]): [education_value],
            to_query_key(age_var["text"]): age_var["valueTexts"],
            to_query_key(sex_var["text"]): sex_var["valueTexts"][:2],
            to_query_key(observations_var["text"]): observations_var["valueTexts"][0],
        },
    )

    raw_rows = fetch_with_retries(
        lambda: scb.get_data().get("data"),
        label=f"{spec.name} / {education_value}",
    )

    positions = build_key_positions(variables, observations_var["code"])

    return (
        pl.DataFrame(raw_rows)
        .with_columns(
            code_4=pl.col("key").list.get(positions["occupation"]),
            age=pl.col("key").list.get(positions["age"]),
            sex_code=pl.col("key").list.get(positions["sex"]),
            year=pl.col("key").list.get(positions["year"]),
            value=pl.col("values")
            .list.get(0)
            .cast(pl.Int64, strict=False),  # ".." → null
        )
        .with_columns(
            occupation=pl.col("code_4").replace(build_lookup(occupation_var)),
            sex=pl.col("sex_code").replace(build_lookup(sex_var)),
        )
        # drop aggregate codes (total and unspecified occupations)
        .filter(~pl.col("code_4").is_in(["0002", "0000"]))
        .select(["code_4", "occupation", "age", "sex", "year", "value"])
    )


def fetch_table(spec: TableSpec) -> pl.DataFrame:
    """
    Fetch a full table vintage by chunking over education-level values and
    summing that dimension away, recovering occupation x age x sex x year
    totals. Appends _source_table and _priority for later deduplication.

    Chunks are fetched sequentially, not concurrently: this pull already
    runs one vintage per thread (see fetch_all_tables), and stacking
    per-chunk concurrency on top of that caused transient empty responses
    from the SCB API under the combined load.
    """
    log.info("Fetching %s", spec.name)
    probe = SCB(*spec.ids)
    variables = fetch_with_retries(
        lambda: probe.info().get("variables"),
        label=f"{spec.name} metadata",
    )
    education_var = find_variable(variables, "education")

    chunks = [fetch_chunk(spec, variables, edu) for edu in education_var["valueTexts"]]

    df = (
        pl.concat(chunks, how="vertical")
        .group_by(["code_4", "occupation", "age", "sex", "year"])
        .agg(pl.col("value").sum())
        .with_columns(
            _source_table=pl.lit(spec.name),
            _priority=pl.lit(spec.priority),
        )
    )

    log.info("%s: %d rows", spec.name, df.height)
    return df


def fetch_all_tables() -> dict[str, pl.DataFrame]:
    """Fetch all SCB table vintages concurrently and return keyed by name."""
    results: dict[str, pl.DataFrame] = {}

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(TABLE_SPECS),
    ) as executor:
        future_to_spec = {
            executor.submit(fetch_table, spec): spec for spec in TABLE_SPECS
        }
        for future in concurrent.futures.as_completed(future_to_spec):
            spec = future_to_spec[future]
            try:
                results[spec.name] = future.result()
            except Exception:
                log.exception("%s — failed", spec.name)
                raise

    return results


# ======================= Overlap Diagnostics ================================ #


def collect_year_overlaps(results: dict[str, pl.DataFrame]) -> list[str]:
    """Return human-readable strings describing year overlaps between table pairs."""
    years_by_table = {
        spec.name: set(results[spec.name]["year"].unique().to_list())
        for spec in TABLE_SPECS
    }
    overlaps = []
    for i, left in enumerate(TABLE_SPECS):
        for right in TABLE_SPECS[i + 1 :]:
            shared = sorted(years_by_table[left.name] & years_by_table[right.name])
            if shared:
                overlaps.append(f"{left.name} vs {right.name}: {', '.join(shared)}")
    return overlaps


# ======================= Merge & Deduplicate ================================ #


def combine_tables(results: dict[str, pl.DataFrame]) -> tuple[pl.DataFrame, int]:
    """
    Concatenate all table vintages and deduplicate on DEDUP_KEYS.

    Rows from higher-priority (more recent) vintages are kept when years
    overlap. Returns the cleaned DataFrame and the number of rows removed.
    """
    combined = pl.concat([results[spec.name] for spec in TABLE_SPECS], how="vertical")
    before = combined.height

    deduped = (
        combined.sort("_priority", descending=True)
        .unique(subset=DEDUP_KEYS, keep="first")
        .drop(["_source_table", "_priority"])
        .sort(SORT_KEY)
    )

    return deduped, before - deduped.height


# ======================= Entry Point ================================ #


def main() -> None:
    """Orchestrate fetch, merge, diagnostics, and save."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    results = fetch_all_tables()
    df, duplicate_count = combine_tables(results)

    for overlap in collect_year_overlaps(results):
        log.info("Year overlap: %s", overlap)

    log.info("Duplicate rows removed: %d", duplicate_count)
    log.info("Final shape: %s", df.shape)

    df.write_parquet(OUTPUT_PATH)
    log.info("Saved to %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()
