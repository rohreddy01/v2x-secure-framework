"""
V2X Communication Bridge — MQTT version
Replaces ZeroMQ with AWS EC2 Mosquitto broker.
Attack injection is applied inside V2XPublisher.publish()
so the scenario script doesn't need to change.
"""

import paho.mqtt.client as mqtt
import json
import threading
import time

EC2_IP    = "3.133.81.84"
MQTT_PORT = 1883

def build_v2x_message(instance_id, vehicle_id, position, speed, heading, intent):
    return json.dumps({
        "instance"  : instance_id,
        "vehicle_id": vehicle_id,
        "timestamp" : time.time(),
        "position"  : {"x": position[0], "y": position[1], "z": position[2]},
        "speed_kmh" : speed,
        "heading"   : heading,
        "intent"    : intent,
    })

class V2XPublisher:
    def __init__(self, instance_id, injector=None, data_logger=None):
        self.instance_id = instance_id
        self.topic       = f"v2x/instance_{instance_id.lower()}/bsm"
        self.msg_count   = 0
        self.injector    = injector       # AttackInjector or None
        self.data_logger = data_logger    # DataLogger or None

        self.client = mqtt.Client(client_id=f"v2x_pub_{instance_id}")
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.connect(EC2_IP, MQTT_PORT, keepalive=60)
        self.client.loop_start()
        time.sleep(0.5)

        # Start DoS flood if injector is configured for it
        if self.injector:
            self.injector.start_flood(self.client)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[V2X-{self.instance_id}] Publisher bound to "
                  f"tcp://{EC2_IP}:{MQTT_PORT} (MQTT)")
        else:
            print(f"[V2X-{self.instance_id}] Publisher connect failed rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        try:
            self.client.reconnect()
        except Exception:
            pass

    def publish(self, vehicle_id, position, speed, heading, intent):
        # Build raw message dict
        raw = {
            "instance"  : self.instance_id,
            "vehicle_id": str(vehicle_id),
            "timestamp" : time.time(),
            "position"  : {"x": position[0], "y": position[1], "z": position[2]},
            "speed_kmh" : speed,
            "heading"   : heading,
            "intent"    : intent,
        }

        # Pass through attack injector
        if self.injector:
            msg = self.injector.process(raw)
        else:
            msg = raw
            msg["is_attack"]   = 0
            msg["attack_type"] = "none"

        # Log to CSV before deciding whether to drop
        if self.data_logger and msg:
            self.data_logger.log(msg)
        elif self.data_logger and msg is None:
            # Log the dropped message too (DoS drop)
            dropped = dict(raw)
            dropped["is_attack"]   = 1
            dropped["attack_type"] = "dos"
            self.data_logger.log(dropped)

        # DoS drop — don't publish
        if msg is None:
            return

        self.client.publish(self.topic, json.dumps(msg), qos=1)
        self.msg_count += 1

    def close(self):
        if self.injector:
            self.injector.stop()
        self.client.loop_stop()
        self.client.disconnect()
        print(f"[V2X-{self.instance_id}] Publisher closed "
              f"({self.msg_count} messages sent)")


class V2XSubscriber:
    def __init__(self, instance_id, callback):
        self.instance_id = instance_id
        self.callback    = callback
        self._running    = False

        other = "b" if instance_id.upper() == "A" else "a"
        self.sub_topic = f"v2x/instance_{other}/#"

        print(f"[V2X-{instance_id}] Subscriber connected to "
              f"tcp://{EC2_IP}:{MQTT_PORT} (MQTT)")

        self.client = mqtt.Client(client_id=f"v2x_sub_{instance_id}")
        self.client.on_connect    = self._on_connect
        self.client.on_message    = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self.sub_topic)
        else:
            print(f"[V2X-{self.instance_id}] Subscriber connect failed rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        if self._running:
            try:
                self.client.reconnect()
            except Exception:
                pass

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if payload.get("instance", "").upper() == self.instance_id.upper():
                return
            self.callback(payload)
        except Exception as e:
            print(f"[V2X-{self.instance_id}] Receive error: {e}")

    def start(self):
        self._running = True
        self.client.connect(EC2_IP, MQTT_PORT, keepalive=60)
        self.client.loop_start()
        time.sleep(0.5)

    def stop(self):
        self._running = False
        self.client.loop_stop()
        self.client.disconnect()
