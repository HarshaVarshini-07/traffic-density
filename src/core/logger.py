import csv
import time
import os
from datetime import datetime

class DataLogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join(log_dir, f"traffic_log_{timestamp}.csv")
        
        # Initialize file with headers
        with open(self.filename, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Lane_1", "Lane_2", "Lane_3", "Lane_4", "Light_States", "Total_Vehicles"])

    def log(self, lane_counts, light_states):
        """
        Logs the current state to the CSV file.
        """
        with open(self.filename, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%H:%M:%S.%f")[:-3], # High precision time
                lane_counts[0],
                lane_counts[1],
                lane_counts[2],
                lane_counts[3],
                "".join(light_states),
                sum(lane_counts)
            ])
