"""Pre-computed traffic analytics: peak hours, anomalies, congestion grid."""

from database import get_connection
from collections import defaultdict
import math


def compute_peak_hours() -> list[dict]:
    """Top 5 busiest hours across the dataset.

    Query readings table, group by hour, sum counts.
    Return [{hour: "17:00", avg_vehicles: 190.5, peak_vehicles: 418,
             sensor_count: 23}, ...]
    sorted by avg_vehicles descending, top 5 only.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            sub.hour_label AS hour,
            AVG(sub.hour_total) AS avg_vehicles,
            MAX(sub.hour_total) AS peak_vehicles,
            COUNT(DISTINCT sub.sensor_id) AS sensor_count
        FROM (
            SELECT
                sensor_id,
                strftime('%H:00', timestamp) AS hour_label,
                SUM(count) AS hour_total
            FROM readings
            GROUP BY sensor_id, strftime('%Y-%m-%d %H', timestamp)
        ) sub
        GROUP BY sub.hour_label
        ORDER BY avg_vehicles DESC
        LIMIT 5
    """).fetchall()
    conn.close()

    return [
        {
            "hour": r["hour"],
            "avg_vehicles": round(r["avg_vehicles"], 1),
            "peak_vehicles": r["peak_vehicles"],
            "sensor_count": r["sensor_count"],
        }
        for r in rows
    ]


def compute_sensor_stats() -> dict[str, dict]:
    """Per-sensor mean and stddev of vehicle counts.

    Return {sensor_id: {mean: float, stddev: float, total: int}}
    Used for anomaly detection.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            sensor_id,
            AVG(ts_total) AS mean_count,
            COALESCE(
                SQRT(AVG(ts_total * ts_total) - AVG(ts_total) * AVG(ts_total)),
                0
            ) AS stddev_count,
            SUM(ts_total) AS total
        FROM (
            SELECT sensor_id, timestamp, SUM(count) AS ts_total
            FROM readings
            GROUP BY sensor_id, timestamp
        ) sub
        GROUP BY sensor_id
    """).fetchall()
    conn.close()

    return {
        r["sensor_id"]: {
            "mean": round(r["mean_count"], 2),
            "stddev": round(r["stddev_count"], 2),
            "total": r["total"],
        }
        for r in rows
    }


def detect_anomalies(readings: dict, sensor_stats: dict) -> list[dict]:
    """Given current readings and pre-computed stats, find anomalies.

    Anomaly = sensor count > mean + 2*stddev
    Return [{sensor_id: str, count: int, mean: float, stddev: float,
             severity: float (how many stddevs above), type: 'high_traffic'}, ...]
    """
    anomalies = []
    for sensor_id, vehicles in readings.items():
        if sensor_id not in sensor_stats:
            continue
        stats = sensor_stats[sensor_id]
        count = sum(c for _, c in vehicles)
        threshold = stats["mean"] + 2 * stats["stddev"]

        if stats["stddev"] > 0 and count > threshold:
            severity = round((count - stats["mean"]) / stats["stddev"], 2)
            anomalies.append({
                "sensor_id": sensor_id,
                "count": count,
                "mean": stats["mean"],
                "stddev": stats["stddev"],
                "severity": severity,
                "type": "high_traffic",
            })

    return sorted(anomalies, key=lambda a: a["severity"], reverse=True)


def compute_congestion_grid(readings: dict, sensor_positions: dict) -> list[list[float]]:
    """Compute heatmap data for Leaflet.heat.

    For each sensor with readings:
      - lat, lon from sensor_positions
      - intensity = count / max_count (normalized 0-1)
    Return [[lat, lon, intensity], ...] only for sensors with count > 0
    """
    counts = {}
    for sensor_id, vehicles in readings.items():
        if sensor_id not in sensor_positions:
            continue
        total = sum(c for _, c in vehicles)
        if total > 0:
            counts[sensor_id] = total

    if not counts:
        return []

    max_count = max(counts.values())

    return [
        [
            sensor_positions[sid][0],
            sensor_positions[sid][1],
            round(count / max_count, 3),
        ]
        for sid, count in counts.items()
    ]


def compute_traffic_status(readings: dict, sensor_stats: dict) -> dict:
    """Compute overall traffic status for the mobile card.

    Return {
        level: 'low'|'medium'|'high'|'critical',
        level_color: '#22c55e'|'#f59e0b'|'#ef4444'|'#dc2626',
        total_vehicles: int,
        active_sensors: int,
        anomaly_count: int,
        busiest_sensor: {sensor_id, count},
        avg_speed_estimate: float  # rough estimate based on congestion
    }
    """
    total_vehicles = 0
    active_sensors = 0
    busiest_sensor_id = None
    busiest_count = 0
    anomaly_count = 0
    congestion_ratios = []

    for sensor_id, vehicles in readings.items():
        count = sum(c for _, c in vehicles)
        if count > 0:
            active_sensors += 1
            total_vehicles += count

            if count > busiest_count:
                busiest_count = count
                busiest_sensor_id = sensor_id

            if sensor_id in sensor_stats:
                stats = sensor_stats[sensor_id]
                if stats["stddev"] > 0:
                    ratio = (count - stats["mean"]) / stats["stddev"]
                    congestion_ratios.append(ratio)
                    if count > stats["mean"] + 2 * stats["stddev"]:
                        anomaly_count += 1

    avg_congestion = (
        sum(congestion_ratios) / len(congestion_ratios)
        if congestion_ratios
        else 0
    )

    if avg_congestion > 2:
        level, level_color = "critical", "#dc2626"
    elif avg_congestion > 1:
        level, level_color = "high", "#ef4444"
    elif avg_congestion > 0:
        level, level_color = "medium", "#f59e0b"
    else:
        level, level_color = "low", "#22c55e"

    # Rough speed estimate: 50 km/h baseline, reduced by congestion
    avg_speed_estimate = round(max(5.0, 50.0 - avg_congestion * 10), 1)

    return {
        "level": level,
        "level_color": level_color,
        "total_vehicles": total_vehicles,
        "active_sensors": active_sensors,
        "anomaly_count": anomaly_count,
        "busiest_sensor": (
            {"sensor_id": busiest_sensor_id, "count": busiest_count}
            if busiest_sensor_id
            else None
        ),
        "avg_speed_estimate": avg_speed_estimate,
    }
