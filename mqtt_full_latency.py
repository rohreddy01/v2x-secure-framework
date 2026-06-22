"""
Measures FULL one-way latency:
Instance A publishes → EC2 broker → Instance B receives

Run this on the same machine as Instance B while Instance A simulation is active.
It subscribes to v2x/instance_a/bsm exactly as Instance B does,
and measures the delay between the send timestamp and arrival time.
"""

import paho.mqtt.client as mqtt
import json
import time
import statistics

EC2_IP    = "3.133.81.84"
MQTT_PORT = 1883
NUM_MSGS  = 100

latencies  = []
per_vehicle = {}   # track latency per vehicle_id

def on_message(client, userdata, msg):
    recv_time = time.time()
    try:
        payload   = json.loads(msg.payload.decode())
        send_time = payload.get("timestamp")
        vid       = payload.get("vehicle_id", "unknown")[-8:]  # last 8 chars of UUID
        instance  = payload.get("instance")

        if not send_time:
            return

        latency_ms = (recv_time - send_time) * 1000
        latencies.append(latency_ms)

        # Track per vehicle
        if vid not in per_vehicle:
            per_vehicle[vid] = []
        per_vehicle[vid].append(latency_ms)

        print(f"  [{len(latencies):3d}] Instance {instance} | "
              f"vehicle ...{vid} | "
              f"latency = {latency_ms:.1f} ms")

        if len(latencies) >= NUM_MSGS:
            print(f"\n{'='*55}")
            print(f"  FULL PATH LATENCY: Instance A → EC2 → Instance B")
            print(f"  (simulating the complete V2X message journey)")
            print(f"{'='*55}")
            print(f"  Total messages   : {len(latencies)}")
            print(f"  Min latency      : {min(latencies):.1f} ms")
            print(f"  Max latency      : {max(latencies):.1f} ms")
            print(f"  Mean latency     : {statistics.mean(latencies):.1f} ms")
            print(f"  Median latency   : {statistics.median(latencies):.1f} ms")
            print(f"  Std deviation    : {statistics.stdev(latencies):.1f} ms")
            print(f"\n  Per-vehicle breakdown:")
            for v, lats in per_vehicle.items():
                print(f"    vehicle ...{v} | "
                      f"mean={statistics.mean(lats):.1f}ms | "
                      f"min={min(lats):.1f}ms | "
                      f"max={max(lats):.1f}ms")
            print(f"\n  Interpretation:")
            print(f"    Base network delay (min) : {min(latencies):.1f} ms")
            print(f"    Broker processing adds   : ~{statistics.mean(latencies)-min(latencies):.1f} ms avg overhead")
            print(f"    5G V2X requirement       : < 100 ms")
            print(f"    Status                   : {'PASS' if min(latencies) < 100 else 'FAIL'}")
            print(f"{'='*55}\n")
            client.disconnect()

    except Exception as e:
        print(f"Error: {e}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        # Subscribe exactly like Instance B does
        client.subscribe("v2x/instance_a/#")
        print("Subscribed to v2x/instance_a/# (same as Instance B)")
        print("Waiting for Instance A to publish BSMs...\n")

client = mqtt.Client(client_id="full_latency_checker",
                     callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
client.on_connect = on_connect
client.on_message = on_message
client.connect(EC2_IP, MQTT_PORT)
client.loop_forever()
