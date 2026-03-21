# Command to run:
#	streamlit run scripts/web.py


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
from sensor_data import simulate_sensor_data

# 1. Simulierte Daten generieren
data = simulate_sensor_data(hours=24)

# 2. Streamlit-Beschriftung
st.title("Verkehrsdaten Analyse")

# 3. Durchschnittlicher Verkehr
avg_traffic = data['Traffic_Count'].mean()
st.write(f"Durchschnittlicher Verkehr pro Stunde: {avg_traffic:.2f}")

# 4. Peak-Traffic-Zeit
peak_time = data.loc[data['Traffic_Count'].idxmax()]['Timestamp']
peak_value = data['Traffic_Count'].max()
st.write(f"Höchster Verkehrswert von {peak_value} registriert um {peak_time}")

# 5. Anomalieerkennung
mean_traffic = data['Traffic_Count'].mean()
std_dev = data['Traffic_Count'].std()
anomalies = data[data['Traffic_Count'] > mean_traffic + 2 * std_dev]

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

# Speichern des Diagramms als Bild
plt.savefig("traffic_data_and_peaks.png")
st.image("traffic_data_and_peaks.png")

# 7. Visualisierung der Anomalien, falls vorhanden
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

    # Speichern des Diagramms als Bild
    plt.savefig("traffic_anomalies.png")
    st.image("traffic_anomalies.png")

# 8. Visualisierung der Stoßzeiten
plt.figure(figsize=(12, 6))
plt.plot(data['Timestamp'], data['Traffic_Count'], marker='o', linestyle='-', label='Verkehrszahl')
plt.axhline(y=data['Traffic_Count'].max(), color='blue', linestyle='--', label='Morgen Peak')
plt.axhline(y=data['Traffic_Count'].max(), color='green', linestyle='--', label='Nachmittag Peak')
plt.xlabel('Zeitpunkt')
plt.ylabel('Verkehrszahl')
plt.title('Verkehrstrends am Tag')
plt.legend()
plt.xticks(rotation=45)
plt.grid(True)
plt.tight_layout()

# Speichern des Diagramms als Bild
plt.savefig("traffic_trends.png")
st.image("traffic_trends.png")
