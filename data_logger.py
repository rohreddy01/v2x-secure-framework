"""
Data Logger — saves every V2X BSM to CSV with ground truth labels.
One CSV file per simulation run, named by timestamp, scenario, and attack type.
"""
import csv
import os
import time

FIELDS = [
    "timestamp", "instance", "scenario", "vehicle_id",
    "pos_x", "pos_y", "pos_z",
    "speed_kmh", "heading", "intent",
    "is_attack", "attack_type"
]

class DataLogger:
    def __init__(self, instance_id, attack_type="none", scenario="unknown", output_dir="~/v2x_data"):
        self.instance_id = instance_id
        self.attack_type = attack_type
        self.scenario    = scenario
        self.msg_count   = 0
        output_dir = os.path.expanduser(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        run_time  = time.strftime("%Y%m%d_%H%M%S")
        filename  = f"v2x_{instance_id}_{scenario}_{attack_type}_{run_time}.csv"
        self.path = os.path.join(output_dir, filename)
        self._file   = open(self.path, "w", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=FIELDS)
        self._writer.writeheader()
        print(f"[DataLogger] Logging to {self.path}")

    def log(self, msg):
        try:
            row = {
                "timestamp"  : msg.get("timestamp", time.time()),
                "instance"   : msg.get("instance", ""),
                "scenario"   : self.scenario,
                "vehicle_id" : msg.get("vehicle_id", ""),
                "pos_x"      : msg.get("position", {}).get("x", 0),
                "pos_y"      : msg.get("position", {}).get("y", 0),
                "pos_z"      : msg.get("position", {}).get("z", 0),
                "speed_kmh"  : msg.get("speed_kmh", 0),
                "heading"    : msg.get("heading", 0),
                "intent"     : msg.get("intent", ""),
                "is_attack"  : msg.get("is_attack", 0),
                "attack_type": msg.get("attack_type", "none"),
            }
            self._writer.writerow(row)
            self._file.flush()
            self.msg_count += 1
        except Exception as e:
            print(f"[DataLogger] Log error: {e}")

    def close(self):
        self._file.close()
        print(f"[DataLogger] Saved {self.msg_count} rows → {self.path}")
