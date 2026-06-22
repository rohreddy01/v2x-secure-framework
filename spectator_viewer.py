import carla
import pygame
import numpy as np

CARLA_HOST = 'localhost'
CARLA_PORT = 2000
WINDOW_W = 960
WINDOW_H = 540

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption('CARLA Viewer - F: follow | WASD: free fly | Q: quit')
    clock = pygame.time.Clock()

    client = carla.Client(CARLA_HOST, CARLA_PORT)
    client.set_timeout(10.0)
    world = client.get_world()

    blueprint_library = world.get_blueprint_library()
    cam_bp = blueprint_library.find('sensor.camera.rgb')
    cam_bp.set_attribute('image_size_x', str(WINDOW_W))
    cam_bp.set_attribute('image_size_y', str(WINDOW_H))
    cam_bp.set_attribute('fov', '90')

    # Spawn camera freestanding — not attached to anything
    init_transform = carla.Transform(
        carla.Location(x=0, y=0, z=80),
        carla.Rotation(pitch=-90, yaw=0, roll=0)
    )
    camera = world.spawn_actor(cam_bp, init_transform)

    image_data = [None]

    def on_image(image):
        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = array.reshape((image.height, image.width, 4))
        array = array[:, :, :3][:, :, ::-1]
        image_data[0] = array

    camera.listen(on_image)

    font = pygame.font.SysFont('monospace', 16)
    follow_mode = True
    speed = 3.0
    cam_yaw = 0.0
    cam_pitch = -90.0
    cam_loc = carla.Location(x=0, y=0, z=80)

    print("Connected! F=follow platoon, WASD=free fly, Shift=fast, Q=quit")

    running = True
    mouse_down = False
    last_mouse = (0, 0)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
                if event.key == pygame.K_f:
                    follow_mode = not follow_mode
                    if follow_mode:
                        cam_pitch = -90.0
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_down = True
                last_mouse = pygame.mouse.get_pos()
            if event.type == pygame.MOUSEBUTTONUP:
                mouse_down = False

        vehicles = list(world.get_actors().filter('vehicle.*'))

        if follow_mode and vehicles:
            avg_x = sum(v.get_location().x for v in vehicles) / len(vehicles)
            avg_y = sum(v.get_location().y for v in vehicles) / len(vehicles)
            avg_z = sum(v.get_location().z for v in vehicles) / len(vehicles)
            cam_loc = carla.Location(x=avg_x, y=avg_y, z=avg_z + 120)
            cam_pitch = -90.0
            cam_yaw = 0.0
        else:
            if mouse_down:
                mx, my = pygame.mouse.get_pos()
                dx = mx - last_mouse[0]
                dy = my - last_mouse[1]
                cam_yaw += dx * 0.3
                cam_pitch = max(-89, min(-10, cam_pitch + dy * 0.3))
                last_mouse = (mx, my)

            keys = pygame.key.get_pressed()
            spd = speed * 4 if keys[pygame.K_LSHIFT] else speed
            # Compute forward/right from yaw only for horizontal movement
            import math
            rad = math.radians(cam_yaw)
            fwd_x = math.cos(rad)
            fwd_y = math.sin(rad)
            right_x = math.cos(rad + math.pi/2)
            right_y = math.sin(rad + math.pi/2)
            if keys[pygame.K_w]: cam_loc += carla.Location(x=fwd_x*spd, y=fwd_y*spd)
            if keys[pygame.K_s]: cam_loc -= carla.Location(x=fwd_x*spd, y=fwd_y*spd)
            if keys[pygame.K_a]: cam_loc -= carla.Location(x=right_x*spd, y=right_y*spd)
            if keys[pygame.K_d]: cam_loc += carla.Location(x=right_x*spd, y=right_y*spd)
            if keys[pygame.K_UP]:   cam_loc.z += spd
            if keys[pygame.K_DOWN]: cam_loc.z -= spd

        camera.set_transform(carla.Transform(
            cam_loc,
            carla.Rotation(pitch=cam_pitch, yaw=cam_yaw, roll=0)
        ))

        if image_data[0] is not None:
            surface = pygame.surfarray.make_surface(image_data[0].swapaxes(0, 1))
            screen.blit(surface, (0, 0))

        mode_str = '[FOLLOW ALL]' if follow_mode else '[FREE FLY]'
        hud = font.render(
            f"{mode_str}  F=toggle  Shift=fast  Q=quit  vehicles={len(vehicles)}",
            True, (255, 255, 0)
        )
        screen.blit(hud, (10, 10))

        pygame.display.flip()
        clock.tick(30)

    camera.stop()
    camera.destroy()
    pygame.quit()

if __name__ == '__main__':
    main()
