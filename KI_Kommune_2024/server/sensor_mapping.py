"""Assign traffic sensors to real Karlsruhe road intersections.

Extracts intersection coordinates from the Folium-generated map.html,
distributes sensors evenly across the road network, and assigns the
busiest sensors to the most central positions.
"""

import json
import math
import os
import re


CENTER_LAT = 49.00587
CENTER_LON = 8.40162

_COORD_RE = re.compile(r"L\.circleMarker\(\s*\n\s*\[([0-9.]+),\s*([0-9.]+)\]")


def _extract_coordinates(map_html_path: str) -> list[tuple[float, float]]:
    with open(map_html_path, "r") as f:
        html = f.read()
    return [
        (float(m.group(1)), float(m.group(2)))
        for m in _COORD_RE.finditer(html)
    ]


def _distance_to_center(coord: tuple[float, float]) -> float:
    return math.hypot(coord[0] - CENTER_LAT, coord[1] - CENTER_LON)


def load_or_create_mapping(
    sensor_ids: list[str],
    traffic_volumes: dict[str, int],
    map_html_path: str = "map.html",
    output_path: str = "sensor_positions.json",
) -> dict[str, tuple[float, float]]:
    """Load an existing sensor-to-coordinate mapping, or create one.

    If *output_path* exists the persisted mapping is returned immediately.
    Otherwise coordinates are extracted from *map_html_path*, a well-
    distributed subset is selected, and the busiest sensors (by
    *traffic_volumes*) are assigned to the most central intersections.
    """
    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            raw = json.load(f)
        return {k: tuple(v) for k, v in raw.items()}

    coords = _extract_coordinates(map_html_path)
    coords.sort(key=_distance_to_center)

    n = len(sensor_ids)
    step = len(coords) / n
    selected = [coords[int(i * step)] for i in range(n)]

    sorted_ids = sorted(sensor_ids, key=lambda s: traffic_volumes.get(s, 0), reverse=True)

    mapping = {sid: selected[i] for i, sid in enumerate(sorted_ids)}

    with open(output_path, "w") as f:
        json.dump(mapping, f, indent=2)

    return mapping
