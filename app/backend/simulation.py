"""
simulation.py — Data-driven traffic simulation on real Karlsruhe road network.

Vehicles drive along real OSMnx road edges with interpolated positions.
Sensor readings control spawn/despawn to match actual traffic counts.
"""

import math
import os
import pickle
import random
from collections import defaultdict

import osmnx as ox

# Karlsruhe city center
CENTER_LAT = 49.00587
CENTER_LON = 8.40162
RADIUS_M = 3000

# Meters per degree at Karlsruhe's latitude
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = 73_000.0

# Speed in meters/second by vehicle type (frontend names)
SPEED_MAP = {
    "car": 12.0,
    "truck": 8.0,
    "bicycle": 4.0,
    "motor_bike": 14.0,
    "foot": 1.5,
}

# Map CSV vehicle types → frontend vehicle types
VEHICLE_TYPE_MAP = {
    "car": "car",
    "motorbike": "motor_bike",
    "truck": "truck",
    "single-unit-truck": "truck",
    "articulated-truck": "truck",
    "car-with-trailer": "car",
    "bicycle": "bicycle",
}


def _latlon_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in meters between two lat/lon points."""
    dy = (lat2 - lat1) * M_PER_DEG_LAT
    dx = (lon2 - lon1) * M_PER_DEG_LON
    return math.hypot(dx, dy)


class RoadNetwork:
    """Real road graph from OSMnx, cached to disk."""

    def __init__(self, cache_path: str = "road_graph.pkl"):
        self.nodes: dict[int, tuple[float, float]] = {}    # {osm_id: (lat, lon)}
        self.edges: dict[int, list[int]] = defaultdict(list)  # adjacency list
        self._weights: dict[int, float] = {}                # center-proximity weights

        if os.path.exists(cache_path):
            print(f"Loading cached road graph from {cache_path}...")
            with open(cache_path, "rb") as f:
                cached = pickle.load(f)
            self.nodes = cached["nodes"]
            self.edges = cached["edges"]
        else:
            print(f"Downloading Karlsruhe road graph (radius={RADIUS_M}m)...")
            G = ox.graph_from_point(
                (CENTER_LAT, CENTER_LON), dist=RADIUS_M, network_type="drive"
            )
            for node_id, data in G.nodes(data=True):
                self.nodes[node_id] = (data["y"], data["x"])  # (lat, lon)
            for u, v, _data in G.edges(data=True):
                if v not in self.edges[u]:
                    self.edges[u].append(v)
                if u not in self.edges[v]:
                    self.edges[v].append(u)
            with open(cache_path, "wb") as f:
                pickle.dump({"nodes": self.nodes, "edges": dict(self.edges)}, f)
            print(f"Cached graph to {cache_path}")

        self._compute_weights()
        print(f"Road network ready: {len(self.nodes)} nodes, "
              f"{sum(len(v) for v in self.edges.values()) // 2} edges")

    def _compute_weights(self) -> None:
        """Weight nodes by proximity to center (closer = higher weight)."""
        max_dist = 0.0
        dists: dict[int, float] = {}
        for nid, (lat, lon) in self.nodes.items():
            d = _latlon_distance_m(CENTER_LAT, CENTER_LON, lat, lon)
            dists[nid] = d
            if d > max_dist:
                max_dist = d
        for nid, d in dists.items():
            norm = d / max_dist if max_dist > 0 else 0
            self._weights[nid] = 1.0 + 2.0 * (1.0 - norm)  # 3 at center, 1 at edge

    def nearest_node(self, lat: float, lon: float) -> int:
        """Find the closest graph node to a GPS position."""
        best_id = -1
        best_dist = float("inf")
        for nid, (nlat, nlon) in self.nodes.items():
            d = _latlon_distance_m(lat, lon, nlat, nlon)
            if d < best_dist:
                best_dist = d
                best_id = nid
        return best_id

    def neighbors_of(self, node_id: int) -> list[int]:
        return self.edges.get(node_id, [])

    def weight_of(self, node_id: int) -> float:
        return self._weights.get(node_id, 1.0)

    def position_of(self, node_id: int) -> tuple[float, float]:
        return self.nodes[node_id]

    def edge_length_m(self, from_id: int, to_id: int) -> float:
        """Distance in meters along the edge between two adjacent nodes."""
        lat1, lon1 = self.nodes[from_id]
        lat2, lon2 = self.nodes[to_id]
        return _latlon_distance_m(lat1, lon1, lat2, lon2)


class Vehicle:
    """A traffic entity that moves along road graph edges."""

    def __init__(
        self,
        vid: int,
        vehicle_type: str,
        road_network: RoadNetwork,
        start_node: int,
    ):
        self.id = vid
        self.vehicle_type = vehicle_type
        self.speed = SPEED_MAP.get(vehicle_type, 10.0)
        self._net = road_network

        lat, lon = road_network.position_of(start_node)
        self.x = lat
        self.y = lon

        self.current_node = start_node
        self.target_node = start_node
        self.progress = 0.0          # 0..1 along current edge
        self._edge_length = 0.0      # meters

        self._pick_next_target()

    def _pick_next_target(self) -> None:
        """Choose a random neighbor weighted toward city center."""
        neighbors = self._net.neighbors_of(self.target_node)
        if not neighbors:
            return
        # Filter out the node we just came from to avoid immediate backtrack
        candidates = [n for n in neighbors if n != self.current_node]
        if not candidates:
            candidates = neighbors

        weights = [self._net.weight_of(n) for n in candidates]
        self.current_node = self.target_node
        self.target_node = random.choices(candidates, weights=weights, k=1)[0]
        self.progress = 0.0
        self._edge_length = self._net.edge_length_m(self.current_node, self.target_node)

    def move(self, dt: float) -> None:
        """Advance along current edge by dt seconds."""
        if self._edge_length <= 0:
            self._pick_next_target()
            if self._edge_length <= 0:
                return  # isolated node, nowhere to go

        distance_moved = self.speed * dt
        self.progress += distance_moved / self._edge_length

        # May overshoot multiple edges in one large dt
        while self.progress >= 1.0:
            self.progress -= 1.0
            self._pick_next_target()
            if self._edge_length <= 0:
                self.progress = 0.0
                break

        # Interpolate position between current and target nodes
        lat1, lon1 = self._net.position_of(self.current_node)
        lat2, lon2 = self._net.position_of(self.target_node)
        self.x = lat1 + (lat2 - lat1) * self.progress
        self.y = lon1 + (lon2 - lon1) * self.progress


class TrafficSimulation:
    """Data-driven simulation: sensor readings control vehicle counts."""

    def __init__(self, sensor_positions: dict[str, tuple[float, float]]):
        self.road_network = RoadNetwork()
        self._next_id = 0
        self._vehicles: dict[int, Vehicle] = {}

        # Map each sensor to its nearest road node
        self._sensor_nodes: dict[str, int] = {}
        for sensor_id, (lat, lon) in sensor_positions.items():
            self._sensor_nodes[sensor_id] = self.road_network.nearest_node(lat, lon)

        # Track which vehicles belong to which sensor+type bucket
        self._bucket: dict[tuple[str, str], list[int]] = defaultdict(list)

    def _spawn(self, sensor_id: str, vehicle_type: str) -> Vehicle:
        """Spawn one vehicle at the sensor's nearest node."""
        vid = self._next_id
        self._next_id += 1
        node = self._sensor_nodes[sensor_id]
        v = Vehicle(vid, vehicle_type, self.road_network, node)
        self._vehicles[vid] = v
        self._bucket[(sensor_id, vehicle_type)].append(vid)
        return v

    def _despawn(self, sensor_id: str, vehicle_type: str, count: int) -> None:
        """Remove `count` vehicles from a bucket, farthest from sensor first."""
        key = (sensor_id, vehicle_type)
        bucket = self._bucket[key]
        if not bucket or count <= 0:
            return

        sensor_node = self._sensor_nodes[sensor_id]
        slat, slon = self.road_network.position_of(sensor_node)

        # Sort by distance from sensor, descending — remove farthest first
        def dist_from_sensor(vid: int) -> float:
            v = self._vehicles.get(vid)
            if v is None:
                return -1.0
            return _latlon_distance_m(slat, slon, v.x, v.y)

        bucket.sort(key=dist_from_sensor, reverse=True)

        removed = 0
        new_bucket = []
        for vid in bucket:
            if removed < count and vid in self._vehicles:
                del self._vehicles[vid]
                removed += 1
            else:
                new_bucket.append(vid)
        self._bucket[key] = new_bucket

    def update_from_data(
        self, readings: dict[str, list[tuple[str, int]]]
    ) -> None:
        """
        Adjust active vehicles to match sensor readings.

        readings: {sensor_id: [(csv_vehicle_type, count), ...]}
        """
        # Build desired counts per (sensor, mapped_type)
        desired: dict[tuple[str, str], int] = defaultdict(int)
        for sensor_id, pairs in readings.items():
            if sensor_id not in self._sensor_nodes:
                continue
            for raw_type, count in pairs:
                mapped = VEHICLE_TYPE_MAP.get(raw_type, raw_type)
                desired[(sensor_id, mapped)] += count

        # All sensor+type buckets we need to consider
        all_keys = set(desired.keys()) | set(self._bucket.keys())

        for key in all_keys:
            want = desired.get(key, 0)
            # Clean stale IDs from bucket
            self._bucket[key] = [
                vid for vid in self._bucket[key] if vid in self._vehicles
            ]
            have = len(self._bucket[key])
            sensor_id, vehicle_type = key

            if have < want:
                for _ in range(want - have):
                    self._spawn(sensor_id, vehicle_type)
            elif have > want:
                self._despawn(sensor_id, vehicle_type, have - want)

    def tick(self, dt: float) -> None:
        """Advance all vehicles by dt seconds."""
        for v in self._vehicles.values():
            v.move(dt)

    def get_positions(self) -> list[dict]:
        """Return positions in the format the frontend expects."""
        return [
            {"X": v.x, "Y": v.y, "TYPE": v.vehicle_type, "ID": v.id}
            for v in self._vehicles.values()
        ]
