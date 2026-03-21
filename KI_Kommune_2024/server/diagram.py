import matplotlib.pyplot as plt
from itertools import chain

def get_ids(graph, x=49.00587, y=8.40162, radius=100):
	diff = (abs(49.005909 - 49.00587) / 100)
	diff = radius * diff
	xmin = x - diff
	xmax = x + diff
	ymin = y - (diff * 100)
	ymax = y + (diff * 100)
	ids = []
	sensors = graph.get_sensor_list()
	for sensor in sensors:
		sensor_x = sensor[0]["X"]
		sensor_y = sensor[0]["Y"]
		in_y_range = ymin <= sensor_y <= ymax
		in_x_range = xmin <= sensor_x <= xmax
		if in_x_range:
			print("y min:", ymin)
			print("y max:", ymax)
			print("y:", y)
			ids.append(sensor[0]["ID"])
	return ids

def filter_sensors(graph, id_list):
	filtered_sensords = []
	all_sensors = graph.get_sensor_list()
	for sensor in all_sensors:
		if sensor[0]["ID"] in id_list and len(sensor[1]):
			filtered_sensords.append(sensor[1])
	filtered_sensords = list(chain.from_iterable(filtered_sensords))
	return filtered_sensords

def animation1(time_stamps):
	i = 0
	all_counts = []
	for time_stamp in time_stamps:
		print("time stamp", i, ":")
		print("  Detected Participants:")
		counts = {}
		for detection in time_stamp:
			detection_type = detection['TYPE']
			if detection_type not in counts:
				counts[detection_type] = 1
			else:
				counts[detection_type] += 1
			# print(f"    - Type: {detection['TYPE']}, "
			# 		f"ID: {detection['ID']}, "
			# 		f"Coordinates: ({detection['X']}, {detection['Y']})")
		i += 1
		all_counts.append(counts)
	if not (i % 20):
		plot_all_counts(all_counts)
	print(all_counts)

#Visz

def plot_all_counts(all_counts):
    # Collect all unique detection types
    detection_types = set()
    for counts in all_counts:
        detection_types.update(counts.keys())

    # Initialize a dictionary to hold counts over time for each detection type
    counts_over_time = {dtype: [] for dtype in detection_types}

    # Populate counts_over_time with counts from all_counts
    for counts in all_counts:
        for dtype in detection_types:
            counts_over_time[dtype].append(counts.get(dtype, 0))

    # Generate time steps based on the length of all_counts
    time_steps = list(range(len(all_counts)))

    # Plot the counts for each detection type over time
    plt.figure(figsize=(12, 6))
    for dtype in sorted(detection_types):
        plt.plot(time_steps, counts_over_time[dtype], marker='o', label=dtype)

    # Add labels, title, and legend to the plot
    plt.xlabel('Time Step')
    plt.ylabel('Count')
    plt.title('Counts of Detection Types Over Time')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

















