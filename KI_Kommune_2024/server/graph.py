from typing import List, Dict
import osmnx as ox
import math
import random
import time
import diagram
class Participant:
    #adds new participant to graph
    def __init__(self, graph, node_id, type, id=0, meters_per_sec=10):
        node = graph.nodes[node_id]
        self.graph = graph
        self.x = node.x
        self.y = node.y
        self.type = type
        self.cur = node
        self.target = node
        self.passed_meters = 0 #distance from start
        self.distance_meters = 0 #distance to target
        self.id = id #some id to ident participants
        self.meters_per_sec = meters_per_sec
        self.total_dist = 1 #some init val to avoid zero div
        self.total_meters = 1#some init val to avoid zero div

    #participant changes destination goal(used when prev destionation was reached)
    def new_target(self):
        possible_targets = [neighbor for neighbor in self.target.neighbors if neighbor.id != self.cur.id]
        if not possible_targets:
            self.distance_meters = 0
            self.passed_meters = 0
            return
        weights = [neighbor.weight for neighbor in possible_targets]
        self.cur = self.target
        self.target = random.choices(possible_targets, weights=weights, k=1)[0]

        self.x = self.target.x
        self.y = self.target.y
        self.passed_meters = 0
        self.passed_coords = 0

        dx = self.target.x - self.cur.x
        dy = self.target.y - self.cur.y
        self.dx_coords = dx
        self.dy_coords = dy
        total_distance = math.hypot(dx, dy)  # Edge length
        if total_distance != 0:
            self.unit_dx = dx / total_distance
            self.unit_dy = dy / total_distance
        else:
            self.unit_dx = 0
            self.unit_dy = 0
        dx_meters = dx * 73 * 1600
        dy_meters = dy * 111.32 * 1600
        self.distance_meters = math.hypot(dx_meters, dy_meters)
        self.total_meters = self.distance_meters

    #participant moves the amount of his speed * time
    def move(self, time=1, speed_scala=1):
        if self.distance_meters <= 0:
            self.new_target()
        if self.distance_meters <= 0:
            return
        self.distance_meters -= time * self.meters_per_sec * speed_scala
        self.passed_meters += time * self.meters_per_sec * speed_scala

        if self.distance_meters < 0:
            self.distance_meters = 0
            self.x = self.target.x
            self.y = self.target.y
        else:
            self.x = self.cur.x + self.dx_coords * (self.passed_meters / self.total_meters)
            self.y = self.cur.y + self.dy_coords * (self.passed_meters / self.total_meters)

        #print("distance to last node:", self.passed_meters)
        #print("distance to next node:", self.distance_meters)
        #
        #print("x:", self.x, ", y:", self.y)


#(sensor)
#use node.connect() to create edges in a graph
#edges go in both directions
class Node:
    def __init__(self, graph, id, x, y, is_sensor=True):
        self.graph = graph
        self.x = x
        self.y = y
        self.id = id
        self.neighbors = []
        self.graph.nodes[id] = self
        self.is_sensor = is_sensor
        self.distance_to_center = 0
        self.weight = 1

    #if the node is not a sensor returns an empty list
    #returns a list of the participants in the radius if it is a sensor
    #currently a sensor has a 360 fov
    def detect(self, radius=10):
        detects = []
        if not self.is_sensor:
            return detects
        for participant in self.graph.participants:
            if participant.target.id == self.id and participant.distance_meters <= radius:
                detects.append(participant)
            elif participant.cur.id == self.id and participant.passed_meters <= radius:
                detects.append(participant)
        return detects

    #creates an edge between two nodes
    def connect(self, node):
        if any(neighbor.id == node.id for neighbor in self.neighbors):
            return
        self.neighbors.append(node)
        node.neighbors.append(self)

