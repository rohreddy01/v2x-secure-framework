# Secure V2X Communication Framework

## Machine
- Host: umd-002896, Ubuntu 24.04 LTS, NVIDIA RTX 4060
- CARLA 0.9.12 in Docker (ports 2000 and 3000)
- AWS EC2 MQTT broker: 3.133.81.84:1883

## Startup
sudo docker start carla_a carla_b && sleep 30
conda activate opencda_a && cd ~/opencda_a
python opencda.py -t v2x_platoon_scenario -v 0.9.12

## Attack Modes
python opencda.py -t v2x_platoon_scenario -v 0.9.12 --attack spoofing --intensity 0.5
python opencda.py -t v2x_platoon_scenario -v 0.9.12 --attack replay --intensity 0.5
python opencda.py -t v2x_platoon_scenario -v 0.9.12 --attack dos --intensity 0.8

## Files
- v2x_bridge.py        MQTT bridge via EC2
- attack_injector.py   GPS spoofing, replay, DoS
- data_logger.py       CSV data collection
- spectator_viewer.py  pygame visualization
