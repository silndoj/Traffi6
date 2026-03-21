import random
import math

# CRITICAL: data says "motorbike", frontend expects "motor_bike"
VEHICLE_TYPE_MAP = {
    'car': 'car',
    'motorbike': 'motor_bike',
    'truck': 'truck',
    'single-unit-truck': 'truck',
    'articulated-truck': 'truck',
    'car-with-trailer': 'car',
    'bicycle': 'bicycle',
}


def scatter_vehicles(lat, lon, count, radius=0.0008):
    """Generate count random points within a circle of given radius (degrees) around (lat, lon).

    Uses uniform disk distribution: angle + sqrt(random) * radius.
    ~0.0008 degrees is approximately 80m.
    """
    points = []
    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi)
        r = math.sqrt(random.random()) * radius
        dx = r * math.cos(angle)
        dy = r * math.sin(angle)
        points.append((lat + dx, lon + dy))
    return points


class ReplayEngine:
    def __init__(self, time_steps, sensor_positions):
        """
        time_steps: list of (timestamp_str, [{'sensor_id': str, 'vehicles': [(type, count)]}])
        sensor_positions: {sensor_id: (lat, lon)}
        """
        self.time_steps = time_steps
        self.sensor_positions = sensor_positions
        self.current_index = 0

    def advance(self):
        """Advance to next time step.

        Returns (timestamp, markers) where markers is [{'X': lat, 'Y': lon, 'TYPE': str}, ...]
        Loops back to start when data ends.
        """
        if not self.time_steps:
            return ("no_data", [])

        timestamp, records = self.time_steps[self.current_index]
        markers = []

        for record in records:
            sensor_id = record['sensor_id']
            if sensor_id not in self.sensor_positions:
                continue

            lat, lon = self.sensor_positions[sensor_id]

            for vehicle_type, count in record['vehicles']:
                mapped_type = VEHICLE_TYPE_MAP.get(vehicle_type)
                if mapped_type is None:
                    continue

                points = scatter_vehicles(lat, lon, count)
                for plat, plon in points:
                    markers.append({
                        'X': plat,
                        'Y': plon,
                        'TYPE': mapped_type,
                    })

        self.current_index = (self.current_index + 1) % len(self.time_steps)
        return (timestamp, markers)
