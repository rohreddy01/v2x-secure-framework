#!/bin/bash
echo "Cleaning up CARLA worlds..."
conda run -n opencda_a python -c "
import carla, time
for port, name in [(2000,'A'),(3000,'B')]:
    c = carla.Client('localhost', port)
    c.set_timeout(30.0)
    actors = c.get_world().get_actors()
    count = 0
    for a in actors:
        if a.type_id.startswith('vehicle') or a.type_id.startswith('sensor'):
            a.destroy()
            count += 1
    print(f'CARLA {name}: destroyed {count} actors')
    c.reload_world()
    print(f'CARLA {name}: world reloaded')
    time.sleep(3)
"
echo "Done. Ready for next scenario."
