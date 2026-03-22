FROM python:3.12-slim

WORKDIR /app

# Install system deps for osmnx/geopandas
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything
COPY backend/ backend/
COPY frontend/ frontend/
COPY data/ data/

# Copy cached road graph + sensor positions (skip OSMnx download)
COPY backend/road_graph.pkl backend/road_graph.pkl
COPY backend/sensor_positions.json backend/sensor_positions.json

EXPOSE 8000

WORKDIR /app/backend
CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
