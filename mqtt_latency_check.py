"""
Measures one-way message latency from Instance A to Instance B
through the AWS EC2 MQTT broker.
Listens on v2x/instance_a/bsm and calculates delay between
the send timestamp in the message and the time it is received here.
"""

import paho.mqtt.client as mqtt
import json
import time
import statistics

EC2_IP    = "3.133.81.84"
MQTT_PORT = 1883
NUM_MSGS  = 50   # how many messages to collect before printing stats

latencies = []

def on_message(client, userdata, msg):
    recv_time = time.time()
    try:
        payload    = json.loads(msg.payload.decode())
        send_time  = payload.get("timestamp")
        if send_time:
            latency_ms = (recv_time - send_time) * 1000
            latencies.append(latency_ms)
            print(f"  msg {len(latencies):3d} | latency = {latency_ms:.1f} ms")

            if len(latencies) >= NUM_MSGS:
                print(f"\n{'='*40}")
                print(f"  Results after {NUM_MSGS} messages")
                print(f"{'='*40}")
                print(f"  Min    : {min(latencies):.1f} ms")
                print(f"  Max    : {max(latencies):.1f} ms")
                print(f"  Mean   : {statistics.mean(latencies):.1f} ms")
                print(f"  Median : {statistics.median(latencies):.1f} ms")
                print(f"  StdDev : {statistics.stdev(latencies):.1f} ms")
                print(f"{'='*40}")
                client.disconnect()
    except Exception as e:
        print(f"Error: {e}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe("v2x/instance_a/bsm")
        print("Connected to EC2 broker. Waiting for Instance A messages...")
        print("(Make sure Instance A simulation is running)\n")

client = mqtt.Client(client_id="latency_checker")
client.on_connect = on_connect
client.on_message = on_message
client.connect(EC2_IP, MQTT_PORT)
client.loop_forever()
