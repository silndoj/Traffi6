import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def simulate_sensor_data(hours=24):
    """Simuliert Verkehrsdaten für eine bestimmte Anzahl an Stunden."""
    timestamps = [datetime.now() - timedelta(hours=i) for i in range(hours)]
    traffic_counts = np.random.randint(50, 200, size=hours)  # Zufällige Verkehrszahlen

    data = pd.DataFrame({
        'Timestamp': timestamps,
        'Traffic_Count': traffic_counts
    })
    return data

# Testfunktion
if __name__ == "__main__":
    simulated_data = simulate_sensor_data()
    print(simulated_data.head())
