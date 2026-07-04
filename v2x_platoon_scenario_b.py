# -*- coding: utf-8 -*-
"""
V2X Cooperative Platoon Scenario - Instance B
Run with:
  python opencda.py -t v2x_platoon_scenario -v 0.9.12
  python opencda.py -t v2x_platoon_scenario -v 0.9.12 --attack spoofing
  python opencda.py -t v2x_platoon_scenario -v 0.9.12 --attack replay
  python opencda.py -t v2x_platoon_scenario -v 0.9.12 --attack dos
"""

import sys
import os
import argparse
import carla

sys.path.insert(0, '/home/umd-user')

from v2x_bridge import V2XPublisher, V2XSubscriber
from attack_injector import AttackInjector
from data_logger import DataLogger

import opencda.scenario_testing.utils.sim_api as sim_api
import opencda.scenario_testing.utils.customized_map_api as map_api
from opencda.core.common.cav_world import CavWorld
from opencda.scenario_testing.evaluations.evaluate_manager import EvaluationManager

received_v2x = []

def on_v2x_receive(msg):
    inst       = msg["instance"]
    vid        = msg["vehicle_id"]
    spd        = msg["speed_kmh"]
    intent_str = msg["intent"]
    px         = msg["position"]["x"]
    py         = msg["position"]["y"]
    received_v2x.append(msg)
    print(f"[V2X-B] << From Instance-{inst}: Vehicle {vid} | speed={spd:.1f}km/h | intent={intent_str} | pos=({px:.1f}, {py:.1f})")


def apply_cooperative_behavior(platoon_list, v2x_messages):
    if not v2x_messages or not platoon_list:
        return
    for msg in v2x_messages:
        intent = msg.get("intent", "")
        remote_speed = msg.get("speed_kmh", 0)
        for platoon in platoon_list:
            current_speed = platoon.leader_target_speed
            if intent == "emergency_stop":
                print(f"[V2X-B] EMERGENCY from Instance-{msg['instance']} — braking")
            elif intent in ("platoon_lead", "platoon_follow", "platoon_join"):
                if abs(current_speed - remote_speed) > 15:
                    new_speed = max(current_speed - 5, remote_speed * 0.9)
                    platoon.leader_target_speed = new_speed
                    print(f"[V2X-B] Speed coord: {current_speed:.1f} -> {new_speed:.1f} km/h")
    v2x_messages.clear()


def run_scenario(opt, config_yaml):
    # ── Parse attack mode from sys.argv ─────────────────────────────────────
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--attack", default="none",
                        choices=["none", "spoofing", "replay", "dos"])
    parser.add_argument("--intensity", type=float, default=0.5)
    parser.add_argument("--flood_rate", type=int, default=200)
    extra, _ = parser.parse_known_args()

    attack_type = extra.attack
    intensity   = extra.intensity
    flood_rate  = extra.flood_rate

    print(f"[V2X-B] Attack mode: {attack_type.upper()}  intensity={intensity}")

    # ── Set up injector and logger ───────────────────────────────────────────
    injector    = AttackInjector(attack_type=attack_type,
                                 intensity=intensity,
                                 flood_rate=flood_rate)
    data_logger = DataLogger(instance_id="B", attack_type=attack_type, scenario="platoon_follow")

    scenario_params = config_yaml
    cav_world = CavWorld(opt.apply_ml)

    v2x_pub = V2XPublisher("B", injector=injector, data_logger=data_logger)
    v2x_sub = V2XSubscriber("B", on_v2x_receive)
    v2x_sub.start()
    print("[V2X-B] Bridge initialized")

    scenario_manager = None
    eval_manager     = None

    try:
        current_path = os.path.dirname(os.path.realpath(__file__))
        xodr_path = os.path.join(
            current_path,
            "../assets/2lane_freeway_simplified/2lane_freeway_simplified.xodr")

        from omegaconf import OmegaConf
        import datetime
        if 'current_time' not in scenario_params:
            current_time = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            scenario_params = OmegaConf.merge(
                scenario_params,
                OmegaConf.create({'current_time': current_time})
            )

        scenario_manager = sim_api.ScenarioManager(
            scenario_params, opt.apply_ml, opt.version, xodr_path=xodr_path)

        platoon_list = scenario_manager.create_platoon_manager(
            map_helper=map_api.spawn_helper_2lanefree, data_dump=False)

        single_cav_list = scenario_manager.create_vehicle_manager(
            ["platooning"], map_api.spawn_helper_2lanefree)

        scenario_manager.create_traffic_carla()

        eval_manager = EvaluationManager(
            scenario_manager.cav_world,
            script_name="v2x_platoon_scenario",
            current_time=getattr(opt, "current_time",
                __import__("datetime").datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
        )

        spectator  = scenario_manager.world.get_spectator()
        tick_count = 0

        while True:
            scenario_manager.tick()

            if tick_count % 5 == 0:
                for platoon in platoon_list:
                    for vm in platoon.vehicle_manager_list:
                        try:
                            transform = vm.vehicle.get_transform()
                            velocity  = vm.vehicle.get_velocity()
                            speed = (velocity.x**2 + velocity.y**2)**0.5 * 3.6
                            state = str(getattr(vm.agent, "status", "platoon_follow"))
                            if "join" in state.lower():
                                intent = "platoon_join"
                            elif "lead" in state.lower():
                                intent = "platoon_lead"
                            else:
                                intent = "platoon_follow"
                            v2x_pub.publish(
                                vehicle_id=vm.vid,
                                position=(transform.location.x,
                                          transform.location.y,
                                          transform.location.z),
                                speed=speed,
                                heading=transform.rotation.yaw,
                                intent=intent
                            )
                        except Exception:
                            pass

            #apply_cooperative_behavior(platoon_list, received_v2x)

            if platoon_list:
                lead = platoon_list[0].vehicle_manager_list[0].vehicle
                t = lead.get_transform()
                spectator.set_transform(carla.Transform(
                    t.location + carla.Location(z=30),
                    carla.Rotation(pitch=-70)
                ))

            for platoon in platoon_list:
                platoon.update_information()
                platoon.run_step()

            for vm in single_cav_list:
                vm.update_info()
                vm.run_step()

            tick_count += 1

    except (KeyboardInterrupt, SystemExit):
        print("\n[V2X-B] Simulation ended")

    finally:
        print("[V2X-B] Cleaning up...")
        v2x_pub.close()
        v2x_sub.stop()
        data_logger.close()
        if eval_manager:
            eval_manager.evaluate()
        if scenario_manager:
            scenario_manager.close()
