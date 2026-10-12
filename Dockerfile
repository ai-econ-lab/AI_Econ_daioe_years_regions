# ------------------------------- Builder stage ------------------------------ #
FROM python:3.14-bookworm AS builder

# Same uv minor version as the lockfile and the uv_build pin in pyproject.toml.
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependencies first, so editing the code does not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Then the project itself. The install is editable on purpose: config.PATHS finds
# the data folder relative to the source tree, so src must stay at /app/src.
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ------------------------------ Production stage ---------------------------- #
FROM python:3.14-slim-bookworm AS production

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Only what the app reads at runtime: the one dataset file and the boundaries,
# not the pipeline intermediates that may sit in data/ locally.
COPY src ./src
COPY app.py _brand.yml ./
COPY logos ./logos
COPY data/daioe_scb_years_all_levels_geo.parquet data/sweden_counties.geojson ./data/

# Hugging Face Spaces route traffic to port 7860.
EXPOSE 7860
CMD ["shiny", "run", "app.py", "--host", "0.0.0.0", "--port", "7860"]
