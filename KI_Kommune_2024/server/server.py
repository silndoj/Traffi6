from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os

from data_loader import load_and_group, compute_traffic_volumes
from sensor_mapping import load_or_create_mapping
from replay_engine import ReplayEngine

# Define the server address and port
HOST = 'localhost'
PORT = 8000


def generate_map():
    if os.path.exists("map.html"):
        return
    try:
        import folium
        my_map = folium.Map(location=[49.00587, 8.40162], zoom_start=15)
        my_map.save("map.html")
    except ImportError:
        print("Warning: folium not installed and map.html not found. Map will not display.")


def get_data(handler):
    timestamp, markers = engine.advance()

    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()

    json_response = json.dumps(markers)
    handler.wfile.write(json_response.encode('utf-8'))


class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/data":
            get_data(self)
        else:
            super().do_GET()


# --- Startup: load data and initialize replay engine ---

csv_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data.csv')
csv_path = os.path.abspath(csv_path)

print(f"Loading CSV from {csv_path}...")
time_steps = load_and_group(csv_path)
traffic_volumes = compute_traffic_volumes(csv_path)

sensor_ids = list(traffic_volumes.keys())
sensor_positions = load_or_create_mapping(sensor_ids, traffic_volumes)

engine = ReplayEngine(time_steps, sensor_positions)

print(f"Sensors loaded: {len(sensor_positions)}")
print(f"Time steps: {len(time_steps)}")
if time_steps:
    print(f"Time range: {time_steps[0][0]} -> {time_steps[-1][0]}")

# Generate the base map HTML file
generate_map()

# Create and start the HTTP server
handler = CustomHTTPRequestHandler
httpd = HTTPServer((HOST, PORT), handler)

print(f"Serving HTTP on {HOST}:{PORT}...")
httpd.serve_forever()
