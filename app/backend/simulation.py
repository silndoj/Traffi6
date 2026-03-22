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
            self._weights[nid] = 1.0 + 0.5 * (1.0 - norm)  # flatter: 1.5 center, 1.0 edge

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

    def __init__(self, vid, vehicle_type, road_network, start_node, sim=None):
        self.id = vid
        self.vehicle_type = vehicle_type
        self.speed = SPEED_MAP.get(vehicle_type, 10.0)
        self._net = road_network
        self._sim = sim  # reference to TrafficSimulation for traffic light checks
        self.attraction_node = None
        self._waiting_at_red = False
        self._queue_offset = 0.0  # how far back from intersection when queued

        lat, lon = road_network.position_of(start_node)
        self.x = lat
        self.y = lon

        self.current_node = start_node
        self.target_node = start_node
        self.progress = 0.0
        self._edge_length = 0.0
        self._recent_nodes = []  # anti-backtrack memory

        self._pick_next_target()

    def _teleport_to_central(self):
        """Move to a random well-connected central node."""
        new_node = self._net.random_central_node()
        self.current_node = new_node
        self.target_node = new_node
        lat, lon = self._net.position_of(new_node)
        self.x = lat
        self.y = lon
        self._recent_nodes = []

    def _pick_next_target(self):
        # Hero car: follow fixed route instead of random walk
        if hasattr(self, '_hero_route') and self._hero_route:
            idx = self._hero_route_idx
            if idx < len(self._hero_route) - 1:
                self._hero_route_idx += 1
                self.current_node = self._hero_route[idx]
                self.target_node = self._hero_route[idx + 1]
                self.progress = 0.0
                self._edge_length = self._net.edge_length_m(self.current_node, self.target_node)
                self._recent_nodes = []
                return
            else:
                # Reached end of route — restart from beginning
                self._hero_route_idx = 0
                self.current_node = self._hero_route[0]
                self.target_node = self._hero_route[1] if len(self._hero_route) > 1 else self._hero_route[0]
                lat, lon = self._net.position_of(self.current_node)
                self.x = lat
                self.y = lon
                self.progress = 0.0
                self._edge_length = self._net.edge_length_m(self.current_node, self.target_node)
                return

        neighbors = self._net.neighbors_of(self.target_node)
        if not neighbors:
            self._teleport_to_central()
            neighbors = self._net.neighbors_of(self.target_node)
            if not neighbors:
                return

        # Filter: exclude dead ends (1 neighbor) and recently visited nodes
        good = [n for n in neighbors
                if n != self.current_node
                and n not in self._recent_nodes
                and len(self._net.neighbors_of(n)) >= 2]

        # Fallback: if all neighbors are dead ends, at least avoid recent
        if not good:
            good = [n for n in neighbors if n != self.current_node and n not in self._recent_nodes]
        if not good:
            good = [n for n in neighbors if n != self.current_node]
        if not good:
            good = neighbors

        weights = [self._net.weight_of(n) for n in good]

        # Attraction-aware routing
        # Threshold adapts to traffic intensity: quiet hours use wider radius
        # so vehicles spread more evenly instead of clustering tightly
        attraction_threshold = 300  # default: start circulating within 300m
        if self._sim is not None:
            intensity = getattr(self._sim, '_traffic_intensity', 5.0)
            if intensity < 3:
                attraction_threshold = 1000  # quiet hours: weaker attraction
        if self.attraction_node is not None:
            attr_lat, attr_lon = self._net.position_of(self.attraction_node)
            my_dist = _latlon_distance_m(attr_lat, attr_lon, self.x, self.y)
            if my_dist > attraction_threshold:
                for i, n in enumerate(good):
                    n_lat, n_lon = self._net.position_of(n)
                    n_dist = _latlon_distance_m(attr_lat, attr_lon, n_lat, n_lon)
                    if n_dist < my_dist:
                        weights[i] *= 5.0

        # Boundary containment
        dist_from_center = _latlon_distance_m(CENTER_LAT, CENTER_LON, self.x, self.y)
        if dist_from_center > 4500:
            self._teleport_to_central()
            neighbors = self._net.neighbors_of(self.target_node)
            if not neighbors:
                return
            good = [n for n in neighbors if len(self._net.neighbors_of(n)) >= 2] or neighbors
            weights = [self._net.weight_of(n) for n in good]
        elif dist_from_center > BOUNDARY_RADIUS_M:
            boost = 2.0 + (dist_from_center - BOUNDARY_RADIUS_M) / 200
            for i, n in enumerate(good):
                n_lat, n_lon = self._net.position_of(n)
                n_dist = _latlon_distance_m(CENTER_LAT, CENTER_LON, n_lat, n_lon)
                if n_dist < dist_from_center:
                    weights[i] *= boost

        # Update anti-backtrack memory (keep last 3)
        self._recent_nodes.append(self.current_node)
        if len(self._recent_nodes) > 3:
            self._recent_nodes.pop(0)

        self.current_node = self.target_node
        self.target_node = random.choices(good, weights=weights, k=1)[0]
        self.progress = 0.0
        self._edge_length = self._net.edge_length_m(self.current_node, self.target_node)

    def _is_red_light(self, node_id):
        """Check if a node has a red traffic light right now."""
        if self._sim is None:
            return False
        tl = self._sim._traffic_lights.get(node_id)
        if tl is None:
            return False  # no traffic light at this node
        t = (self._sim._sim_time + tl["phase_offset"]) % tl["cycle_sec"]
        green_duration = tl["cycle_sec"] * 0.45
        yellow_duration = 3.0
        return t >= green_duration + yellow_duration  # red phase

    def move(self, dt):
        # Skip micro-edges (<10m) instantly
        if 0 < self._edge_length < 10:
            self._pick_next_target()

        if self._edge_length <= 0:
            self._pick_next_target()
            if self._edge_length <= 0:
                return

        # If waiting at a red light, check if it turned green
        if self._waiting_at_red:
            if self._is_red_light(self.target_node):
                # Stay queued — position along road behind intersection
                lat1, lon1 = self._net.position_of(self.current_node)
                lat2, lon2 = self._net.position_of(self.target_node)
                queue_progress = max(0.5, 1.0 - self._queue_offset)
                self.x = lat1 + (lat2 - lat1) * queue_progress
                self.y = lon1 + (lon2 - lon1) * queue_progress
                return
            self._waiting_at_red = False
            self._queue_offset = 0.0
            self._pick_next_target()

        distance_moved = self.speed * dt
        self.progress += distance_moved / self._edge_length

        # Approaching a red light — decelerate and stop before intersection
        if self.progress >= 0.85 and self._is_red_light(self.target_node):
            self.progress = min(self.progress, 0.92)
            self._waiting_at_red = True
            # Assign queue position: small random offset so vehicles don't stack
            self._queue_offset = random.uniform(0.04, 0.35)

        # Reaching target node — proceed through
        if self.progress >= 1.0:
            self.progress -= 1.0
            self._pick_next_target()
            if self._edge_length <= 0:
                self.progress = 0.0

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

        # Traffic lights at intersections with 4+ connections
        self._traffic_lights = {}
        self._sim_time = 0.0
        self._init_traffic_lights()

        # Create exactly POOL_SIZE vehicles with fixed composition
        self._create_pool()

    def _init_traffic_lights(self):
        """Place traffic lights at intersections with 4+ road connections."""
        rn = self.road_network
        for nid in rn.nodes:
            degree = len(rn.edges.get(nid, []))
            if degree >= 4:
                lat, lon = rn.nodes[nid]
                # Cycle time based on intersection size: bigger = longer cycle
                cycle_sec = 30 + degree * 10  # 70s for 4-way, 90s for 6-way
                # Random phase offset so not all lights sync
                phase_offset = random.random() * cycle_sec
                self._traffic_lights[nid] = {
                    "lat": lat,
                    "lon": lon,
                    "cycle_sec": cycle_sec,
                    "phase_offset": phase_offset,
                    "degree": degree,
                }
        print(f"[sim] Traffic lights: {len(self._traffic_lights)} intersections")

    def get_traffic_light_states(self):
        """Return current state of traffic lights within visible map bounds."""
        lights = []
        for nid, tl in self._traffic_lights.items():
            # Skip lights outside visible area
            # Only show major intersections (5+ connections) to reduce frontend DOM load
            if tl["degree"] < 5:
                continue
            if abs(tl["lat"] - CENTER_LAT) > 0.035 or abs(tl["lon"] - CENTER_LON) > 0.05:
                continue

            t = (self._sim_time + tl["phase_offset"]) % tl["cycle_sec"]
            green_duration = tl["cycle_sec"] * 0.45
            yellow_duration = 3.0

            if t < green_duration:
                state = "green"
            elif t < green_duration + yellow_duration:
                state = "yellow"
            else:
                state = "red"

            lights.append({
                "lat": round(tl["lat"], 6),
                "lon": round(tl["lon"], 6),
                "state": state,
                "degree": tl["degree"],
            })
        return lights

    def enable_green_wave(self, corridors):
        """Synchronize corridor traffic lights AND route vehicles through corridors.

        Two effects:
        1. Sync light phases along corridors (cascade green lights)
        2. Increase green time ratio on corridor lights (45% → 70%)
        3. Redirect 30% of vehicles to use corridor routes
        """
        self._green_wave_active = True
        self._original_offsets = {}
        self._original_cycles = {}

        # Collect corridor sensor nodes for vehicle routing
        corridor_sensor_nodes = set()

        for corridor in corridors:
            sensors = corridor.get("sensors", [])
            if len(sensors) < 2:
                continue

            for s in sensors:
                sid = s.get("sensor_id")
                if sid and sid in self._sensor_nodes:
                    corridor_sensor_nodes.add(self._sensor_nodes[sid])

            corridor_points = [(s["lat"], s["lon"]) for s in sensors]
            corridor_speed = 30 / 3.6

            for nid, tl in self._traffic_lights.items():
                if nid in self._original_offsets:
                    continue

                tlat, tlon = tl["lat"], tl["lon"]
                min_perp_dist = float("inf")
                dist_along = 0.0
                cumulative_dist = 0.0

                for i in range(len(corridor_points) - 1):
                    ax, ay = corridor_points[i]
                    bx, by = corridor_points[i + 1]
                    seg_len = _latlon_distance_m(ax, ay, bx, by)

                    if seg_len > 0:
                        dx, dy = bx - ax, by - ay
                        t = max(0, min(1, ((tlat - ax) * dx + (tlon - ay) * dy) / (dx * dx + dy * dy)))
                        px, py = ax + t * dx, ay + t * dy
                        perp_dist = _latlon_distance_m(tlat, tlon, px, py)

                        if perp_dist < min_perp_dist:
                            min_perp_dist = perp_dist
                            dist_along = cumulative_dist + t * seg_len

                    cumulative_dist += seg_len

                if min_perp_dist < 80:
                    self._original_offsets[nid] = tl["phase_offset"]
                    self._original_cycles[nid] = tl["cycle_sec"]
                    travel_time = dist_along / corridor_speed
                    tl["phase_offset"] = travel_time
                    # Increase green time: shorter cycle, more green ratio
                    tl["cycle_sec"] = tl["cycle_sec"] * 0.85

        # Route 30% of free-roaming vehicles toward corridor sensor nodes
        if corridor_sensor_nodes:
            corridor_nodes = list(corridor_sensor_nodes)
            redirected = 0
            for vid, v in self._vehicles.items():
                if v.attraction_node is None and random.random() < 0.3:
                    target = random.choice(corridor_nodes)
                    v.attraction_node = target
                    self._attractions[vid] = target
                    redirected += 1

        synced = len(self._original_offsets)
        print(f"[sim] Green wave: {synced} lights synced, {len(corridor_sensor_nodes)} corridor nodes, {redirected} vehicles redirected")

        synced = len(self._original_offsets)
        print(f"[sim] Green wave enabled: {synced} lights synchronized across {len(corridors)} corridors")

    def disable_green_wave(self):
        """Restore original phase offsets, cycle times, and clear vehicle redirects."""
        if not hasattr(self, '_original_offsets'):
            return
        for nid, original_offset in self._original_offsets.items():
            if nid in self._traffic_lights:
                self._traffic_lights[nid]["phase_offset"] = original_offset
        for nid, original_cycle in getattr(self, '_original_cycles', {}).items():
            if nid in self._traffic_lights:
                self._traffic_lights[nid]["cycle_sec"] = original_cycle
        self._original_offsets = {}
        self._green_wave_active = False
        print("[sim] Green wave disabled: original timing restored")

    def _create_pool(self):
        vid = 0
        for vehicle_type, share in POOL_COMPOSITION.items():
            count = round(share * POOL_SIZE)
            for _ in range(count):
                node = self.road_network.random_connected_node()
                v = Vehicle(vid, vehicle_type, self.road_network, node, sim=self)
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
            v = Vehicle(vid, "car", self.road_network, node, sim=self)
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

        # Traffic intensity: avg vehicles per reporting sensor
        reporting_sensors = max(1, len(sensor_totals))
        traffic_intensity = grand_total / reporting_sensors
        self._traffic_intensity = traffic_intensity

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

        # Rush hour amplification: concentrate vehicles at top sensors
        if traffic_intensity > 8 and len(sensor_allocations) >= 4:
            # Amplify top 3 sensors by 1.5x, reduce bottom sensors proportionally
            top_bonus = 0
            amplified = []
            for i, (sensor_id, alloc) in enumerate(sensor_allocations[:3]):
                bonus = round(alloc * 0.5)
                amplified.append((sensor_id, alloc + bonus))
                top_bonus += bonus
            amplified.extend(sensor_allocations[3:])

            # Reduce bottom sensors to compensate (keep total = POOL_SIZE)
            bottom_sensors = amplified[3:]
            bottom_total = sum(a for _, a in bottom_sensors)
            if bottom_total > 0 and top_bonus > 0:
                reduction_ratio = max(0.0, (bottom_total - top_bonus) / bottom_total)
                rebalanced_bottom = [
                    (sid, max(0, round(alloc * reduction_ratio)))
                    for sid, alloc in bottom_sensors
                ]
                amplified = amplified[:3] + rebalanced_bottom

            # Fix rounding: adjust last sensor to hit POOL_SIZE exactly
            current_total = sum(a for _, a in amplified)
            if current_total != POOL_SIZE and amplified:
                last_sid, last_alloc = amplified[-1]
                amplified[-1] = (last_sid, last_alloc + (POOL_SIZE - current_total))

            sensor_allocations = amplified

        # When Green Wave is active, keep existing corridor-routed vehicles assigned
        all_vids = list(self._vehicles.keys())
        assigned = set()
        if getattr(self, '_green_wave_active', False):
            for vid in all_vids:
                if self._attractions.get(vid) is not None:
                    assigned.add(vid)

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
        self._sim_time += dt
        for v in self._vehicles.values():
            v.move(dt)

    def launch_hero_car(self):
        """Launch a special hero car that drives Spassbecken → Heidesee."""
        from collections import deque

        rn = self.road_network
        # Spassbecken → Heidesee
        start_node = rn.nearest_node(48.985, 8.395)
        end_node = rn.nearest_node(49.020, 8.435)

        # BFS to find road path
        visited = {start_node}
        queue = deque([(start_node, [start_node])])
        route = None
        while queue:
            node, path = queue.popleft()
            if node == end_node:
                route = path
                break
            if len(path) > 50:
                continue
            for neighbor in rn.neighbors_of(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        if not route:
            print("[sim] Hero car: no route found!")
            return

        # Create the hero car with a fixed route
        vid = -1  # special ID
        v = Vehicle(vid, "car", rn, route[0], sim=self)
        v._hero_route = route
        v._hero_route_idx = 0
        v.speed = 14.0  # slightly faster than normal cars
        self._vehicles[vid] = v
        self._hero_car = v

        print(f"[sim] Hero car launched: {len(route)} nodes, "
              f"{sum(rn.edge_length_m(route[k], route[k+1]) for k in range(len(route)-1)):.0f}m")

    def remove_hero_car(self):
        if -1 in self._vehicles:
            del self._vehicles[-1]
            self._hero_car = None
            print("[sim] Hero car removed")

    def get_positions(self):
        result = [
            {"X": round(v.x, 6), "Y": round(v.y, 6), "TYPE": v.vehicle_type, "ID": v.id}
            for v in self._vehicles.values()
            if v.id != -1  # exclude hero car from regular list
        ]
        # Add hero car with special type
        if hasattr(self, '_hero_car') and self._hero_car and -1 in self._vehicles:
            h = self._hero_car
            result.append({
                "X": round(h.x, 6), "Y": round(h.y, 6),
                "TYPE": "hero", "ID": -1,
            })
        return result

    def get_corridor_vehicle_count(self, corridors):
        """Count how many vehicles are currently near each corridor.

        Returns a list of dicts with corridor_id, vehicle_count, and
        avg_speed_pct for each corridor.  A vehicle is "on" a corridor
        if its attraction_node matches one of the corridor's sensor nodes.
        """
        # Build a set of sensor nodes per corridor
        corridor_sensor_nodes = []
        for corridor in corridors:
            sensor_ids = [s.get("sensor_id", s.get("id", "")) for s in corridor.get("sensors", [])]
            nodes = set()
            for sid in sensor_ids:
                node = self._sensor_nodes.get(sid)
                if node is not None:
                    nodes.add(node)
            corridor_sensor_nodes.append(nodes)

        results = []
        for idx, corridor in enumerate(corridors):
            nodes = corridor_sensor_nodes[idx]
            if not nodes:
                results.append({
                    "corridor_id": corridor.get("id", idx),
                    "vehicle_count": 0,
                    "avg_speed_pct": 0.0,
                })
                continue

            matched_vehicles = [
                v for v in self._vehicles.values()
                if v.attraction_node in nodes
            ]
            vehicle_count = len(matched_vehicles)

            # Average speed as percentage of max speed for vehicle type
            if vehicle_count > 0:
                speed_pcts = []
                for v in matched_vehicles:
                    max_speed = SPEED_MAP.get(v.vehicle_type, 10.0)
                    # Stopped vehicles have 0% speed; moving ones approximate full speed
                    pct = 0.0 if v._waiting_at_red else 100.0
                    speed_pcts.append(pct)
                avg_speed_pct = round(sum(speed_pcts) / len(speed_pcts), 1)
            else:
                avg_speed_pct = 0.0

            results.append({
                "corridor_id": corridor.get("id", idx),
                "vehicle_count": vehicle_count,
                "avg_speed_pct": avg_speed_pct,
            })

        return results
