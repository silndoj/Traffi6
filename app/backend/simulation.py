"""
simulation.py — Constant-pool traffic simulation on real Karlsruhe road network.

Exactly POOL_SIZE (750) vehicles exist at ALL times. Sensor data controls WHERE
vehicles cluster via attraction zones, not how many exist. No spawn/despawn.
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
RADIUS_M = 5000  # 5km radius — covers most of inner Karlsruhe

# Meters per degree at Karlsruhe's latitude
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = 73_000.0

SPEED_MAP = {
    "car": 12.0,
    "truck": 8.0,
    "bicycle": 4.0,
    "motor_bike": 14.0,
    "foot": 1.5,
}

VEHICLE_TYPE_MAP = {
    "car": "car",
    "motorbike": "motor_bike",
    "truck": "truck",
    "single-unit-truck": "truck",
    "articulated-truck": "truck",
    "car-with-trailer": "car",
    "bicycle": "bicycle",
}

# Constant pool — exactly this many vehicles exist at all times
POOL_SIZE = 750
POOL_COMPOSITION = {
    "car": 0.65,
    "truck": 0.08,
    "motor_bike": 0.15,
    "bicycle": 0.07,
    "foot": 0.05,
}

# Boundary containment radius (meters) — beyond this, vehicles pushed toward center
BOUNDARY_RADIUS_M = 3500


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

        # pickle is safe here — we only load our own OSMnx-generated cache
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

        self._connected_nodes = [
            nid for nid in self.nodes if len(self.edges.get(nid, [])) >= 2
        ]
        self._central_nodes = [
            nid for nid in self._connected_nodes
            if _latlon_distance_m(CENTER_LAT, CENTER_LON, *self.nodes[nid]) < 2000
        ]
        if not self._central_nodes:
            self._central_nodes = self._connected_nodes

        print(f"Road network ready: {len(self.nodes)} nodes, "
              f"{sum(len(v) for v in self.edges.values()) // 2} edges, "
              f"{len(self._central_nodes)} central, "
              f"{len(self._connected_nodes)} connected")

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
        self.attraction_node = None

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
            # Dead end — teleport to a random CENTRAL node (not edge)
            new_node = self._net.random_central_node()
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

        # Attraction-aware routing: steer toward assigned sensor node
        if self.attraction_node is not None:
            attr_lat, attr_lon = self._net.position_of(self.attraction_node)
            my_dist = _latlon_distance_m(attr_lat, attr_lon, self.x, self.y)

            if my_dist > 500:  # >500m from target: actively route toward it
                for i, n in enumerate(candidates):
                    n_lat, n_lon = self._net.position_of(n)
                    n_dist = _latlon_distance_m(attr_lat, attr_lon, n_lat, n_lon)
                    if n_dist < my_dist:
                        weights[i] *= 3.0  # strongly prefer getting closer

        # Boundary containment: if far from center, strongly prefer inward movement
        dist_from_center = _latlon_distance_m(CENTER_LAT, CENTER_LON, self.x, self.y)
        if dist_from_center > BOUNDARY_RADIUS_M:
            boost = 1.0 + (dist_from_center - BOUNDARY_RADIUS_M) / 300
            for i, n in enumerate(candidates):
                n_lat, n_lon = self._net.position_of(n)
                n_dist = _latlon_distance_m(CENTER_LAT, CENTER_LON, n_lat, n_lon)
                if n_dist < dist_from_center:
                    weights[i] *= boost

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
    """Constant-pool simulation: exactly POOL_SIZE vehicles at all times."""

    def __init__(self, sensor_positions):
        self.road_network = RoadNetwork()
        self._vehicles = {}
        self._attractions = {}  # vehicle_id → target_sensor_node (or None)

        # Map each sensor to its nearest road node
        self._sensor_nodes = {}
        for sensor_id, (lat, lon) in sensor_positions.items():
            self._sensor_nodes[sensor_id] = self.road_network.nearest_node(lat, lon)

        # Create exactly POOL_SIZE vehicles with fixed composition
        self._create_pool()

    def _create_pool(self):
        vid = 0
        for vehicle_type, share in POOL_COMPOSITION.items():
            count = round(share * POOL_SIZE)
            for _ in range(count):
                node = self.road_network.random_connected_node()
                v = Vehicle(vid, vehicle_type, self.road_network, node)
                # Scatter initial progress so vehicles don't all start at nodes
                v.progress = random.random()
                if v._edge_length > 0:
                    lat1, lon1 = self.road_network.position_of(v.current_node)
                    lat2, lon2 = self.road_network.position_of(v.target_node)
                    v.x = lat1 + (lat2 - lat1) * v.progress
                    v.y = lon1 + (lon2 - lon1) * v.progress
                self._vehicles[vid] = v
                self._attractions[vid] = None
                vid += 1

        # Fix rounding: add or remove to hit exactly POOL_SIZE
        while len(self._vehicles) < POOL_SIZE:
            node = self.road_network.random_connected_node()
            v = Vehicle(vid, "car", self.road_network, node)
            self._vehicles[vid] = v
            self._attractions[vid] = None
            vid += 1
        # If rounding overshot, remove the last added (unlikely, but safe)
        while len(self._vehicles) > POOL_SIZE:
            last_vid = max(self._vehicles.keys())
            del self._vehicles[last_vid]
            del self._attractions[last_vid]

        print(f"[sim] Constant pool: {len(self._vehicles)} vehicles "
              f"(target: {POOL_SIZE})")

    def update_from_data(self, readings):
        """Redistribute attraction zones based on sensor data."""
        # Flatten readings into {sensor_id: total_count}
        sensor_totals = {}
        for sensor_id, pairs in readings.items():
            if sensor_id not in self._sensor_nodes:
                continue
            total = 0
            for _raw_type, count in pairs:
                total += count
            sensor_totals[sensor_id] = total

        grand_total = sum(sensor_totals.values())
        if grand_total <= 0:
            # No data — clear all attractions (free roam)
            for vid in self._attractions:
                self._attractions[vid] = None
                self._vehicles[vid].attraction_node = None
            return

        # Sort sensors by count descending (busiest first)
        sorted_sensors = sorted(
            sensor_totals.items(), key=lambda kv: kv[1], reverse=True
        )

        # Compute how many vehicles each sensor should attract
        sensor_allocations = []
        allocated_so_far = 0
        for i, (sensor_id, count) in enumerate(sorted_sensors):
            if i == len(sorted_sensors) - 1:
                # Last sensor gets the remainder to avoid rounding drift
                alloc = POOL_SIZE - allocated_so_far
            else:
                alloc = round((count / grand_total) * POOL_SIZE)
            alloc = max(0, min(alloc, POOL_SIZE - allocated_so_far))
            sensor_allocations.append((sensor_id, alloc))
            allocated_so_far += alloc

        # Build list of all vehicle ids with their distance to each sensor
        all_vids = list(self._vehicles.keys())
        assigned = set()

        for sensor_id, alloc in sensor_allocations:
            if alloc <= 0:
                continue

            sensor_node = self._sensor_nodes[sensor_id]
            slat, slon = self.road_network.position_of(sensor_node)

            # Score unassigned vehicles by distance to this sensor
            candidates = []
            for vid in all_vids:
                if vid in assigned:
                    continue
                v = self._vehicles[vid]
                dist = _latlon_distance_m(slat, slon, v.x, v.y)
                candidates.append((dist, vid))

            # Pick the closest `alloc` vehicles
            candidates.sort()
            for _, vid in candidates[:alloc]:
                self._attractions[vid] = sensor_node
                self._vehicles[vid].attraction_node = sensor_node
                assigned.add(vid)

        # Unassigned vehicles: free roam
        for vid in all_vids:
            if vid not in assigned:
                self._attractions[vid] = None
                self._vehicles[vid].attraction_node = None

    def tick(self, dt):
        for v in self._vehicles.values():
            v.move(dt)

    def get_positions(self):
        return [
            {"X": v.x, "Y": v.y, "TYPE": v.vehicle_type, "ID": v.id}
            for v in self._vehicles.values()
        ]
