import pandas as pd
import matplotlib.pyplot as plt
from sensor_data import simulate_sensor_data

# # Beispiel-Daten erstellen
# data = {
#     'Stunde': range(24),
#     'Verkehr': np.random.randint(50, 200, size=24)  # Zufällige Verkehrszahlen
# }
# df = pd.DataFrame(data)

# # Daten analysieren und ausgeben
# print("Verkehrsdaten über 24 Stunden:")
# print(df)

# # Durchschnittlichen Verkehr berechnen
# avg_traffic = df['Verkehr'].mean()
# print(f"\nDurchschnittlicher Verkehr pro Stunde: {avg_traffic}")


# import matplotlib.pyplot as plt

# # Daten visualisieren
# plt.plot(df['Stunde'], df['Verkehr'], marker='o', linestyle='-')
# plt.xlabel('Stunde')
# plt.ylabel('Verkehr')
# plt.title('Verkehrsdaten über den Tag')
# plt.grid(True)
# plt.show()




# 1. Sensor-Daten abrufen (simuliert)
data = simulate_sensor_data(hours=24)
print("Simulierte Verkehrsdaten:")
print(data.head())

# 2. Analyse: Durchschnittlicher Verkehr pro Stunde
avg_traffic = data['Traffic_Count'].mean()
print(f"\nDurchschnittlicher Verkehr pro Stunde: {avg_traffic}")

# 3. Visualisierung der Verkehrsdaten
plt.figure(figsize=(10, 5))
plt.plot(data['Timestamp'], data['Traffic_Count'], marker='o', linestyle='-')
plt.xlabel('Zeitpunkt')
plt.ylabel('Verkehrszahl')
plt.title('Simulierte Verkehrsdaten über 24 Stunden')
plt.xticks(rotation=45)
plt.grid(True)
plt.tight_layout()
plt.show()

# Speichern der Daten in einer CSV-Datei
data.to_csv("data/simulated_traffic_data.csv", index=False)
print("\nDaten wurden in 'data/simulated_traffic_data.csv' gespeichert.")
