"""SQLite database for traffic sensor data."""

import sqlite3
import os
import re
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'traffic.db')

_LIST_PAIR_RE = re.compile(r"\['(\w[\w-]*)',\s*(\d+)\]")
_DICT_ENTRY_RE = re.compile(
    r"'class':\s*'(\w[\w-]*)'"
    r".*?'count':\s*(\d+)"
    r".*?'subClass':\s*(?:'(\w[\w-]*)'|None)"
)


def _parse_lane_classes(raw):
    if not isinstance(raw, str) or raw.strip() in ("", "[]"):
        return []
    dict_matches = _DICT_ENTRY_RE.findall(raw)
    if dict_matches:
        return [(sub or cls, int(count)) for cls, count, sub in dict_matches]
    list_matches = _LIST_PAIR_RE.findall(raw)
    if list_matches:
        return [(cls, int(count)) for cls, count in list_matches]
    return []


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sensors (
            sensor_id TEXT PRIMARY KEY,
            lat REAL,
            lon REAL,
            total_volume INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            count INTEGER NOT NULL,
            FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
        );

        CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp);
        CREATE INDEX IF NOT EXISTS idx_readings_sensor ON readings(sensor_id);
    """)
    conn.commit()
    conn.close()


def import_csv(csv_path):
    """Import data.csv into the database. Skips if data already exists."""
    import pandas as pd

    conn = get_connection()
    existing = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    if existing > 0:
        print(f"Database already has {existing:,} readings. Skipping import.")
        conn.close()
        return

    print(f"Importing {csv_path}...")
    df = pd.read_csv(csv_path)

    volumes = defaultdict(int)
    readings_batch = []

    for _, row in df.iterrows():
        sensor_id = str(row["sensor_id"])
        ts = str(row["timestamp"])
        lane1 = _parse_lane_classes(str(row.get("lane1.classes", "[]")))
        lane2 = _parse_lane_classes(str(row.get("lane2.classes", "[]")))

        for vehicle_type, count in lane1 + lane2:
            readings_batch.append((sensor_id, ts, vehicle_type, count))
            volumes[sensor_id] += count

        if len(readings_batch) >= 10000:
            conn.executemany(
                "INSERT INTO readings (sensor_id, timestamp, vehicle_type, count) VALUES (?, ?, ?, ?)",
                readings_batch,
            )
            readings_batch.clear()

    if readings_batch:
        conn.executemany(
            "INSERT INTO readings (sensor_id, timestamp, vehicle_type, count) VALUES (?, ?, ?, ?)",
            readings_batch,
        )

    sensor_rows = [(sid, vol) for sid, vol in volumes.items()]
    conn.executemany(
        "INSERT OR IGNORE INTO sensors (sensor_id, total_volume) VALUES (?, ?)",
        sensor_rows,
    )

    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    sensors = conn.execute("SELECT COUNT(*) FROM sensors").fetchone()[0]
    timestamps = conn.execute("SELECT COUNT(DISTINCT timestamp) FROM readings").fetchone()[0]
    print(f"Imported {total:,} readings | {sensors} sensors | {timestamps:,} timestamps")
    conn.close()


def get_timestamps():
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT timestamp FROM readings ORDER BY timestamp"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_readings_at(timestamp):
    conn = get_connection()
    rows = conn.execute(
        "SELECT sensor_id, vehicle_type, count FROM readings WHERE timestamp = ?",
        (timestamp,),
    ).fetchall()
    conn.close()

    by_sensor = defaultdict(list)
    for r in rows:
        by_sensor[r["sensor_id"]].append((r["vehicle_type"], r["count"]))
    return dict(by_sensor)


def get_sensor_volumes():
    conn = get_connection()
    rows = conn.execute("SELECT sensor_id, total_volume FROM sensors").fetchall()
    conn.close()
    return {r["sensor_id"]: r["total_volume"] for r in rows}


def get_stats():
    conn = get_connection()
    total = conn.execute("SELECT SUM(count) FROM readings").fetchone()[0]
    by_type = conn.execute(
        "SELECT vehicle_type, SUM(count) as total FROM readings GROUP BY vehicle_type ORDER BY total DESC"
    ).fetchall()
    conn.close()
    return {
        "total_vehicles": total,
        "by_type": {r["vehicle_type"]: r["total"] for r in by_type},
    }


def update_sensor_positions(mapping):
    """Update sensors table with GPS coordinates."""
    conn = get_connection()
    for sensor_id, (lat, lon) in mapping.items():
        conn.execute(
            "UPDATE sensors SET lat = ?, lon = ? WHERE sensor_id = ?",
            (lat, lon, sensor_id),
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    csv_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data.csv')
    import_csv(csv_path)
    print("Stats:", get_stats())
