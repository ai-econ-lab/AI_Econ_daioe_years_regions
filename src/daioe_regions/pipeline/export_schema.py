"""Write the dataset schema as JSON, for publishing next to the parquet.

04_development_to_main.yml runs this after validation and uploads the result to
the dataset releases, so consumers get the same definition the gate enforces.

Usage:
    daioe-schema
    daioe-schema --output schema.json
"""

import argparse
import json
from pathlib import Path
from typing import Any

from daioe_regions.config import PATHS, VALIDATION
from daioe_regions.schema import COLUMNS


def build_document() -> dict[str, Any]:
    """Return the schema and dataset level rules as a JSON serialisable dict."""
    return {
        "dataset": PATHS.dataset.name,
        "rules": {
            "key": list(VALIDATION.key),
            "levels": sorted(VALIDATION.expected_levels),
            "counties": VALIDATION.expected_counties,
            "sexes": VALIDATION.expected_sexes,
        },
        "columns": [
            {
                "name": column.name,
                "dtype": str(column.dtype),
                "nullable": column.nullable,
                "minimum": column.minimum,
                "maximum": column.maximum,
                "description": column.description,
            }
            for column in COLUMNS
        ],
    }


def render() -> str:
    """Return the schema document as stable, indented JSON text."""
    return json.dumps(build_document(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    """Write the schema JSON to the chosen path."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=PATHS.data_dir / "schema.json",
        help="Where to write the schema JSON.",
    )
    args = parser.parse_args()
    args.output.write_text(render(), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
