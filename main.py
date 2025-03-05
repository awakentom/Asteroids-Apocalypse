import pygame
import math
import random
import os
import json

# --------------------------------------------------
# Helper Functions for High Score
# --------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
HIGH_SCORE_FILE = os.path.join(script_dir, "highscore.json")

def load_high_score():
    if os.path.exists(HIGH_SCORE_FILE):
        with open(HIGH_SCORE_FILE, "r") as f:
            return json.load(f).get("high_score", 0)
    return 0

def save_high_score(high_score):
    with open(HIGH_SCORE_FILE, "w") as f:
        json.dump({"high_score": high_score}, f)

# --------------------------------------------------
# Helper Functions for Collision Detection
# --------------------------------------------------
def point_in_polygon(x, y, poly):
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def polygons_collide(poly1, poly2):
    def get_axes(polygon):
        axes = []
        for i in range(len(polygon)):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % len(polygon)]
            edge = (p2[0] - p1[0], p2[1] - p1[1])
            normal = (-edge[1], edge[0])
            length = math.sqrt(normal[0]**2 + normal[1]**2)
            if length != 0:
                normal = (normal[0]/length, normal[1]/length)
            axes.append(normal)
        return axes

    def project(polygon, axis):
        dots = [pt[0]*axis[0] + pt[1]*axis[1] for pt in polygon]
        return min(dots), max(dots)

    axes = get_axes(poly1) + get_axes(poly2)
    for axis in axes:
        min1, max1 = project(poly1, axis)
        min2, max2 = project(poly2, axis)
        if max1 < min2 or max2 < min1:
            return False
    return True

# --------------------------------------------------
# Pygame Initialization
# --------------------------------------------------
pygame.init()
pygame.mixer.init()
pygame.mixer.set_num_channels(32)

# --------------------------------------------------
# Constants
# --------------------------------------------------
WIDTH, HEIGHT = 1920, 1080
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
STAR_COLOR = (180, 180, 180)
FPS = 60

LARGE_SIZE = 54
MEDIUM_SIZE = 36
SMALL_SIZE = 18
SHIP_RADIUS = 36
UFO_DETECTION_RADIUS = 225
BLACK_HOLE_SPAWN_CHANCE = 0.0005
UFO_SPAWN_CHANCE = 0.001

MISSILE_LIFETIME_MS = 15000
MISSILE_INITIAL_SPEED = 1.08
MISSILE_ACCEL = 0.005
MISSILE_MAX_SPEED = 4
MISSILE_TURN_RATE = 0.5
MISSILE_REWARD = 500

# --------------------------------------------------
# Sound Setup
# --------------------------------------------------
laser_sound = pygame.mixer.Sound(os.path.join(script_dir, "laser.wav"))
explosion_sound = pygame.mixer.Sound(os.path.join(script_dir, "explosion.wav"))
thruster_sound = pygame.mixer.Sound(os.path.join(script_dir, "thruster.wav"))
ufo_sound = pygame.mixer.Sound(os.path.join(script_dir, "ufo.wav"))
missile_sound = pygame.mixer.Sound(os.path.join(script_dir, "missile.wav"))
blackhole_sound = pygame.mixer.Sound(os.path.join(script_dir, "blackhole.wav"))
missile_sound.set_volume(0.7)

thruster_channel = pygame.mixer.Channel(31)
ufo_channel = pygame.mixer.Channel(30)
missile_channel = pygame.mixer.Channel(29)
blackhole_channel = pygame.mixer.Channel(28)

pygame.mixer.music.load(os.path.join(script_dir, "music.wav"))
pygame.mixer.music.set_volume(0.5)
pygame.mixer.music.play(-1)

# --------------------------------------------------
# Screen Setup
# --------------------------------------------------
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Asteroids: Apocalypse")
clock = pygame.time.Clock()

# --------------------------------------------------
# Helper Functions
# --------------------------------------------------
def wrap_position(x, y):
    return x % WIDTH, y % HEIGHT

def create_star_field(num_stars=180):
    return [(random.randint(0, WIDTH), random.randint(0, HEIGHT)) for _ in range(num_stars)]

def create_asteroid_shape(radius, num_points=12):
    pts = []
    for i in range(num_points):
        angle = i * (2 * math.pi / num_points) + random.uniform(-0.25, 0.25)
        variation = random.uniform(-0.4, 0.4) if random.random() >= 0.2 else random.uniform(-0.6, 0.6)
        r = radius * (1 + variation)
        pts.append((r * math.cos(angle), r * math.sin(angle)))
    return pts

