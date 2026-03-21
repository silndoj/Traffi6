"""
simulation.py — Data-driven traffic simulation on real Karlsruhe road network.

Vehicles drive along real OSMnx road edges with interpolated positions.
Two layers of traffic:
  1. Base traffic — permanent fleet that makes the city look alive
  2. Sensor traffic — additional vehicles spawned/despawned based on real sensor data
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

# Map CSV vehicle types -> frontend vehicle types
VEHICLE_TYPE_MAP = {
    "car": "car",
    "motorbike": "motor_bike",
    "truck": "truck",
    "single-unit-truck": "truck",
    "articulated-truck": "truck",
    "car-with-trailer": "car",
    "bicycle": "bicycle",
}

# Base traffic composition (permanent vehicles — always on the roads)
BASE_TRAFFIC = [
    ("car", 280),
    ("truck", 30),
    ("motor_bike", 50),
    ("bicycle", 25),
    ("foot", 15),
]

# Sensor data amplification (sensors count vehicles passing per minute,
# but we want vehicles present in the area — multiply to fill the gaps)
SENSOR_AMPLIFIER = 3


def _latlon_distance_m(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * M_PER_DEG_LAT
    dx = (lon2 - lon1) * M_PER_DEG_LON
    return math.hypot(dx, dy)


class RoadNetwork:
    """Real road graph from OSMnx, cached to disk."""

    def __init__(self, cache_path="road_graph.pkl"):
        self.nodes = {}
        self.edges = defaultdict(list)
        self._weights = {}
        self._central_nodes = []

        # pickle is safe here — we only load files WE created from OSMnx data
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
                self.nodes[node_id] = (data["y"], data["x"])
            for u, v, _data in G.edges(data=True):
                if v not in self.edges[u]:
                    self.edges[u].append(v)
                if u not in self.edges[v]:
                    self.edges[v].append(u)
            with open(cache_path, "wb") as f:
                pickle.dump({"nodes": self.nodes, "edges": dict(self.edges)}, f)

        self._compute_weights()

        # Pre-compute lists of connected nodes (exclude dead ends and isolates)
        self._connected_nodes = [
            nid for nid in self.nodes if len(self.edges.get(nid, [])) >= 2
        ]
        # Central nodes (within 1.5km of center) for spawning base traffic
        self._central_nodes = [
            nid for nid in self._connected_nodes
            if _latlon_distance_m(CENTER_LAT, CENTER_LON, *self.nodes[nid]) < 1500
        ]
        if not self._central_nodes:
            self._central_nodes = self._connected_nodes

        print(f"Road network ready: {len(self.nodes)} nodes, "
              f"{sum(len(v) for v in self.edges.values()) // 2} edges, "
              f"{len(self._central_nodes)} central nodes")

    def _compute_weights(self):
        max_dist = 0.0
        dists = {}
        for nid, (lat, lon) in self.nodes.items():
            d = _latlon_distance_m(CENTER_LAT, CENTER_LON, lat, lon)
            dists[nid] = d
            if d > max_dist:
                max_dist = d
        for nid, d in dists.items():
            norm = d / max_dist if max_dist > 0 else 0
            self._weights[nid] = 1.0 + 2.0 * (1.0 - norm)

    def nearest_node(self, lat, lon):
        best_id = -1
        best_dist = float("inf")
        for nid, (nlat, nlon) in self.nodes.items():
            d = _latlon_distance_m(lat, lon, nlat, nlon)
            if d < best_dist:
                best_dist = d
                best_id = nid
        return best_id

    def random_connected_node(self):
        return random.choice(self._connected_nodes)

    def random_central_node(self):
        return random.choice(self._central_nodes)

    def neighbors_of(self, node_id):
        return self.edges.get(node_id, [])

    def weight_of(self, node_id):
        return self._weights.get(node_id, 1.0)

    def position_of(self, node_id):
        return self.nodes[node_id]

    def edge_length_m(self, from_id, to_id):
        lat1, lon1 = self.nodes[from_id]
        lat2, lon2 = self.nodes[to_id]
        return _latlon_distance_m(lat1, lon1, lat2, lon2)


class Vehicle:
    """A traffic entity that moves along road graph edges."""

    def __init__(self, vid, vehicle_type, road_network, start_node):
        self.id = vid
        self.vehicle_type = vehicle_type
        self.speed = SPEED_MAP.get(vehicle_type, 10.0)
        self._net = road_network

        lat, lon = road_network.position_of(start_node)
        self.x = lat
        self.y = lon

        self.current_node = start_node
        self.target_node = start_node
        self.progress = 0.0
        self._edge_length = 0.0

        self._pick_next_target()

    def _pick_next_target(self):
        neighbors = self._net.neighbors_of(self.target_node)
        if not neighbors:
            # Dead end — teleport to a random connected node to stay on roads
            new_node = self._net.random_connected_node()
            self.current_node = new_node
            self.target_node = new_node
            lat, lon = self._net.position_of(new_node)
            self.x = lat
            self.y = lon
            neighbors = self._net.neighbors_of(new_node)
            if not neighbors:
                return

        candidates = [n for n in neighbors if n != self.current_node]
        if not candidates:
            candidates = neighbors

        weights = [self._net.weight_of(n) for n in candidates]
        self.current_node = self.target_node
        self.target_node = random.choices(candidates, weights=weights, k=1)[0]
        self.progress = 0.0
        self._edge_length = self._net.edge_length_m(self.current_node, self.target_node)

    def move(self, dt):
        if self._edge_length <= 0:
            self._pick_next_target()
            if self._edge_length <= 0:
                return

        distance_moved = self.speed * dt
        self.progress += distance_moved / self._edge_length

        while self.progress >= 1.0:
            self.progress -= 1.0
            self._pick_next_target()
            if self._edge_length <= 0:
                self.progress = 0.0
                break

        lat1, lon1 = self._net.position_of(self.current_node)
        lat2, lon2 = self._net.position_of(self.target_node)
        self.x = lat1 + (lat2 - lat1) * self.progress
        self.y = lon1 + (lon2 - lon1) * self.progress


class TrafficSimulation:
    """Data-driven simulation with base traffic + sensor-modulated traffic."""

    def __init__(self, sensor_positions):
        self.road_network = RoadNetwork()
        self._next_id = 0
        self._vehicles = {}

        # Map each sensor to its nearest road node
        self._sensor_nodes = {}
        for sensor_id, (lat, lon) in sensor_positions.items():
            self._sensor_nodes[sensor_id] = self.road_network.nearest_node(lat, lon)

        # Sensor-driven vehicle tracking
        self._bucket = defaultdict(list)
        self._targets = defaultdict(int)
        self._max_change_per_tick = 5

        # Base traffic — permanent vehicles that make the city alive
        self._base_vehicle_ids = set()
        self._spawn_base_traffic()

    def _spawn_base_traffic(self):
        """Spawn the permanent base fleet distributed across the road network."""
        for vehicle_type, base_count in BASE_TRAFFIC:
            for _ in range(base_count):
                vid = self._next_id
                self._next_id += 1
                node = self.road_network.random_connected_node()
                v = Vehicle(vid, vehicle_type, self.road_network, node)
                # Randomize starting progress so they don't all start at nodes
                v.progress = random.random()
                if v._edge_length > 0:
                    lat1, lon1 = self.road_network.position_of(v.current_node)
                    lat2, lon2 = self.road_network.position_of(v.target_node)
                    v.x = lat1 + (lat2 - lat1) * v.progress
                    v.y = lon1 + (lon2 - lon1) * v.progress
                self._vehicles[vid] = v
                self._base_vehicle_ids.add(vid)

        print(f"[sim] Base traffic: {len(self._base_vehicle_ids)} vehicles spawned")

    def _spawn(self, sensor_id, vehicle_type):
        vid = self._next_id
        self._next_id += 1
        node = self._sensor_nodes[sensor_id]
        # Spawn near the sensor node — pick a random neighbor for variety
        neighbors = self.road_network.neighbors_of(node)
        start = random.choice(neighbors) if neighbors else node
        v = Vehicle(vid, vehicle_type, self.road_network, start)
        self._vehicles[vid] = v
        self._bucket[(sensor_id, vehicle_type)].append(vid)
        return v

    def _despawn(self, sensor_id, vehicle_type, count):
        key = (sensor_id, vehicle_type)
        bucket = self._bucket[key]
        if not bucket or count <= 0:
            return

        sensor_node = self._sensor_nodes[sensor_id]
        slat, slon = self.road_network.position_of(sensor_node)

        def dist_from_sensor(vid):
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

    def update_from_data(self, readings):
        """Set target vehicle counts from sensor readings (amplified by 3x)."""
        for sensor_id, pairs in readings.items():
            if sensor_id not in self._sensor_nodes:
                continue
            existing_types = {k[1] for k in self._targets if k[0] == sensor_id}
            for t in existing_types:
                self._targets[(sensor_id, t)] = 0
            for raw_type, count in pairs:
                mapped = VEHICLE_TYPE_MAP.get(raw_type, raw_type)
                self._targets[(sensor_id, mapped)] += count * SENSOR_AMPLIFIER

    def _apply_gradual_changes(self):
        all_keys = set(self._targets.keys()) | set(self._bucket.keys())
        for key in all_keys:
            want = self._targets.get(key, 0)
            # Clean bucket — never touch base vehicles
            self._bucket[key] = [
                vid for vid in self._bucket[key]
                if vid in self._vehicles and vid not in self._base_vehicle_ids
            ]
            have = len(self._bucket[key])
            sensor_id, vehicle_type = key

            if have < want:
                to_spawn = min(want - have, self._max_change_per_tick)
                for _ in range(to_spawn):
                    self._spawn(sensor_id, vehicle_type)
            elif have > want:
                to_despawn = min(have - want, self._max_change_per_tick)
                self._despawn(sensor_id, vehicle_type, to_despawn)

    def tick(self, dt):
        """Advance all vehicles and gradually adjust sensor-driven counts."""
        self._apply_gradual_changes()
        for v in self._vehicles.values():
            v.move(dt)

    def get_positions(self):
        return [
            {"X": v.x, "Y": v.y, "TYPE": v.vehicle_type, "ID": v.id}
            for v in self._vehicles.values()
        ]
