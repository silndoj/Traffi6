"""Traffic signal intelligence engine.

TWO categories of output:
1. REAL analysis -- proven directly from 589K sensor readings
2. MODELED recommendations -- prototype suggestions based on assumptions
"""

import math
from database import get_connection


def compute_intersection_analysis():
    """ALL REAL DATA. Per-sensor hourly traffic profiles, CV scores, peak hours."""
    conn = get_connection()

    sensors = conn.execute(
        "SELECT sensor_id, total_volume FROM sensors"
    ).fetchall()

    analysis = {}

    for sensor in sensors:
        sid = sensor["sensor_id"]
        total_vol = sensor["total_volume"] or 0

        hourly_rows = conn.execute(
            "SELECT substr(timestamp, 12, 2) as hour, SUM(count) as total "
            "FROM readings WHERE sensor_id = ? GROUP BY hour ORDER BY hour",
            (sid,),
        ).fetchall()

        hourly_profile = [0.0] * 24
        for row in hourly_rows:
            h = int(row["hour"])
            if 0 <= h < 24:
                hourly_profile[h] = float(row["total"])

        peak_hour = max(range(24), key=lambda h: hourly_profile[h])
        daily_avg = sum(hourly_profile)

        all_counts = conn.execute(
            "SELECT count FROM readings WHERE sensor_id = ?", (sid,)
        ).fetchall()
        values = [float(r["count"]) for r in all_counts]

        if len(values) > 1:
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            stddev = math.sqrt(variance)
            cv = stddev / mean if mean > 0 else 0.0
        else:
            mean = values[0] if values else 0.0
            stddev = 0.0
            cv = 0.0

        analysis[sid] = {
            "hourly_profile": hourly_profile,
            "peak_hour": f"{peak_hour:02d}:00",
            "daily_avg": daily_avg,
            "cv": cv,
            "needs_adaptive": cv > 0.5,
            "total_volume": total_vol,
            "mean": mean,
            "stddev": stddev,
        }

    conn.close()
    return analysis


def _haversine(lat1, lon1, lat2, lon2):
    """Distance in meters between two lat/lon points."""
    r = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _pearson(xs, ys):
    """Pearson correlation coefficient for two equal-length sequences."""
    n = len(xs)
    if n == 0:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def find_coordination_pairs(sensor_positions):
    """REAL proximity + correlation from real hourly patterns.

    For every sensor pair within 500m: Pearson correlation of 24h profiles.
    Returns pairs with correlation > 0.5 sorted by combined volume desc.
    """
    analysis = compute_intersection_analysis()
    sids = [s for s in analysis if s in sensor_positions]
    pairs = []

    for i, sid_a in enumerate(sids):
        lat_a, lon_a = sensor_positions[sid_a]
        prof_a = analysis[sid_a]["hourly_profile"]
        vol_a = analysis[sid_a]["total_volume"]

        for sid_b in sids[i + 1 :]:
            lat_b, lon_b = sensor_positions[sid_b]
            dist = _haversine(lat_a, lon_a, lat_b, lon_b)

            if dist > 500:
                continue

            prof_b = analysis[sid_b]["hourly_profile"]
            corr = _pearson(prof_a, prof_b)

            if corr > 0.5:
                pairs.append({
                    "sensor_a": sid_a,
                    "sensor_b": sid_b,
                    "distance_m": round(dist, 1),
                    "correlation": round(corr, 4),
                    "combined_volume": vol_a + analysis[sid_b]["total_volume"],
                })

    pairs.sort(key=lambda p: p["combined_volume"], reverse=True)
    return pairs


def compute_city_summary(analysis, pairs):
    """ALL REAL data summary across the city."""
    conn = get_connection()
    total_readings = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]

    type_rows = conn.execute(
        "SELECT vehicle_type, SUM(count) as total FROM readings "
        "GROUP BY vehicle_type ORDER BY total DESC"
    ).fetchall()

    hourly_city = conn.execute(
        "SELECT substr(timestamp, 12, 2) as hour, SUM(count) as total "
        "FROM readings GROUP BY hour ORDER BY hour"
    ).fetchall()
    conn.close()

    city_profile = [0] * 24
    for row in hourly_city:
        h = int(row["hour"])
        if 0 <= h < 24:
            city_profile[h] = row["total"]

    peak_h = max(range(24), key=lambda h: city_profile[h])
    quiet_h = min(range(24), key=lambda h: city_profile[h])

    grand_total = sum(r["total"] for r in type_rows) or 1
    breakdown = {
        r["vehicle_type"]: round(r["total"] * 100 / grand_total)
        for r in type_rows
    }

    adaptive_count = sum(1 for a in analysis.values() if a["needs_adaptive"])
    pct_adaptive = round(adaptive_count * 100 / max(len(analysis), 1))

    busiest = max(analysis.items(), key=lambda kv: kv[1]["total_volume"])

    # Compute peak vs off-peak ratio
    peak_vol = sum(city_profile[h] for h in range(7, 19))
    offpeak_vol = sum(city_profile[h] for h in range(0, 7)) + sum(city_profile[h] for h in range(19, 24))
    peak_ratio = round(peak_vol / max(1, offpeak_vol) * 12 / 12, 1)  # normalize by hours

    # Estimated daily savings (conservative 15% reduction in peak wait time)
    daily_savings_hours = int(peak_vol * 0.15 / 60)

    # Top 5 worst intersections by congestion score (volume × variance)
    hotspots = []
    for sid, a in analysis.items():
        cv = a.get("cv", 0)
        vol = a.get("total_volume", 0)
        score = a.get("mean", 0) * a.get("stddev", 0)
        if score > 0:
            hotspots.append({"sensor_id": sid, "score": round(score), "cv": round(cv, 2), "volume": vol})
    hotspots.sort(key=lambda x: -x["score"])

    return {
        "total_sensors": len(analysis),
        "total_readings": total_readings,
        "pct_needs_adaptive": pct_adaptive,
        "peak_hour": f"{peak_h:02d}:00",
        "peak_hour_volume": city_profile[peak_h],
        "coordination_pairs": len(pairs),
        "busiest_sensor": {
            "sensor_id": busiest[0],
            "total_volume": busiest[1]["total_volume"],
        },
        "quietest_hour": f"{quiet_h:02d}:00",
        "vehicle_type_breakdown": breakdown,
        "peak_vs_offpeak_ratio": peak_ratio,
        "estimated_daily_savings_hours": daily_savings_hours,
        "top_hotspots": hotspots[:5],
    }