class Graph:
    #set the speed to control the speed of the simulation
    #(1-> 1simulation sec/1real sec)
    #too fast speeds will be buggy for small maps
    def __init__(self,
                 #[(type, count, meters per sec), <more types>
                 participants=[("car", 10, 10)],
                 #simulation speed
                 speed=1,
                 #where is the simulation:
                 x=49.007706, y=8.394864, radius_meters=400):
        self.speed = speed
        self.nodes = {}
        self.participants = []
        self.center_x = x
        self.center_y = y
        self.day_time = 0

        self.add_intersections(x, y, radius_meters)
        self.compute_node_distances_and_weights()
        node_ids = list(self.nodes.keys())
        id = 0
        for participant in participants:
            type, count, meters_per_sec = participant
            i = 0
            while i < count:
                random_node_id = random.choice(node_ids)
                participant_obj = Participant(self, random_node_id, type, id, meters_per_sec=meters_per_sec)
                id += 1
                i += 1
                self.participants.append(participant_obj)

    def add_intersections(self, center_lat, center_lon, radius_meters=400):
        G = ox.graph_from_point((center_lat, center_lon), dist=radius_meters, network_type='drive')
        osm_id_to_node = {}
        for node_id, node_data in G.nodes(data=True):
            unique_id = f"node_{node_id}"
            lat = node_data['y']
            lon = node_data['x']
            if unique_id not in self.nodes:
                node = Node(self, unique_id, lat, lon)
                osm_id_to_node[node_id] = node
                self.nodes[unique_id] = node

        for u, v, data in G.edges(data=True):
            node_u = osm_id_to_node.get(u)
            node_v = osm_id_to_node.get(v)
            if node_u and node_v:
                node_u.connect(node_v)

    def compute_node_distances_and_weights(self):
        max_distance = 0
        for node in self.nodes.values():
            dx = (node.x - self.center_x) * 73 * 1600
            dy = (node.y - self.center_y) * 111.32 * 1600
            distance = math.hypot(dx, dy)
            node.distance_to_center = distance
            if distance > max_distance:
                max_distance = distance

        for node in self.nodes.values():
            normalized_distance = node.distance_to_center / max_distance
            node.weight = 1 + 2 * (1 - normalized_distance)  # from 3(center)-1(outer)

    def get_detected_participants_positions(self, sensor_meter_radius=10, from_print=False):
        detected_positions = []
        sensor_list = self.get_sensor_list(sensor_meter_radius, from_print)
        detected_ids = set()
        for sensor_info, detected_participants in sensor_list:
            for participant in detected_participants:
                detected_ids.add(participant["ID"])
        for participant in self.participants:
            if participant.id in detected_ids and participant.is_active():
                participant_info = {
                    'TYPE': participant.type,
                    'ID': participant.id,
                    'X': participant.x,
                    'Y': participant.y,
                    'Current Node': participant.cur.id,
                    'Target Node': participant.target.id,
                    'Distance to Target': participant.distance_meters,
                }
                detected_positions.append(participant_info)
        return detected_positions

    def get_participants_positions(self):
        positions = []
        for participant in self.participants:
            participant_info = {
                'TYPE': participant.type,
                'ID': participant.id,
                'X': participant.x,
                'Y': participant.y,
                'Current Node': participant.cur.id,
                'Target Node': participant.target.id,
                'Distance to Target': participant.distance_meters,
            }
            positions.append(participant_info)
        return positions

    def print_participants_positions(self):
        positions = self.get_participants_positions()
        print("Current Participants Positions:")
        for participant_info in positions:
            print(f"Type: {participant_info['TYPE']}, ID: {participant_info['ID']}, "
                  f"X: {participant_info['X']}, Y: {participant_info['Y']}, "
                  f"Current Node: {participant_info['Current Node']}, "
                  f"Target Node: {participant_info['Target Node']}, "
                  f"Distance to Target: {participant_info['Distance to Target']:.2f} meters")
        print("-" * 40)

    def get_sensor_list(self, sensor_meter_radius=10):
        sensor_list = []
        for node in self.nodes.values():
            if node.is_sensor:
                detects = node.detect(sensor_meter_radius)
                detected_participants = [
                    {
                        "TYPE": participant.type,
                        "ID": participant.id,
                        "X": participant.x,
                        "Y": participant.y,
                    }
                    for participant in detects
                ]
                sensor_info = {
                    "ID": node.id,
                    "X": node.x,
                    "Y": node.y,
                }
                sensor_list.append((sensor_info, detected_participants))
        return sensor_list

    def print_sensor_data(self, radius=10):
        sensor_list = self.get_sensor_list(radius)
        for sensor_info, detected_participants in sensor_list:
            if not detected_participants:
                continue  # Use continue instead of return
            print(f"Sensor ID: {sensor_info['ID']}")
            print(f"  Coordinates: ({sensor_info['X']}, {sensor_info['Y']})")
            if detected_participants:
                print("  Detected Participants:")
                for participant in detected_participants:
                    print(f"    - Type: {participant['TYPE']}, "
                          f"ID: {participant['ID']}, "
                          f"Coordinates: ({participant['X']}, {participant['Y']})")
            else:
                print(" no participants in sensor range")
            print("-" * 40)

    def add_node(self, new_node):
        self.nodes[new_node.id] = new_node

    #advance simulation by 1 simulation second
    def pass_time(self, time=1):
        self.day_time += time
        self.day_time %= 24
        for participant in self.participants:
            participant.move(time, self.speed)

    #prints the current cars in sensor ranges
    #old version, of print_sensor_data, should print the same cases as print_sensor_data
    def print_detects(self, range=10):
        for node in self.nodes.values():
            detects = node.detect(range)
            for participant in detects:
                print(node.id, ": ", participant.type, "(id: ", participant.id, ")")

def get_large_graph():
    participant_list = [("car", 400, 10), ("truck", 20, 10), ("foot", 40, 1), ("bicycle", 40, 2), ("motor_bike", 40, 10)]
    graph = Graph(speed=5, participants=participant_list, x=49.00587, y=8.40162, radius_meters=3000)
    return graph



if __name__ == '__main__':
    #graph = Graph()
    graph = get_large_graph()
    #graph.print_detects()
    passed_time = 0
    ids_in_range = diagram.get_ids(graph)
    all_time_stamps = []
    while 1:
        all_time_stamps.append(diagram.filter_sensors(graph, ids_in_range))
        diagram.animation1(all_time_stamps)

        graph.pass_time()
        #graph.print_participants_positions()
        #graph.print_sensor_data(10)

        passed_time += 1
        print("passed time: ", passed_time)
        time.sleep(1)




