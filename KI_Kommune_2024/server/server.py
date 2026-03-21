from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from dataclasses import dataclass
import folium
from typing import List
from graph import Graph, get_large_graph


# Define the server address and port
HOST = 'localhost'
PORT = 8000

# define graph and image urls
graph = get_large_graph()
car_icon_url = "car.png"

class Sensor:
	def __init__(self, entity_id, value, timestamp, count, sensor_type):
		self.entity_id = entity_id  # Die eindeutige ID des Sensors
		self.value = value  # Der Wert (z.B. gemessene Geschwindigkeit oder Anzahl der Fahrzeuge)
		self.timestamp = timestamp  # Der Zeitstempel der Messung
		self.count = count  # Die Anzahl des Typs (z.B. 5 Autos)
		self.type = sensor_type  # Der Typ des Objekts (z.B. "Car", "Bus", "Bike")

	def __repr__(self):
		# Gibt eine benutzerfreundliche Darstellung des Sensor-Objekts zurück
		return (f"Sensor(entity_id={self.entity_id}, value={self.value}, "
				f"timestamp={self.timestamp}, count={self.count}, type={self.type})")


def generate_map():
	sensor_list = graph.get_sensor_list()
	coordinates = [([coordinate["X"], coordinate["Y"]], coordinate["ID"]) for coordinate, _ in sensor_list]

	my_map = folium.Map(location=[49.00587, 8.40162], zoom_start=15)

	# Add all coordinates as CircleMarkers
	for coord, id_ in coordinates:
		# create popup html
		popup_html = f"""
		<div style="width: 200px; padding: 10px;">
			<h4 style="margin-bottom: 5px;">{id_}</h4>
			<p style="margin: 0; color: gray;">{coord[0]}, {coord[1]}</p>
		</div>
		"""
		tooltip_text = f"{id_}: {coord[0]}, {coord[1]}"


		# create and add the marker for the sensor
		folium.CircleMarker(
			location=coord,
			radius=5,
			color="blue",
			fill=True,
			fill_color="blue",
			popup=folium.Popup(popup_html, max_width=300),
			tooltip=tooltip_text
		).add_to(my_map)
	
	# Save the map to an HTML file
	my_map.save("map.html")


def query_api() -> list[Sensor]:
	""" Ilies entry point"""
	pass


def enrich_map():
	""" Silvesters entry point"""
	# add traffic members
	return graph.get_participants_positions()


def get_data(handler):
	# get sensor data from api
	sensors = query_api()

	# simulate traffic
	graph.pass_time()

	# paint points to map
	response_data = enrich_map()

	# print sensor data
	# graph.print_sensor_data()

	# Send response status
	handler.send_response(200)

	# Set headers for JSON response
	handler.send_header("Content-Type", "application/json")
	handler.end_headers()

	# Write JSON response
	json_response = json.dumps(response_data)
	handler.wfile.write(json_response.encode('utf-8'))


class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/data":
            get_data(self)
        else:
            super().do_GET()

# generate the base map html file
generate_map()

# Create a handler to handle HTTP requests
handler = CustomHTTPRequestHandler

# Create the HTTP server
httpd = HTTPServer((HOST, PORT), handler)

print(f"Serving HTTP on {HOST}:{PORT}...")

# Run the server
httpd.serve_forever()
