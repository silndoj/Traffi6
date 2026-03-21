"""
data_loader.py — Parse CSV sensor data and group by timestamp for replay.

Handles two lane-class serialization formats:
  List format:  [['car', 2], ['motorbike', 1]]
  Dict format:  [{'class': 'car', 'count': 2, 'subClass': None}]
"""

import re
from collections import defaultdict

import pandas as pd


# Regex patterns for safe parsing (no eval)
_LIST_PAIR_RE = re.compile(r"\['(\w[\w-]*)',\s*(\d+)\]")
_DICT_ENTRY_RE = re.compile(
    r"'class':\s*'(\w[\w-]*)'"       # vehicle class
    r".*?'count':\s*(\d+)"           # count
    r".*?'subClass':\s*(?:'(\w[\w-]*)'|None)"  # optional subClass
)


def _parse_lane_classes(raw: str) -> list[tuple[str, int]]:
    """Extract (vehicle_type, count) pairs from a lane classes string."""
    if not isinstance(raw, str) or raw.strip() in ("", "[]"):
        return []

    # Dict format: [{'class': 'car', 'count': 2, 'subClass': 'single-unit-truck'}]
    dict_matches = _DICT_ENTRY_RE.findall(raw)
    if dict_matches:
        results = []
        for cls, count, sub_class in dict_matches:
            vehicle_type = sub_class if sub_class else cls
            results.append((vehicle_type, int(count)))
        return results

    # List format: [['car', 2], ['motorbike', 1]]
    list_matches = _LIST_PAIR_RE.findall(raw)
    if list_matches:
        return [(cls, int(count)) for cls, count in list_matches]

    return []


def load_and_group(file_path: str) -> list[tuple[str, list[dict]]]:
    """
    Load CSV, parse lane classes, combine lane1+lane2, group by timestamp.

    Returns list of (timestamp_str, records) tuples sorted chronologically.
    Each record is a dict:
        {
            'sensor_id': str,
            'vehicles': [(vehicle_type: str, count: int), ...]
        }
    """
    df = pd.read_csv(file_path)

    grouped: dict[str, list[dict]] = defaultdict(list)

    for _, row in df.iterrows():
        ts = str(row["timestamp"])
        sensor_id = str(row["sensor_id"])

        lane1 = _parse_lane_classes(str(row.get("lane1.classes", "[]")))
        lane2 = _parse_lane_classes(str(row.get("lane2.classes", "[]")))
        vehicles = lane1 + lane2

        grouped[ts].append({"sensor_id": sensor_id, "vehicles": vehicles})

    steps = sorted(grouped.items(), key=lambda x: x[0])

    # Summary
    total_records = len(df)
    unique_sensors = df["sensor_id"].nunique()
    unique_ts = len(steps)
    time_range = f"{steps[0][0]}  →  {steps[-1][0]}" if steps else "N/A"
    print(f"Loaded {total_records:,} records | "
          f"{unique_sensors} sensors | "
          f"{unique_ts:,} timestamps | "
          f"Range: {time_range}")

    return steps


def compute_traffic_volumes(file_path: str) -> dict[str, int]:
    """
    Return {sensor_id: total_vehicle_count} across the entire dataset.
    Used by sensor_mapping.py to assign busier sensors to central positions.
    """
    df = pd.read_csv(file_path)

    volumes: dict[str, int] = defaultdict(int)

    for _, row in df.iterrows():
        sensor_id = str(row["sensor_id"])
        lane1 = _parse_lane_classes(str(row.get("lane1.classes", "[]")))
        lane2 = _parse_lane_classes(str(row.get("lane2.classes", "[]")))
        total = sum(c for _, c in lane1) + sum(c for _, c in lane2)
        volumes[sensor_id] += total

    return dict(volumes)
