#!/bin/bash
export DISPLAY=:1
export SDL_VIDEODRIVER=x11
source /home/umd-user/miniconda3/etc/profile.d/conda.sh
conda activate opencda_a
python /home/umd-user/spectator_viewer.py
