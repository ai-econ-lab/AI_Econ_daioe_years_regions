"""Minimal map check that county_lat/county_lon joined correctly onto the DAIOE dataset."""

import json
from pathlib import Path

import polars as pl
from shiny.express import ui

APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / "data" / "daioe_scb_years_all_levels_geo.parquet"

DATA = pl.read_parquet(DATA_PATH)
LATEST_YEAR = DATA.get_column("year").max()

county_points = (
    DATA.filter((pl.col("level") == "SSYK1") & (pl.col("year") == LATEST_YEAR))
    # Some upstream DAIOE rows carry literal float NaN rather than null.
    .with_columns(pl.col("daioe_allapps_wavg").fill_nan(None))
    .group_by(["county_code", "county", "county_lat", "county_lon"])
    .agg(
        # Weighted by county-level employment (not weight_sum, which is a
        # national total repeated per ssyk_code and wouldn't vary by county).
        (
            (pl.col("daioe_allapps_wavg") * pl.col("emp_count")).sum()
            / pl.when(pl.col("daioe_allapps_wavg").is_not_null())
            .then(pl.col("emp_count"))
            .otherwise(None)
            .sum()
        ).alias("avg_exposure"),
        pl.col("emp_count").sum().alias("total_employment"),
    )
    .sort("county_code")
)

MARKERS = [
    {
        "county": row["county"],
        "lat": row["county_lat"],
        "lon": row["county_lon"],
        "exposure": row["avg_exposure"],
        "employment": row["total_employment"],
    }
    for row in county_points.iter_rows(named=True)
]

ui.page_opts(title="Geodata check")

ui.tags.link(
    rel="stylesheet",
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
)
ui.tags.script(src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js")

ui.tags.p(
    f"{len(MARKERS)} counties, year {LATEST_YEAR}. "
    "Marker radius/colour scale with AI-exposure score (data/daioe_scb_years_all_levels_geo.parquet).",
)
ui.tags.div(id="map", style="height: 600px; border-radius: 8px;")

ui.tags.script(
    f"""
    const markers = {json.dumps(MARKERS)};
    const map = L.map("map").setView([62.5, 15.5], 4.3);
    L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      attribution: "&copy; OpenStreetMap contributors",
    }}).addTo(map);

    const exposures = markers.map((m) => m.exposure).filter((v) => v !== null);
    const minExp = Math.min(...exposures);
    const maxExp = Math.max(...exposures);

    function colorFor(exposure) {{
      if (exposure === null) return "#999999";
      const t = (exposure - minExp) / (maxExp - minExp || 1);
      const hue = 220 - t * 220; // blue (low) -> red (high)
      return `hsl(${{hue}}, 80%, 45%)`;
    }}

    markers.forEach((m) => {{
      L.circleMarker([m.lat, m.lon], {{
        radius: 8 + Math.sqrt(m.employment) / 40,
        color: colorFor(m.exposure),
        fillColor: colorFor(m.exposure),
        fillOpacity: 0.7,
      }})
        .bindPopup(
          `<b>${{m.county}}</b><br/>` +
          `AI exposure (weighted avg): ${{m.exposure !== null ? m.exposure.toFixed(2) : "n/a"}}<br/>` +
          `Employment: ${{m.employment.toLocaleString()}}<br/>` +
          `Coords: ${{m.lat.toFixed(4)}}, ${{m.lon.toFixed(4)}}`,
        )
        .addTo(map);
    }});
    """,
)
