"""
world.py – Obstacle, LawnWorld, and low-level pygame drawing helpers.
"""

import math
import random
import pygame
from typing import List

from src.constants import (
    GRASS_PAL, CUT_PAL,
    MOWER_COL, SENSOR_COL,
)


# ── Data classes ──────────────────────────────────────────────────────────────

class Obstacle:
    """A circular obstacle placed inside the lawn."""

    def __init__(self, x: float, y: float, radius: float) -> None:
        self.x = x
        self.y = y
        self.radius = radius


class LawnWorld:
    """
    Procedurally-generated lawn containing obstacles and renderable surfaces.
    """

    W: int = 1600
    H: int = 1200

    def __init__(self, seed: int, pal_idx: int, name: str) -> None:
        self.seed = seed
        self.pal_idx = pal_idx
        self.name = name
        self.obstacles: List[Obstacle] = []
        self._surf = None
        self._cut_surf = None
        self._gen(seed)

    # ── Generation ────────────────────────────────────────────────────────────

    def _gen(self, seed: int) -> None:
        """Populate obstacles with spacing / corridor constraints."""
        rng = random.Random(seed)
        self.obstacles = []
        self._elements = []

        for _ in range(rng.randint(6, 10)):
            for _ in range(200):
                margin = 120
                x = rng.randint(margin, self.W - margin)
                y = rng.randint(margin, self.H - margin)
                size_type = rng.choice(["small", "medium", "large"])
                r = {"small": rng.randint(12, 20),
                     "medium": rng.randint(25, 40),
                     "large": rng.randint(45, 65)}[size_type]

                valid = all(
                    math.hypot(x - o.x, y - o.y) >= o.radius + r + 80 and
                    not (abs(x - o.x) < 100 and abs(y - o.y) < o.radius + r + 120) and
                    not (abs(y - o.y) < 100 and abs(x - o.x) < o.radius + r + 120)
                    for o in self.obstacles
                )
                if valid:
                    self.obstacles.append(Obstacle(x, y, r))
                    self._elements.append(("obstacle", x, y, r))
                    break

    # ── Surface management ────────────────────────────────────────────────────

    def build_surface(self) -> pygame.Surface:
        """Render grass and obstacles into the world surface; reset cut overlay."""
        surf = pygame.Surface((self.W, self.H))
        pal  = GRASS_PAL[self.pal_idx % len(GRASS_PAL)]
        _grass_base(surf, (0, 0, self.W, self.H), pal, self.seed)
        for el in self._elements:
            if el[0] == "obstacle":
                _, x, y, r = el
                pygame.draw.circle(surf, (60, 60, 60),   (x, y), r)
                pygame.draw.circle(surf, (100, 100, 100), (x, y), r, 2)
        self._surf = surf
        self._cut_surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        return surf

    @property
    def surface(self) -> pygame.Surface:
        """Lazily build and return the world surface."""
        if self._surf is None:
            self.build_surface()
        return self._surf

    @property
    def cut_surface(self) -> pygame.Surface:
        """Lazily build and return the transparent cut-grass overlay."""
        if self._cut_surf is None:
            self.build_surface()
        return self._cut_surf

    def mark_cut(self, x: float, y: float, radius: int = 14) -> None:
        """Paint a cut-grass circle onto the cut overlay at (x, y)."""
        c = random.choice(CUT_PAL)
        pygame.draw.circle(self._cut_surf, (*c, 190), (int(x), int(y)), radius)

    def thumbnail(self, w: int, h: int) -> pygame.Surface:
        """Return a smoothly-scaled thumbnail of the world surface."""
        return pygame.transform.smoothscale(self.surface, (w, h))


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _grass_base(surf: pygame.Surface, rect: tuple, pal: list, seed: int = 0) -> None:
    """Fill a rectangle with a randomised grass texture using palette pal."""
    rx, ry, rw, rh = rect
    pygame.draw.rect(surf, pal[0], rect)
    rng = random.Random(seed + 1)
    for _ in range(rw * rh // 9):
        x = rx + rng.randint(0, rw - 1)
        y = ry + rng.randint(0, rh - 1)
        c = rng.choice(pal)
        pygame.draw.rect(surf, c, (x, y, rng.randint(4, 12), rng.randint(4, 12)))
    for _ in range(rw * rh // 50):
        x    = rx + rng.randint(0, rw - 1)
        y    = ry + rng.randint(0, rh - 1)
        h    = rng.randint(5, 14)
        lean = rng.randint(-3, 3)
        pygame.draw.line(surf, rng.choice(pal), (x, y), (x + lean, y - h), 1)


def draw_mower(surf: pygame.Surface, x: int, y: int, theta: float) -> None:
    """Render the top-down circular mower with direction arrow and sensor dots."""
    radius = 18
    pygame.draw.circle(surf, (40, 40, 40),   (int(x), int(y)), radius + 2)
    pygame.draw.circle(surf, MOWER_COL,      (int(x), int(y)), radius)
    pygame.draw.circle(surf, (200, 200, 200), (int(x), int(y)), radius // 2)
    pygame.draw.circle(surf, (230, 230, 230), (int(x), int(y)), radius // 2, 1)
    ax = x + math.cos(theta) * (radius + 6)
    ay = y + math.sin(theta) * (radius + 6)
    pygame.draw.line(surf, (255, 255, 255), (int(x), int(y)), (int(ax), int(ay)), 2)
    for off in [-math.pi / 3, math.pi / 3]:
        sx = x + math.cos(theta + off) * radius
        sy = y + math.sin(theta + off) * radius
        pygame.draw.circle(surf, (80, 220, 255), (int(sx), int(sy)), 3)


def draw_sensor_cone(
    surf: pygame.Surface,
    x: float, y: float,
    theta: float, angle_off: float,
    dist: int, fov: float = 0.35,
) -> None:
    """Render a single translucent ultrasonic sensor cone."""
    cone = pygame.Surface((dist * 2 + 4, dist * 2 + 4), pygame.SRCALPHA)
    cx, cy = dist + 2, dist + 2
    pts = [(cx, cy)]
    a0  = theta + angle_off - fov / 2
    for i in range(13):
        a = a0 + fov * i / 12
        pts.append((cx + math.cos(a) * dist, cy + math.sin(a) * dist))
    pygame.draw.polygon(cone, SENSOR_COL, pts)
    surf.blit(cone, (int(x) - dist - 2, int(y) - dist - 2))
