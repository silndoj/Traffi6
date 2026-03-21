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

# 4. Anomalieerkennung
mean_traffic = data['Traffic_Count'].mean()
std_dev = data['Traffic_Count'].std()
anomalies = data[data['Traffic_Count'] > mean_traffic + 2 * std_dev]

# 5. Analyse von Stoßzeiten
morning_data = data[(data['Timestamp'].dt.hour >= 6) & (data['Timestamp'].dt.hour < 12)]
afternoon_data = data[(data['Timestamp'].dt.hour >= 12) & (data['Timestamp'].dt.hour < 18)]

morning_peak = morning_data['Traffic_Count'].max()
afternoon_peak = afternoon_data['Traffic_Count'].max()

print(f"\nMorgendliche Stoßzeit: {morning_peak} Verkehrszahl")
print(f"Nachmittägliche Stoßzeit: {afternoon_peak} Verkehrszahl")

# Visualisierungen am Ende
# 6. Visualisierung der Verkehrsdaten
plt.figure(figsize=(12, 6))
plt.plot(data['Timestamp'], data['Traffic_Count'], marker='o', linestyle='-', label='Verkehrszahl')
plt.axhline(y=peak_value, color='red', linestyle='--', label='Peak-Traffic')
plt.xlabel('Zeitpunkt')
plt.ylabel('Verkehrszahl')
plt.title('Verkehrsdaten und Peak-Zeiten')
plt.legend()
plt.xticks(rotation=45)
plt.grid(True)
plt.tight_layout()
plt.show()

# 7. Visualisierung der Anomalien
if not anomalies.empty:
    plt.figure(figsize=(12, 6))
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

# 8. Visualisierung der Stoßzeiten
plt.figure(figsize=(12, 6))
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

# Speichern der Daten in einer CSV-Datei
data.to_csv("data/simulated_traffic_data.csv", index=False)
print("\nDaten wurden in 'data/simulated_traffic_data.csv' gespeichert.")
