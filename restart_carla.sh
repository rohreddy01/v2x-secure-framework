#!/bin/bash
echo "Restarting CARLA containers..."
sudo docker stop carla_a carla_b 2>/dev/null
sudo docker rm carla_a carla_b 2>/dev/null
sleep 5

sudo docker run -d --name carla_a --gpus all \
  -p 2000-2002:2000-2002 \
  carlasim/carla:0.9.12 \
  /bin/bash -c "./CarlaUE4.sh -RenderOffScreen -opengl -carla-world-port=2000 -nosound"

sudo docker run -d --name carla_b --gpus all \
  -p 3000-3002:3000-3002 \
  carlasim/carla:0.9.12 \
  /bin/bash -c "./CarlaUE4.sh -RenderOffScreen -opengl -carla-world-port=3000 -nosound"

echo "Waiting 60 seconds..."
sleep 60

echo "Clearing default actors..."
conda run -n opencda_a python -c "
import carla, time
for port, name in [(2000,'A'),(3000,'B')]:
    c = carla.Client('localhost', port)
    c.set_timeout(30.0)
    world = c.get_world()
    batch = [carla.command.DestroyActor(a.id) 
             for a in world.get_actors() 
             if a.type_id != 'spectator']
    if batch:
        c.apply_batch_sync(batch, True)
        print(f'CARLA {name}: cleared {len(batch)} actors')
    time.sleep(3)
    remaining = [a for a in world.get_actors() if a.type_id != 'spectator']
    print(f'CARLA {name}: ready | actors={len(remaining)}')
"
echo "Ready to run scenarios."
