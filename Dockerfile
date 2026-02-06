# SkyWeb Backend - Cloud Run Container
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for SpatiaLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-mod-spatialite \
    libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY core/ ./core/
COPY data/ ./data/

# Install Python dependencies (api + gcp + llm extras)
RUN pip install --no-cache-dir ".[api,gcp,llm]"

# Cloud Run uses PORT env variable
ENV PORT=8000

EXPOSE 8000

# Run uvicorn with Cloud Run conventions
CMD exec uvicorn core.api.app:app --host 0.0.0.0 --port $PORT
