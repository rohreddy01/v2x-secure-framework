"""
Attack Injection Module — V2X Secure Communication Framework
Intercepts BSM messages before publishing and corrupts them
to simulate three cyber-attack types. Labels every message
with ground truth for AI training.
"""

import random
import time
import json
import threading
import collections

class AttackInjector:
    """
    Drop-in wrapper around a V2X message before it is published.
    Usage:
        injector = AttackInjector(attack_type="spoofing", intensity=0.5)
        corrupted_msg = injector.process(msg_dict)
        if corrupted_msg:
            publish(corrupted_msg)
    """

    ATTACK_NONE     = "none"
    ATTACK_SPOOFING = "spoofing"
    ATTACK_REPLAY   = "replay"
    ATTACK_DOS      = "dos"

    def __init__(self, attack_type="none", intensity=0.5, flood_rate=200):
        """
        attack_type : "none" | "spoofing" | "replay" | "dos"
        intensity   : 0.0–1.0  probability that any given message is attacked
        flood_rate  : junk packets per second for DoS flooding
        """
        assert attack_type in (self.ATTACK_NONE, self.ATTACK_SPOOFING,
                               self.ATTACK_REPLAY, self.ATTACK_DOS), \
            f"Unknown attack_type: {attack_type}"

        self.attack_type = attack_type
        self.intensity   = intensity
        self.flood_rate  = flood_rate

        # Replay buffer — keeps last N messages (up to 10 seconds at 4 msg/s)
        self._replay_buffer = collections.deque(maxlen=40)

        # Stats
        self.total_msgs    = 0
        self.attacked_msgs = 0

        # DoS flood thread (started lazily)
        self._flood_client  = None
        self._flood_thread  = None
        self._flood_running = False

    # ── Public API ──────────────────────────────────────────────────────────

    def process(self, msg_dict):
        """
        Takes a raw BSM dict, applies the configured attack,
        and returns the (possibly corrupted) dict with labels added.
        Returns None if the message should be dropped (DoS drop).
        """
        self.total_msgs += 1

        # Always keep a copy in replay buffer (before corruption)
        self._replay_buffer.append((time.time(), dict(msg_dict)))

        if self.attack_type == self.ATTACK_NONE:
            return self._label(msg_dict, attacked=False)

        # Roll the dice
        if random.random() > self.intensity:
            return self._label(msg_dict, attacked=False)

        # Apply attack
        self.attacked_msgs += 1

        if self.attack_type == self.ATTACK_SPOOFING:
            return self._apply_spoofing(msg_dict)

        elif self.attack_type == self.ATTACK_REPLAY:
            return self._apply_replay(msg_dict)

        elif self.attack_type == self.ATTACK_DOS:
            return self._apply_dos(msg_dict)

    def start_flood(self, mqtt_client):
        """Start DoS flooding thread (call after MQTT connection is up)."""
        if self.attack_type != self.ATTACK_DOS:
            return
        self._flood_client  = mqtt_client
        self._flood_running = True
        self._flood_thread  = threading.Thread(
            target=self._flood_loop, daemon=True)
        self._flood_thread.start()

    def stop(self):
        """Stop flooding thread and print stats."""
        self._flood_running = False
        print(f"[AttackInjector] type={self.attack_type} | "
              f"total={self.total_msgs} | "
              f"attacked={self.attacked_msgs} | "
              f"rate={self.attacked_msgs/max(1,self.total_msgs)*100:.1f}%")

    # ── Attack implementations ───────────────────────────────────────────────

    def _apply_spoofing(self, msg):
        """GPS Spoofing — falsify position by 10–50 m random offset."""
        corrupted = dict(msg)
        corrupted["position"] = dict(msg["position"])
        corrupted["position"]["x"] += random.uniform(-50, 50)
        corrupted["position"]["y"] += random.uniform(-50, 50)
        # Optionally falsify speed
        if random.random() < 0.3:
            corrupted["speed_kmh"] *= random.uniform(0.5, 1.5)
        return self._label(corrupted, attacked=True)

    def _apply_replay(self, msg):
        """Replay Attack — re-send a stale message (3–10 seconds old)."""
        now = time.time()
        stale_window = [
            m for (ts, m) in self._replay_buffer
            if 3.0 <= now - ts <= 10.0
        ]
        if not stale_window:
            # No stale message available — send current but flagged
            return self._label(msg, attacked=True)

        replayed = dict(random.choice(stale_window))
        replayed["timestamp"] = now   # re-stamp as current
        return self._label(replayed, attacked=True)

    def _apply_dos(self, msg):
        """Denial of Service — drop this legitimate message (return None)."""
        return None   # caller should not publish

    def _flood_loop(self):
        """Background thread that floods the broker with junk."""
        import paho.mqtt.client as mqtt
        flood = mqtt.Client(client_id="v2x_dos_flood")
        try:
            from v2x_bridge import EC2_IP, MQTT_PORT
            flood.connect(EC2_IP, MQTT_PORT, keepalive=10)
            flood.loop_start()
            interval = 1.0 / max(1, self.flood_rate)
            while self._flood_running:
                junk = json.dumps({
                    "instance": "ATTACK",
                    "vehicle_id": "dos",
                    "timestamp": time.time(),
                    "junk": "x" * 256
                })
                flood.publish("v2x/attack/dos", junk, qos=0)
                time.sleep(interval)
            flood.loop_stop()
            flood.disconnect()
        except Exception as e:
            print(f"[AttackInjector] Flood error: {e}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _label(self, msg, attacked):
        """Add ground-truth labels to the message dict."""
        labeled = dict(msg)
        labeled["is_attack"]   = 1 if attacked else 0
        labeled["attack_type"] = self.attack_type if attacked else "none"
        return labeled
