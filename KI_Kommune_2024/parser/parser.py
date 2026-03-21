import json

file_path = "../data2/Daten_20241105.json"

from typing import List, Optional, Callable
from dataclasses import dataclass


@dataclass
class Vehicle:
    count: int
    name: str

@dataclass
class Lane:
    total: int
    classes: List[Vehicle]

@dataclass
class SensorRecord:
    _id: str
    sensor_id: str
    weather_bitmap: int
    mq_timestamp: str
    timezone: str
    timestamp: str
    lane1: Lane
    lane2: Lane

#@dataclass
#class SensorData:
#    records: List[SensorRecord]

records = {}

# Recursive function to explore dimensions
def explore_json_structure(data, depth=0):
    if isinstance(data, dict):
        print(" " * depth * 2 + f"Dict with keys: {list(data.keys())}")
        for key, value in data.items():
            print(" " * depth * 2 + f"Key: {key}")
            explore_json_structure(value, depth + 1)
    elif isinstance(data, list):
        print(" " * depth * 2 + f"List of length: {len(data)}")
        if data:
            print(" " * depth * 2 + "First item structure:")
            explore_json_structure(data[0], depth + 1)
    else:
        print(" " * depth * 2 + f"Value type: {type(data).__name__} (Example: {data})")

with open(file_path, 'r') as f:
    data = json.load(f)

def parse_sensor_data(file_path = file_path) -> List[SensorRecord]:
    with open(file_path, 'r') as f:
        data = json.load(f)
    records = []
    for item in data:
        lane1_classes = []
        for cls in item["lane1"]["classes"]:
            if isinstance(cls, dict) and 'class' in cls and 'count' in cls:
                lane1_classes.append(Vehicle(name=cls['class'], count=cls['count']))
            elif isinstance(cls, list) and len(cls) == 2:
                lane1_classes.append(Vehicle(name=cls[0], count=cls[1]))
            else:
                print(f"Skipping invalid class format: {cls}")

        lane1 = Lane(
            total=item["lane1"]["total"],
            classes=lane1_classes
        )

        lane2_classes = []
        for cls in item["lane2"]["classes"]:
            if isinstance(cls, dict) and 'class' in cls and 'count' in cls:
                lane2_classes.append(Vehicle(name=cls['class'], count=cls['count']))
            elif isinstance(cls, list) and len(cls) == 2:
                lane2_classes.append(Vehicle(name=cls[0], count=cls[1]))
            else:
                print(f"Skipping invalid class format: {cls}")

        lane2 = Lane(
            total=item["lane2"]["total"],
            classes=lane2_classes
        )
        
        sensor_record = SensorRecord(
            _id=item["_id"],
            sensor_id=item["sensor_id"],
            weather_bitmap=item["weather_bitmap"],
            mq_timestamp=item["mq_timestamp"],
            timezone=item["timezone"],
            timestamp=item["timestamp"],
            lane1=lane1,
            lane2=lane2,
        )
        records.append(sensor_record)
    
    return records


sensor_data = parse_sensor_data(file_path)

#arg1: sensor_data (default takes the full data set)
#args2: filter fn(default will return the given data set)
def filter_sensor_data(sensor_data: List[SensorRecord], condition_fn: Optional[Callable[[SensorRecord], bool]] = None) -> List[SensorRecord]:
    if condition_fn is None:
        return sensor_data
    filtered = []
    for record in sensor_data:
        if condition_fn(record):
            filtered.append(record)

    return filtered


def not_motorized(record: SensorRecord) -> bool:
    motorized_names = ["car", "motorbike", "truck"]
    match = False
    if (not record.lane1 or (record.lane1.total == 0)) and (not record.lane2 or (record.lane2.total == 0)):
        return False
    for lane in [record.lane1, record.lane2]:
        for vehicle in lane.classes:
            for name in motorized_names:
                if vehicle.name == name:
                    match = True
    if not match:
        print(lane)
        return True
    return False

def get_not_motorized(sensor_data: List[SensorRecord]) -> List[SensorRecord]:
    filtered = filter_sensor_data(sensor_data, not_motorized)
    return filtered

filtered = get_not_motorized(sensor_data)
print(filtered)

@dataclass
class Date:
    year: int
    month: int
    day: int
    hour: int

