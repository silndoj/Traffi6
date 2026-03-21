import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sensor_data import simulate_sensor_data
import os

# Sicherstellen, dass das Verzeichnis existiert
if not os.path.exists("data"):
    os.makedirs("data")

# 1. Sensor-Daten abrufen (simuliert)
data = simulate_sensor_data(hours=24)
print("Simulierte Verkehrsdaten:")
print(data.head())

# 2. Analyse: Durchschnittlicher Verkehr pro Stunde
avg_traffic = data['Traffic_Count'].mean()
print(f"\nDurchschnittlicher Verkehr pro Stunde: {avg_traffic}")

# 3. Peak-Traffic-Zeit ermitteln
peak_time = data.loc[data['Traffic_Count'].idxmax()]['Timestamp']
peak_value = data['Traffic_Count'].max()
print(f"\nHöchster Verkehrswert von {peak_value} registriert um {peak_time}")

# 4. Visualisierung der Verkehrsdaten
plt.figure(figsize=(10, 5))
plt.plot(data['Timestamp'], data['Traffic_Count'], marker='o', linestyle='-', label='Verkehrszahl')
plt.axhline(y=peak_value, color='r', linestyle='--', label='Peak-Traffic')
plt.xlabel('Zeitpunkt')
plt.ylabel('Verkehrszahl')
plt.title('Stoßzeiten im Verkehr')
plt.legend()
plt.xticks(rotation=45)
plt.grid(True)
plt.tight_layout()
plt.show()

def detect_anomalies(data, threshold=2.0):
    """Erkennt ungewöhnliche Verkehrsspitzen basierend auf der Standardabweichung."""
    mean_traffic = data['Traffic_Count'].mean()
    std_dev = data['Traffic_Count'].std()

    # Bedingung für Anomalien
    anomalies = data[data['Traffic_Count'] > mean_traffic + threshold * std_dev]
    print("\nAnomalien im Verkehr (außergewöhnlich hohe Werte):")
    print(anomalies)

    # Visualisierung der Anomalien
    plt.figure(figsize=(10, 5))
    plt.plot(data['Timestamp'], data['Traffic_Count'], marker='o', linestyle='-', label='Verkehrszahl')
    plt.scatter(anomalies['Timestamp'], anomalies['Traffic_Count'], color='red', label='Anomalien', zorder=5)
    plt.xlabel('Zeitpunkt')
    plt.ylabel('Verkehrszahl')
    plt.title('Anomalie-Erkennung im Verkehr')
    plt.legend()
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

# Funktion aufrufen
detect_anomalies(data)

def analyze_daily_trends(data):
    """Analysiert Verkehrstrends und gibt Peak-Zeiten für morgen und nachmittags an."""
    morning_data = data[(data['Timestamp'].dt.hour >= 6) & (data['Timestamp'].dt.hour < 12)]
    afternoon_data = data[(data['Timestamp'].dt.hour >= 12) & (data['Timestamp'].dt.hour < 18)]

    morning_peak = morning_data['Traffic_Count'].max()
    afternoon_peak = afternoon_data['Traffic_Count'].max()

    print(f"\nMorgendliche Stoßzeit: {morning_peak} Verkehrszahl")
    print(f"Nachmittägliche Stoßzeit: {afternoon_peak} Verkehrszahl")

    # Visualisierung der Trends
    plt.figure(figsize=(10, 5))
    plt.plot(data['Timestamp'], data['Traffic_Count'], marker='o', linestyle='-', label='Verkehrszahl')
    plt.axhline(y=morning_peak, color='blue', linestyle='--', label='Morgen Peak')
    plt.axhline(y=afternoon_peak, color='green', linestyle='--', label='Nachmittag Peak')
    plt.xlabel('Zeitpunkt')
    plt.ylabel('Verkehrszahl')
    plt.title('Verkehrstrends am Tag')
    plt.legend()
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

# Funktion aufrufen
analyze_daily_trends(data)

# Speichern als PNG im aktuellen Verzeichnis
plt.savefig("traffic_trends.png")
plt.show()
# Speichern der Daten in einer CSV-Datei
data.to_csv("alo.csv", index=False)
print("\nDaten wurden in 'data/test.csv' gespeichert.")
