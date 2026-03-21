import requests
import os
import time
import sys
import json
from server import Sensor

#
# Uebergeordnete Verzeichnis zum sys.path
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'server')))

# # Jetzt sollte der Import funktionieren
# from server.server import Sensor

api_key = os.getenv('API_KEY')
if api_key is None:
	raise ValueError("API_KEY ist nicht gesetzt. Bitte die Umgebungsvariable API_KEY festlegen.")


# Konfiguriere die API-URL
BASE_URL = "https://apis.smartcity.hn/bildungscampus/iotplatform/trafficsensor/v1"

auth_group = "trafficsensor_devices"

def query_api(auth_group: str, page: int = 0) -> list:
	# Endpoint für die Entity-ID-Anfrage
	url = f"{BASE_URL}/authGroup/{auth_group}/entityId"

	# Parameter und API-Schlüssel als Query-Parameter setzen
	params = {
		'x-apikey': api_key,
		'page': page  # Seite für Paginierung festlegen
	}

	# API-Request senden
	try:
		response = requests.get(url, params=params)
		response.raise_for_status()  # Prüft auf Fehler im Response
	except requests.exceptions.RequestException as e:
		print(f"Fehler bei der API-Anfrage: {e}")
		return []

	# Daten verarbeiten
	data = response.json()

	# Ausgabe der gesamten Antwort zur Überprüfung
	print("Vollständige API-Antwort:")
	print(data)

	# Extrahiere `entities`, falls vorhanden
	entities = data.get('entities', [])

	# Liste der Sensor-Objekte erstellen
	sensors = []

	for entity in entities:
		entity_id = entity.get('entityId')
		value = entity.get('value')
		timestamp = entity.get('timestamp')
		count = entity.get('count', 1)  # Falls nicht vorhanden, setze default auf 1
		sensor_type = entity.get('type', "Unknown")  # Falls nicht vorhanden, setze default auf "Unknown"

		# Sensor-Objekt erstellen und zur Liste hinzufügen
		if entity_id and value and timestamp:
			sensor = Sensor(entity_id, value, timestamp, count, sensor_type)
			sensors.append(sensor)
	print("Liste der Sensoren:")
	for sensor in sensors:
		print(sensor)  # Dies wird die __repr__-Methode der Sensor-Klasse aufrufen
	return sensors

# if __name__ == "__main__":
#     auth_group = "trafficsensor_devices"  # Beispiel-Authentifizierungsgruppe
#     page = 0  # Startseite für die Paginierung

#     # Sensoren von der API abrufen
#     sensors = query_api(auth_group, page)
#     # Sensor-Objekte ausgeben
#     print("Liste der Sensoren:")
#     for sensor in sensors:
#         print(sensor)  # Dies wird die __repr__-Methode der Sensor-Klasse aufrufen