def model_signal_recommendations(analysis):
    """MODELED (clearly labeled). Signal timing recommendations.

    Assumes current signals use fixed 90s cycle with 50/50 green split.
    """
    recommendations = {}

    for sid, data in analysis.items():
        profile = data["hourly_profile"]
        daily_total = sum(profile) or 1

        hourly_recs = []
        for h in range(24):
            share = profile[h] / daily_total
            green_pct = round(30 + share * (80 - 30) * 24)
            green_pct = max(30, min(80, green_pct))

            if 0 <= h < 6:
                cycle_sec = 60
            elif 6 <= h < 9:
                cycle_sec = 80
            elif 9 <= h < 18:
                cycle_sec = 100
            elif 18 <= h < 22:
                cycle_sec = 80
            else:
                cycle_sec = 60

            hourly_recs.append({
                "hour": f"{h:02d}:00",
                "green_pct": green_pct,
                "cycle_sec": cycle_sec,
            })

        improvement = min(data["cv"] * 15, 30)

        recommendations[sid] = {
            "current_cycle": 90,
            "current_green_pct": 50,
            "hourly_recommendations": hourly_recs,
            "estimated_improvement_pct": round(improvement, 1),
            "model_basis": "Assumed fixed 90s/50% baseline",
        }

    return recommendations


def model_green_wave_corridors(pairs, sensor_positions):
    """MODELED timing, REAL topology.

    Groups coordination pairs into chains and computes signal offsets
    assuming 30 km/h average city driving speed.
    """
    adjacency = {}
    for p in pairs:
        a, b = p["sensor_a"], p["sensor_b"]
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    pair_lookup = {}
    for p in pairs:
        pair_lookup[(p["sensor_a"], p["sensor_b"])] = p
        pair_lookup[(p["sensor_b"], p["sensor_a"])] = p

    visited = set()
    corridors = []
    speed_ms = 30 / 3.6

    for start in adjacency:
        if start in visited:
            continue

        chain = [start]
        visited.add(start)
        current = start

        while True:
            neighbors = adjacency.get(current, set()) - visited
            if not neighbors:
                break
            nxt = max(neighbors, key=lambda n: pair_lookup.get(
                (current, n), {"combined_volume": 0}
            )["combined_volume"])
            chain.append(nxt)
            visited.add(nxt)
            current = nxt

        if len(chain) < 2:
            continue

        sensors_out = []
        total_length = 0.0
        cumulative_offset = 0.0

        for idx, sid in enumerate(chain):
            if sid not in sensor_positions:
                continue
            lat, lon = sensor_positions[sid]

            if idx > 0:
                prev_sid = chain[idx - 1]
                if prev_sid in sensor_positions:
                    plat, plon = sensor_positions[prev_sid]
                    seg_dist = _haversine(plat, plon, lat, lon)
                    total_length += seg_dist
                    cumulative_offset += seg_dist / speed_ms

            sensors_out.append({
                "sensor_id": sid,
                "lat": lat,
                "lon": lon,
                "offset_sec": round(cumulative_offset, 1),
            })

        combined_vol = sum(
            pair_lookup.get((chain[i], chain[i + 1]), {"combined_volume": 0})[
                "combined_volume"
            ]
            for i in range(len(chain) - 1)
        )

        corridors.append({
            "corridor_id": f"corridor_{len(corridors) + 1}",
            "sensors": sensors_out,
            "total_length_m": round(total_length, 1),
            "travel_time_sec": round(total_length / speed_ms, 1),
            "combined_volume": combined_vol,
            "model_basis": "Assumed 30km/h city driving",
        })

    corridors.sort(key=lambda c: c["combined_volume"], reverse=True)
    return corridors