# --------------------------------------------------
# Entity Classes
# --------------------------------------------------
class Ship:
    def __init__(self):
        self.x = WIDTH // 2
        self.y = HEIGHT // 2
        self.angle = 0
        self.vel_x = 0
        self.vel_y = 0
        self.thrust_amount = 0.18
        self.friction = 0.99
        self.max_speed = 9.9
        self.spawned = False
        self.invulnerable = False
        self.invuln_start_time = 0
        self.invuln_duration = 0
        self.rapid_fire = False
        self.rapid_fire_start_time = 0
        self.rapid_fire_duration = 5000
        self.thrusting = False
        self.respawn_delay = 0
        self.respawn_timer = 0
        self.pending_respawn = False
        self.respawn_invuln_duration = 0

    def reset_position(self):
        self.x, self.y = WIDTH // 2, HEIGHT // 2
        self.vel_x = self.vel_y = 0
        self.angle = 0
        self.thrusting = False
        if thruster_channel.get_busy():
            thruster_channel.stop()

    def trigger_respawn(self, delay_ms, invuln_duration_ms):
        self.spawned = False
        self.pending_respawn = True
        self.respawn_delay = delay_ms
        self.respawn_timer = pygame.time.get_ticks()
        self.respawn_invuln_duration = invuln_duration_ms
        self.vel_x = self.vel_y = 0
        self.thrusting = False
        if thruster_channel.get_busy():
            thruster_channel.stop()

    def handle_input(self, keys):
        if keys[pygame.K_LEFT]:
            self.angle += 3
        if keys[pygame.K_RIGHT]:
            self.angle -= 3
        if keys[pygame.K_UP]:
            self.thrusting = True
            self.vel_x += self.thrust_amount * math.cos(math.radians(self.angle))
            self.vel_y -= self.thrust_amount * math.sin(math.radians(self.angle))
            if not thruster_channel.get_busy():
                thruster_channel.play(thruster_sound, loops=-1)
        else:
            self.thrusting = False
            if thruster_channel.get_busy():
                thruster_channel.stop()

    def update(self, dt):
        current_time = pygame.time.get_ticks()
        if self.pending_respawn and (current_time - self.respawn_timer >= self.respawn_delay):
            self.reset_position()
            self.spawned = True
            self.invulnerable = True
            self.invuln_start_time = current_time
            self.invuln_duration = self.respawn_invuln_duration
            self.pending_respawn = False

        if not self.spawned:
            return

        self.x += self.vel_x * dt * 60
        self.y += self.vel_y * dt * 60
        speed = math.sqrt(self.vel_x**2 + self.vel_y**2)
        if speed > self.max_speed:
            factor = self.max_speed / speed
            self.vel_x *= factor
            self.vel_y *= factor
        self.vel_x *= (self.friction ** (dt * 60))
        self.vel_y *= (self.friction ** (dt * 60))
        self.x, self.y = wrap_position(self.x, self.y)

        if self.invulnerable and (current_time - self.invuln_start_time) >= self.invuln_duration:
            self.invulnerable = False
        if self.rapid_fire and (current_time - self.rapid_fire_start_time) >= self.rapid_fire_duration:
            self.rapid_fire = False

    def draw(self, surface):
        if not self.spawned or (self.invulnerable and (pygame.time.get_ticks() // 100) % 2 == 0):
            return
        ship_length = 36
        wing_length = 18
        tip = (self.x + ship_length * math.cos(math.radians(self.angle)),
               self.y - ship_length * math.sin(math.radians(self.angle)))
        left = (self.x + wing_length * math.cos(math.radians(self.angle + 135)),
                self.y - wing_length * math.sin(math.radians(self.angle + 135)))
        right = (self.x + wing_length * math.cos(math.radians(self.angle - 135)),
                 self.y - wing_length * math.sin(math.radians(self.angle - 135)))
        pygame.draw.line(surface, WHITE, tip, left, 2)
        pygame.draw.line(surface, WHITE, left, right, 2)
        pygame.draw.line(surface, WHITE, right, tip, 2)
        if self.thrusting:
            flame_offset = 27
            flame_size = 12.6
            flame_base = (self.x - flame_offset * math.cos(math.radians(self.angle)),
                          self.y + flame_offset * math.sin(math.radians(self.angle)))
            flame_l = (self.x + flame_size * math.cos(math.radians(self.angle + 160)),
                       self.y - flame_size * math.sin(math.radians(self.angle + 160)))
            flame_r = (self.x + flame_size * math.cos(math.radians(self.angle - 160)),
                       self.y - flame_size * math.sin(math.radians(self.angle - 160)))
            pygame.draw.polygon(surface, (255, 100, 0), [flame_l, flame_base, flame_r])

    def get_polygon(self):
        ship_length = 36
        wing_length = 18
        tip = (self.x + ship_length * math.cos(math.radians(self.angle)),
               self.y - ship_length * math.sin(math.radians(self.angle)))
        left = (self.x + wing_length * math.cos(math.radians(self.angle + 135)),
                self.y - wing_length * math.sin(math.radians(self.angle + 135)))
        right = (self.x + wing_length * math.cos(math.radians(self.angle - 135)),
                 self.y - wing_length * math.sin(math.radians(self.angle - 135)))
        return [tip, left, right]

class Missile:
    def __init__(self, x, y, ship):
        self.x = x
        self.y = y
        self.ship = ship
        self.active = True
        self.angle = 0.0
        self.speed = MISSILE_INITIAL_SPEED
        self.spawn_time = pygame.time.get_ticks()
        missile_channel.play(missile_sound, loops=-1)

    def update(self, dt):
        if not self.active:
            if missile_channel.get_busy():
                missile_channel.stop()
            return
        if pygame.time.get_ticks() - self.spawn_time >= MISSILE_LIFETIME_MS:
            self.active = False
            if missile_channel.get_busy():
                missile_channel.stop()
            return

        R = self.speed / MISSILE_TURN_RATE if MISSILE_TURN_RATE != 0 else float('inf')
        margin = 2 * R
        avoidance_x = avoidance_y = 0
        if self.x < margin: avoidance_x += 1
        if self.x > WIDTH - margin: avoidance_x -= 1
        if self.y < margin: avoidance_y += 1
        if self.y > HEIGHT - margin: avoidance_y -= 1

        if avoidance_x or avoidance_y:
            mag = math.sqrt(avoidance_x**2 + avoidance_y**2)
            desired_dir = (avoidance_x / mag, avoidance_y / mag)
        else:
            dx, dy = self.ship.x - self.x, self.ship.y - self.y
            mag = max(math.sqrt(dx**2 + dy**2), 0.001)
            desired_dir = (dx / mag, dy / mag)

        desired_angle = math.atan2(desired_dir[1], desired_dir[0])
        angle_diff = (desired_angle - self.angle + math.pi) % (2 * math.pi) - math.pi
        angle_diff = max(min(angle_diff, MISSILE_TURN_RATE * dt * 60), -MISSILE_TURN_RATE * dt * 60)
        self.angle += angle_diff

        self.speed = min(self.speed + MISSILE_ACCEL * dt * 60, MISSILE_MAX_SPEED)
        self.x += self.speed * math.cos(self.angle) * dt * 60
        self.y += self.speed * math.sin(self.angle) * dt * 60
        self.x = max(0, min(self.x, WIDTH))
        self.y = max(0, min(self.y, HEIGHT))

    def draw(self, surface):
        if not self.active:
            return
        length = 21.6
        width = 7.2
        tip = (self.x + length * math.cos(self.angle), self.y + length * math.sin(self.angle))
        base_left = (self.x - (length * 0.5) * math.cos(self.angle) - width * math.sin(self.angle),
                     self.y - (length * 0.5) * math.sin(self.angle) + width * math.cos(self.angle))
        base_right = (self.x - (length * 0.5) * math.cos(self.angle) + width * math.sin(self.angle),
                      self.y - (length * 0.5) * math.sin(self.angle) - width * math.cos(self.angle))
        pygame.draw.polygon(surface, WHITE, [tip, base_left, base_right])
        flame_length = 9
        flame_offset = (self.x - (length * 0.6) * math.cos(self.angle),
                        self.y - (length * 0.6) * math.sin(self.angle))
        flame_left = (flame_offset[0] + 3.6 * math.sin(self.angle),
                      flame_offset[1] - 3.6 * math.cos(self.angle))
        flame_right = (flame_offset[0] - 3.6 * math.sin(self.angle),
                       flame_offset[1] + 3.6 * math.cos(self.angle))
        flame_tip = (flame_offset[0] - flame_length * math.cos(self.angle),
                     flame_offset[1] - flame_length * math.sin(self.angle))
        pygame.draw.polygon(surface, (255, 128, 0), [flame_left, flame_tip, flame_right])

    def take_damage(self):
        self.active = False
        if missile_channel.get_busy():
            missile_channel.stop()

    def get_polygon(self):
        length = 21.6
        width = 7.2
        tip = (self.x + length * math.cos(self.angle), self.y + length * math.sin(self.angle))
        base_left = (self.x - (length * 0.5) * math.cos(self.angle) - width * math.sin(self.angle),
                     self.y - (length * 0.5) * math.sin(self.angle) + width * math.cos(self.angle))
        base_right = (self.x - (length * 0.5) * math.cos(self.angle) + width * math.sin(self.angle),
                      self.y - (length * 0.5) * math.sin(self.angle) - width * math.cos(self.angle))
        return [tip, base_left, base_right]

class UFO:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 108
        self.height = 36
        self.health = 5
        self.rib_count = 5
        self.rib_spacing = self.width / self.rib_count
        self.rib_offset = 0.0
        self.angle = 0.0
        self.vel_x = self.vel_y = 0.0
        self.base_speed = 1
        self.tractor_wave_offset = 0.0
        self.missile_fire_chance = 0.0006

    def update(self, ship_x, ship_y, dt):
        desired_angle = math.atan2(ship_y - self.y, ship_x - self.x)
        turn_speed = 0.02
        angle_diff = (desired_angle - self.angle + math.pi) % (2 * math.pi) - math.pi
        angle_diff = max(min(angle_diff, turn_speed * dt * 60), -turn_speed * dt * 60)
        self.angle += angle_diff
        self.vel_x = self.base_speed * math.cos(self.angle)
        self.vel_y = self.base_speed * math.sin(self.angle)
        self.x += self.vel_x * dt * 60
        self.y += self.vel_y * dt * 60
        self.x, self.y = wrap_position(self.x, self.y)
        self.rib_offset += 0.54 * dt * 60
        self.tractor_wave_offset += 2.0 * dt * 60

    def draw(self, surface):
        UFO_COLOR = (20, 20, 20)
        UFO_RIB_COLOR = (70, 70, 70)
        ufo_rect = pygame.Rect(self.x - self.width/2, self.y - self.height/2, self.width, self.height)
        pygame.draw.ellipse(surface, UFO_COLOR, ufo_rect)
        dome_center = (int(self.x), int(self.y - self.height//2))
        pygame.draw.circle(surface, UFO_COLOR, dome_center, int(self.height // 2))
        rib_y_top = self.y - self.height/4
        rib_y_bottom = self.y + self.height/4
        full_rib_height = rib_y_bottom - rib_y_top
        for i in range(self.rib_count):
            rel_x = -self.width/2 + i * self.rib_spacing
            rib_x = self.x + (((rel_x + self.rib_offset + self.width/2) % self.width) - self.width/2)
            taper_factor = 0.5 + 0.5 * (1 - abs((rib_x - self.x) / (self.width/2)))
            tapered_height = full_rib_height * taper_factor
            pygame.draw.line(surface, UFO_RIB_COLOR,
                             (rib_x, self.y - tapered_height/2),
                             (rib_x, self.y + tapered_height/2), 2)

    def draw_tractor_beam(self, surface, ship_x, ship_y):
        cx, cy = self.x, self.y
        angle_to_ship = math.atan2(ship_y - cy, ship_x - cx)
        half_cone = math.radians(22.5)
        start_angle, end_angle = angle_to_ship - half_cone, angle_to_ship + half_cone
        num_waves = 5
        wave_interval = UFO_DETECTION_RADIUS / num_waves
        points_per_wave = 30
        for i in range(num_waves):
            r = UFO_DETECTION_RADIUS - (i * wave_interval + (self.tractor_wave_offset % wave_interval))
            if 0 <= r <= UFO_DETECTION_RADIUS:
                wave_points = []
                for j in range(points_per_wave):
                    factor = j / (points_per_wave - 1)
                    cur_angle = start_angle + factor * (end_angle - start_angle)
                    base_x = cx + r * math.cos(cur_angle)
                    base_y = cy + r * math.sin(cur_angle)
                    wave_points.append((base_x, base_y))
                pygame.draw.lines(surface, WHITE, False, wave_points, 1)

    def get_polygon(self):
        points = []
        for i in range(6):
            angle = math.pi - i * (math.pi / 5)
            x = self.x + (self.width / 2) * math.cos(angle)
            y = self.y + (self.height / 2) * math.sin(angle)
            points.append((x, y))
        dome_center_x = self.x
        dome_center_y = self.y - self.height / 2
        dome_radius = self.height / 2
        for i in range(4):
            angle = -math.pi / 2 - i * (math.pi / 3)
            x = dome_center_x + dome_radius * math.cos(angle)
            y = dome_center_y + dome_radius * math.sin(angle)
            points.append((x, y))
        return points

class BlackHole:
    def __init__(self):
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(0, HEIGHT)
        self.radius = 90
        self.base_speed = 0.09
        direction = random.uniform(0, 2 * math.pi)
        self.vel_x = self.base_speed * math.cos(direction)
        self.vel_y = self.base_speed * math.sin(direction)
        self.rotation_angle = 0
        self.rotation_speed = -2
        self.spiral_points = [(self.radius / (2 * math.pi * 5) * theta * math.cos(theta),
                              self.radius / (2 * math.pi * 5) * theta * math.sin(theta))
                             for theta in [i * 0.1 for i in range(int(2 * math.pi * 5 / 0.1) + 1)]]
        self.fade_in_duration = 2000
        self.active_duration = 11000
        self.fade_out_duration = 2000
        self.spawn_time = pygame.time.get_ticks()
        self.opacity = 0
        self.state = "fading_in"
        blackhole_channel.play(blackhole_sound, loops=-1)

    def update(self, dt):
        current_time = pygame.time.get_ticks()
        elapsed_time = current_time - self.spawn_time

        if self.state == "fading_in":
            if elapsed_time < self.fade_in_duration:
                self.opacity = int(255 * (elapsed_time / self.fade_in_duration))
            else:
                self.state = "active"
                self.opacity = 255
        elif self.state == "active":
            if elapsed_time >= self.fade_in_duration + self.active_duration:
                self.state = "fading_out"
        elif self.state == "fading_out":
            fade_out_elapsed = elapsed_time - (self.fade_in_duration + self.active_duration)
            if fade_out_elapsed < self.fade_out_duration:
                self.opacity = int(255 * (1 - fade_out_elapsed / self.fade_out_duration))

        self.rotation_angle += self.rotation_speed * dt * 60
        self.x += self.vel_x * dt * 60
        self.y += self.vel_y * dt * 60
        self.x, self.y = wrap_position(self.x, self.y)

    def draw(self, surface):
        cx, cy = int(self.x), int(self.y)
        bh_surface = pygame.Surface((int(self.radius * 2), int(self.radius * 2)), pygame.SRCALPHA)
        c = (255, 255, 255, self.opacity)
        cos_a, sin_a = math.cos(math.radians(self.rotation_angle)), math.sin(math.radians(self.rotation_angle))
        points = [(int(self.radius + px * cos_a - py * sin_a), int(self.radius + px * sin_a + py * cos_a))
                  for px, py in self.spiral_points]
        pygame.draw.lines(bh_surface, c, False, points, 1)
        pygame.draw.circle(bh_surface, c, (int(self.radius), int(self.radius)), 2, 1)
        surface.blit(bh_surface, (cx - self.radius, cy - self.radius))

    def is_active(self):
        current_time = pygame.time.get_ticks()
        elapsed_time = current_time - self.spawn_time
        fade_out_start = self.fade_in_duration + self.active_duration
        return (elapsed_time >= 1000 and
                elapsed_time < fade_out_start + 1000)

    def check_collision_with_ship(self, sx, sy):
        return math.sqrt((sx - self.x)**2 + (sy - self.y)**2) < (self.radius + SHIP_RADIUS)

    def stop_sound(self):
        if blackhole_channel.get_busy():
            blackhole_channel.stop()

# --------------------------------------------------
# Manager Classes
# --------------------------------------------------
class BulletManager:
    def __init__(self):
        self.bullet_speed = 10.8
        self.bullets = []
        self.cooldown_time = 15
        self.shoot_cooldown = 0
        self.shoot_grace_timer = 0

    def shoot(self, ship):
        if self.shoot_cooldown == 0 and self.shoot_grace_timer == 0 and ship.spawned:
            bx = ship.x + 36 * math.cos(math.radians(ship.angle))
            by = ship.y - 36 * math.sin(math.radians(ship.angle))
            bvx = self.bullet_speed * math.cos(math.radians(ship.angle))
            bvy = -self.bullet_speed * math.sin(math.radians(ship.angle))
            self.bullets.append([bx, by, bvx, bvy])
            self.shoot_cooldown = 5 if ship.rapid_fire else self.cooldown_time
            laser_sound.play()

    def update(self, dt):
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= dt * 60
            if self.shoot_cooldown < 0:
                self.shoot_cooldown = 0
        if self.shoot_grace_timer > 0:
            self.shoot_grace_timer -= dt * 60
            if self.shoot_grace_timer < 0:
                self.shoot_grace_timer = 0

        for b in self.bullets:
            b[0] += b[2] * dt * 60
            b[1] += b[3] * dt * 60

        self.bullets = [b for b in self.bullets if 0 <= b[0] <= WIDTH and 0 <= b[1] <= HEIGHT]

    def draw(self, surface):
        for b in self.bullets:
            pygame.draw.circle(surface, WHITE, (int(b[0]), int(b[1])), 3)

    def clear(self):
        self.bullets.clear()

class ExplosionManager:
    def __init__(self):
        self.explosions = []

    def spawn_explosion(self, x, y, count=20):
        parts = [{"x": x, "y": y, "vel_x": random.uniform(1.8, 5.4) * math.cos(random.uniform(0, 2*math.pi)),
                  "vel_y": random.uniform(1.8, 5.4) * math.sin(random.uniform(0, 2*math.pi)),
                  "life": random.randint(20, 40)} for _ in range(count)]
        self.explosions.append(parts)

    def update(self, dt):
        for ex in self.explosions[:]:
            for p in ex[:]:
                p["x"] += p["vel_x"] * dt * 60
                p["y"] += p["vel_y"] * dt * 60
                p["life"] -= dt * 60
                if p["life"] <= 0:
                    ex.remove(p)
            if not ex:
                self.explosions.remove(ex)

    def draw(self, surface):
        for ex in self.explosions:
            for p in ex:
                pygame.draw.circle(surface, WHITE, (int(p["x"]), int(p["y"])), max(1, int(p["life"] // 10)))

    def clear(self):
        self.explosions.clear()

class AsteroidManager:
    def __init__(self):
        self.asteroids = []

    def spawn_asteroid(self, size, x, y, pvx=0, pvy=0):
        vx = pvx + random.uniform(-1.17, 1.17)
        vy = pvy + random.uniform(-1.17, 1.17)
        shape = create_asteroid_shape(size)
        rotation_speed = random.uniform(-0.6, 0.6) * (random.choice([2, 3]) if random.random() < 0.2 else 1)
        max_radius = max(math.sqrt(px**2 + py**2) for px, py in shape)
        return [x, y, vx, vy, size, shape, 0, rotation_speed, max_radius]

    def spawn_safe_asteroid(self, size, sx, sy, min_dist=180):
        while True:
            ax, ay = random.randint(0, WIDTH), random.randint(0, HEIGHT)
            if math.sqrt((ax - sx)**2 + (ay - sy)**2) > min_dist:
                return self.spawn_asteroid(size, ax, ay)

    def start_wave(self, wave_count, ship_x, ship_y):
        for _ in range(int((3 + wave_count) * 1.3)):
            self.asteroids.append(self.spawn_safe_asteroid(LARGE_SIZE, ship_x, ship_y))

    def update(self, dt):
        for ast in self.asteroids:
            ast[0], ast[1] = wrap_position(ast[0] + ast[2] * dt * 60, ast[1] + ast[3] * dt * 60)
            ast[6] += ast[7] * dt * 60

    def get_polygon(self, ast):
        x, y, _, _, _, shape, angle, _, _ = ast
        cos_a, sin_a = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        return [(x + px * cos_a - py * sin_a, y + px * sin_a + py * cos_a) for px, py in shape]

    def draw(self, surface):
        for ast in self.asteroids:
            pygame.draw.polygon(surface, WHITE, self.get_polygon(ast), 1)

    def handle_bullet_collisions(self, bullet_manager, explosion_manager, score):
        for b in bullet_manager.bullets[:]:
            bx, by = b[0], b[1]
            for ast in self.asteroids[:]:
                distance = math.sqrt((bx - ast[0])**2 + (by - ast[1])**2)
                if distance < ast[8]:
                    ast_poly = self.get_polygon(ast)
                    if point_in_polygon(bx, by, ast_poly):
                        explosion_manager.spawn_explosion(ast[0], ast[1], 8)
                        explosion_sound.play()
                        if ast[4] == LARGE_SIZE:
                            score += 20
                            self.asteroids.extend([self.spawn_asteroid(MEDIUM_SIZE, ast[0], ast[1], ast[2], ast[3]) for _ in range(2)])
                        elif ast[4] == MEDIUM_SIZE:
                            score += 50
                            self.asteroids.extend([self.spawn_asteroid(SMALL_SIZE, ast[0], ast[1], ast[2], ast[3]) for _ in range(2)])
                        else:
                            score += 100
                        self.asteroids.remove(ast)
                        bullet_manager.bullets.remove(b)
                        break
        return score

    def handle_ship_collision(self, ship):
        if not ship.spawned or ship.invulnerable:
            return False
        ship_poly = ship.get_polygon()
        for ast in self.asteroids:
            if math.sqrt((ship.x - ast[0])**2 + (ship.y - ast[1])**2) < (SHIP_RADIUS + ast[8]):
                if polygons_collide(ship_poly, self.get_polygon(ast)):
                    return True
        return False

    def clear(self):
        self.asteroids.clear()

class MissileManager:
    def __init__(self):
        self.missiles = []

    def spawn_missile(self, x, y, ship):
        self.missiles.append(Missile(x, y, ship))

    def update(self, dt):
        for m in self.missiles[:]:
            m.update(dt)
            if not m.active:
                self.missiles.remove(m)

    def draw(self, surface):
        for m in self.missiles:
            m.draw(surface)

    def handle_bullet_collisions(self, bullet_manager, explosion_manager, score):
        for b in bullet_manager.bullets[:]:
            bx, by = b[0], b[1]
            for m in self.missiles[:]:
                if math.sqrt((bx - m.x)**2 + (by - m.y)**2) < 18:
                    missile_poly = m.get_polygon()
                    if point_in_polygon(bx, by, missile_poly):
                        m.take_damage()
                        explosion_sound.play()
                        bullet_manager.bullets.remove(b)
                        if not m.active:
                            explosion_manager.spawn_explosion(m.x, m.y, 10)
                            score += MISSILE_REWARD
                            self.missiles.remove(m)
                        break
        return score

    def handle_ship_collision(self, ship, explosion_manager, lives):
        if not ship.spawned or ship.invulnerable:
            return lives
        ship_poly = ship.get_polygon()
        for m in self.missiles[:]:
            if math.sqrt((ship.x - m.x)**2 + (ship.y - m.y)**2) < (SHIP_RADIUS + 14.4):
                missile_poly = m.get_polygon()
                if polygons_collide(ship_poly, missile_poly):
                    explosion_manager.spawn_explosion(ship.x, ship.y, 30)
                    explosion_sound.play()
                    lives -= 1
                    ship.trigger_respawn(2000, 5000)
                    m.active = False
                    if missile_channel.get_busy():
                        missile_channel.stop()
                    self.missiles.remove(m)
                    break
        return lives

    def clear(self):
        self.missiles.clear()
        if missile_channel.get_busy():
            missile_channel.stop()

# --------------------------------------------------
# Spawn Helpers
# --------------------------------------------------
def spawn_black_hole():
    return BlackHole()

def spawn_ufo_on_edge():
    side = random.choice(["left", "right", "top", "bottom"])
    if side == "left": return UFO(0, random.randint(0, HEIGHT))
    if side == "right": return UFO(WIDTH, random.randint(0, HEIGHT))
    if side == "top": return UFO(random.randint(0, WIDTH), 0)
    return UFO(random.randint(0, WIDTH), HEIGHT)

# --------------------------------------------------
# World Class
# --------------------------------------------------
class World:
    def __init__(self):
        self.ship = Ship()
        self.bullet_manager = BulletManager()
        self.asteroid_manager = AsteroidManager()
        self.explosion_manager = ExplosionManager()
        self.missile_manager = MissileManager()
        self.ufo = None
        self.black_hole = None
        self.score = 0
        self.lives = 3
        self.wave_count = 1
        self.stars = create_star_field()
        font_path = os.path.join(script_dir, "orbitron.ttf")
        try:
            self.large_font = pygame.font.Font(font_path, 90)  # Increased from 75
            self.semilarge_font = pygame.font.Font(font_path, 45)  # Decreased from 50
            self.regular_font = pygame.font.Font(font_path, 35)  # Increased from 30
            self.tiny_font = pygame.font.Font(font_path, 25)  # Increased from 20
        except FileNotFoundError:
            print("Orbitron font not found, falling back to default font")
            self.large_font = pygame.font.SysFont(None, 90)
            self.semilarge_font = pygame.font.SysFont(None, 45)
            self.regular_font = pygame.font.SysFont(None, 35)
            self.tiny_font = pygame.font.SysFont(None, 25)
        self.high_score = load_high_score()
        self.game_state = "MENU"
        self.wave_cleared = False
        self.wave_cleared_start_time = 0
        self.wave_cleared_duration = 1500
        self.pause_options = ["Resume", "Restart", "Quit to Menu"]
        self.selected_option = 0
        self.toggle_cooldown = 0  # Cooldown timer for option toggling (in milliseconds)
        self.toggle_delay = 200   # Delay between toggles (0.2 seconds)

    def handle_input(self, keys):
        if self.game_state == "PLAYING":
            self.ship.handle_input(keys)
            if keys[pygame.K_SPACE]:
                self.bullet_manager.shoot(self.ship)
        elif self.game_state == "PAUSED":
            current_time = pygame.time.get_ticks()
            if current_time - self.toggle_cooldown >= self.toggle_delay:
                if keys[pygame.K_UP]:
                    self.selected_option = (self.selected_option - 1) % len(self.pause_options)
                    self.toggle_cooldown = current_time
                elif keys[pygame.K_DOWN]:
                    self.selected_option = (self.selected_option + 1) % len(self.pause_options)
                    self.toggle_cooldown = current_time
            if keys[pygame.K_RETURN] or keys[pygame.K_SPACE]:
                self.handle_pause_selection()

    def handle_pause_selection(self):
        if self.pause_options[self.selected_option] == "Resume":
            self.game_state = "PLAYING"
        elif self.pause_options[self.selected_option] == "Restart":
            self.reset_game()
            self.game_state = "PLAYING"
            self.bullet_manager.shoot_grace_timer = 15
            self.asteroid_manager.start_wave(self.wave_count, self.ship.x, self.ship.y)
        elif self.pause_options[self.selected_option] == "Quit to Menu":
            self.reset_game()
            self.game_state = "MENU"

    def reset_game(self):
        self.ship.trigger_respawn(0, 5000)
        self.bullet_manager.clear()
        self.asteroid_manager.clear()
        self.explosion_manager.clear()
        self.missile_manager.clear()
        self.ufo = None
        if ufo_channel.get_busy():
            ufo_channel.stop()
        if self.black_hole:
            self.black_hole.stop_sound()
            self.black_hole = None
        self.score = 0
        self.lives = 3
        self.wave_count = 1

    def update(self, dt):
        if self.game_state != "PLAYING":
            return

        self.ship.update(dt)
        self.bullet_manager.update(dt)
        self.asteroid_manager.update(dt)
        self.missile_manager.update(dt)
        self.explosion_manager.update(dt)

        if not self.ufo and random.random() < UFO_SPAWN_CHANCE * dt * 60:
            self.ufo = spawn_ufo_on_edge()
            ufo_channel.play(ufo_sound, loops=-1)
        if self.ufo:
            self.ufo.update(self.ship.x, self.ship.y, dt)
            active_missiles = [m for m in self.missile_manager.missiles if m.active]
            if not active_missiles and random.random() < self.ufo.missile_fire_chance * dt * 60:
                self.missile_manager.spawn_missile(self.ufo.x, self.ufo.y, self.ship)

        if not self.black_hole and random.random() < BLACK_HOLE_SPAWN_CHANCE * dt * 60:
            self.black_hole = spawn_black_hole()
        if self.black_hole:
            self.black_hole.update(dt)
            current_time = pygame.time.get_ticks()
            total_duration = (self.black_hole.fade_in_duration + 
                             self.black_hole.active_duration + 
                             self.black_hole.fade_out_duration)
            if (current_time - self.black_hole.spawn_time >= total_duration):
                self.black_hole.stop_sound()
                self.black_hole = None

        self.handle_collisions()

        if not self.asteroid_manager.asteroids:
            self.reset_for_new_wave()

        if self.wave_cleared and (pygame.time.get_ticks() - self.wave_cleared_start_time >= self.wave_cleared_duration):
            self.wave_cleared = False

        if self.lives <= 0 and not self.ship.pending_respawn:
            self.game_state = "GAME_OVER"
            if self.score > self.high_score:
                self.high_score = self.score
                save_high_score(self.high_score)

    def handle_collisions(self):
        self.score = self.asteroid_manager.handle_bullet_collisions(self.bullet_manager, self.explosion_manager, self.score)
        self.score = self.missile_manager.handle_bullet_collisions(self.bullet_manager, self.explosion_manager, self.score)

        if self.asteroid_manager.handle_ship_collision(self.ship):
            self.handle_ship_destruction()

        old_lives = self.lives
        self.lives = self.missile_manager.handle_ship_collision(self.ship, self.explosion_manager, self.lives)
        if self.lives < old_lives and self.lives <= 0:
            self.game_state = "GAME_OVER"

        if self.ufo:
            UFO_RADIUS = 45
            for b in self.bullet_manager.bullets[:]:
                bx, by = b[0], b[1]
                if math.sqrt((bx - self.ufo.x)**2 + (by - self.ufo.y)**2) < UFO_RADIUS:
                    ufo_poly = self.ufo.get_polygon()
                    if point_in_polygon(bx, by, ufo_poly):
                        self.explosion_manager.spawn_explosion(self.ufo.x, self.ufo.y, 3)
                        explosion_sound.play()
                        self.bullet_manager.bullets.remove(b)
                        self.ufo.health -= 1
                        if self.ufo.health <= 0:
                            self.explosion_manager.spawn_explosion(self.ufo.x, self.ufo.y, 20)
                            explosion_sound.play()
                            self.score += 200
                            self.ufo = None
                            if ufo_channel.get_busy():
                                ufo_channel.stop()
                        break

            if self.ufo and self.ship.spawned and not self.ship.invulnerable:
                ship_poly = self.ship.get_polygon()
                if math.sqrt((self.ship.x - self.ufo.x)**2 + (self.ship.y - self.ufo.y)**2) < (UFO_RADIUS + SHIP_RADIUS):
                    ufo_poly = self.ufo.get_polygon()
                    if polygons_collide(ship_poly, ufo_poly):
                        self.handle_ship_destruction()

            if self.ufo and self.ship.spawned and not self.ship.invulnerable:
                dist = math.sqrt((self.ship.x - self.ufo.x)**2 + (self.ship.y - self.ufo.y)**2)
                if dist < UFO_DETECTION_RADIUS:
                    pull_speed = 0.09
                    self.ship.vel_x = self.ship.vel_y = 0
                    angle_to_ufo = math.atan2(self.ufo.y - self.ship.y, self.ufo.x - self.ship.x)
                    self.ship.x += pull_speed * math.cos(angle_to_ufo)
                    self.ship.y += pull_speed * math.sin(angle_to_ufo)
                    self.ship.x, self.y = wrap_position(self.ship.x, self.ship.y)

        if self.black_hole and self.ship.spawned and self.black_hole.check_collision_with_ship(self.ship.x, self.ship.y) and self.black_hole.is_active():
            self.ship.trigger_respawn(0, 10000)  # Respawns at center with 10s invulnerability
            self.ship.rapid_fire = True
            self.ship.rapid_fire_start_time = pygame.time.get_ticks()
            self.ship.rapid_fire_duration = 10000
            self.missile_manager.clear()  # Clears all missiles
            self.ufo = None  # Clears the UFO
            if ufo_channel.get_busy():
                ufo_channel.stop()  # Stops UFO sound
            self.black_hole.stop_sound()
            self.black_hole = None

    def handle_ship_destruction(self):
        self.explosion_manager.spawn_explosion(self.ship.x, self.ship.y, 30)
        explosion_sound.play()
        self.lives -= 1
        self.ship.trigger_respawn(2000, 5000)
        self.missile_manager.clear()
        self.ufo = None
        if ufo_channel.get_busy():
            ufo_channel.stop()
        if self.black_hole:
            self.black_hole.stop_sound()
            self.black_hole = None

    def reset_for_new_wave(self):
        self.wave_count += 1
        self.ship.trigger_respawn(2000, 5000)
        self.ship.rapid_fire = False
        self.bullet_manager.clear()
        self.missile_manager.clear()
        self.explosion_manager.clear()
        self.ufo = None
        if ufo_channel.get_busy():
            ufo_channel.stop()
        if self.black_hole:
            self.black_hole.stop_sound()
            self.black_hole = None
        self.asteroid_manager.start_wave(self.wave_count, self.ship.x, self.ship.y)
        self.wave_cleared = True
        self.wave_cleared_start_time = pygame.time.get_ticks()

    def draw(self, surface):
        surface.fill(BLACK)
        if self.game_state == "MENU":
            for sx, sy in self.stars:
                surface.set_at((sx, sy), STAR_COLOR)
            t_text = self.large_font.render("Asteroids: Apocalypse", True, WHITE)
            surface.blit(t_text, t_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 250)))
            s_text = self.semilarge_font.render("Press Space to Start", True, WHITE)
            surface.blit(s_text, s_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 250)))
            instructions = [
                "Controls:",
                "Left/Right Arrow: Rotate Ship",
                "Up Arrow: Thrust",
                "Space: Shoot",
                "P: Pause",
                "F: Toggle Fullscreen",
                "Esc: Quit"
            ]
            for i, line in enumerate(instructions):
                instr_text = self.regular_font.render(line, True, WHITE)
                surface.blit(instr_text, instr_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 100 + i * 40)))
        elif self.game_state == "GAME_OVER":
            go_text = self.semilarge_font.render("GAME OVER!", True, WHITE)
            surface.blit(go_text, go_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 90)))
            score_text = self.regular_font.render(f"Your Score: {self.score}", True, WHITE)
            surface.blit(score_text, score_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 30)))
            high_score_text = self.regular_font.render(f"High Score: {self.high_score}", True, WHITE)
            surface.blit(high_score_text, high_score_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 30)))
            r_text = self.regular_font.render("Press R to Restart", True, WHITE)
            surface.blit(r_text, r_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 90)))
        elif self.game_state == "PAUSED":
            for sx, sy in self.stars:
                surface.set_at((sx, sy), STAR_COLOR)
            self.asteroid_manager.draw(surface)
            self.bullet_manager.draw(surface)
            self.explosion_manager.draw(surface)
            self.missile_manager.draw(surface)
            if self.ufo:
                self.ufo.draw(surface)
            if self.black_hole:
                self.black_hole.draw(surface)
            self.ship.draw(surface)
            paused_text = self.semilarge_font.render("PAUSED", True, WHITE)
            surface.blit(paused_text, paused_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 150)))
            for i, option in enumerate(self.pause_options):
                color = WHITE if i == self.selected_option else (150, 150, 150)
                opt_text = self.regular_font.render(option, True, color)
                surface.blit(opt_text, opt_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 50 + i * 50)))
        elif self.game_state == "PLAYING":
            for sx, sy in self.stars:
                surface.set_at((sx, sy), STAR_COLOR)
            self.asteroid_manager.draw(surface)
            self.bullet_manager.draw(surface)
            self.explosion_manager.draw(surface)
            self.missile_manager.draw(surface)
            if self.ufo:
                self.ufo.draw(surface)
                if math.sqrt((self.ship.x - self.ufo.x)**2 + (self.ship.y - self.ufo.y)**2) < UFO_DETECTION_RADIUS:
                    self.ufo.draw_tractor_beam(surface, self.ship.x, self.ship.y)
            if self.black_hole:
                self.black_hole.draw(surface)
            self.ship.draw(surface)
            score_text = self.tiny_font.render(f"Score: {self.score}", True, WHITE)
            surface.blit(score_text, (18, 18))
            for i in range(self.lives):
                ix = WIDTH - (self.lives * 36) - 18 + i * 36
                tip = (ix, 36 - 10.8)
                left = (ix - (5/6)*10.8, 36 + (5/6)*10.8)
                right = (ix + (5/6)*10.8, 36 + (5/6)*10.8)
                pygame.draw.line(surface, WHITE, tip, left, 2)
                pygame.draw.line(surface, WHITE, left, right, 2)
                pygame.draw.line(surface, WHITE, right, tip, 2)
            if self.wave_cleared:
                wave_text = self.semilarge_font.render(f"Level {self.wave_count - 1} Cleared!", True, WHITE)
                wave_rect = wave_text.get_rect(center=(WIDTH//2, HEIGHT//2))
                surface.blit(wave_text, wave_rect)

# --------------------------------------------------
# Main Loop
# --------------------------------------------------
def main():
    global screen
    running = True
    world = World()
    blackhole_channel.play(blackhole_sound, loops=-1)  # Play sound for menu
    fullscreen = False
    pygame.mouse.set_visible(False)  # Hide the cursor at all times

    while running:
        dt = clock.tick(FPS) / 1000  # Delta time in seconds
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN if fullscreen else 0)
                elif event.key == pygame.K_ESCAPE:
                    running = False
                elif world.game_state == "MENU" and event.key == pygame.K_SPACE:
                    if blackhole_channel.get_busy():
                        blackhole_channel.stop()  # Stop the menu black hole sound
                    world.reset_game()
                    world.game_state = "PLAYING"
                    world.bullet_manager.shoot_grace_timer = 15
                    world.asteroid_manager.start_wave(world.wave_count, world.ship.x, world.ship.y)
                elif world.game_state == "GAME_OVER" and event.key == pygame.K_r:
                    world.reset_game()
                    world.game_state = "PLAYING"
                    world.bullet_manager.shoot_grace_timer = 15
                    world.asteroid_manager.start_wave(world.wave_count, world.ship.x, world.ship.y)
                elif world.game_state in ["PLAYING", "PAUSED"] and event.key == pygame.K_p:
                    world.game_state = "PAUSED" if world.game_state == "PLAYING" else "PLAYING"
                    world.selected_option = 0  # Reset selection on pause

        world.handle_input(pygame.key.get_pressed())
        world.update(dt)
        world.draw(screen)
        pygame.display.flip()

    if blackhole_channel.get_busy():
        blackhole_channel.stop()
    pygame.quit()

if __name__ == "__main__":
    main()