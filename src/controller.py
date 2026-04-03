"""
controller.py – Autonomous mower controller (spec §7.9).

Implements pure-pursuit heading control, obstacle avoidance side-bias,
stuck detection, and cut-grass marking.
"""

import math
from typing import List, Tuple

from src.planner import BehaviourParams
from src.world   import Obstacle, LawnWorld


class AutoMower:
    """
    Tracks a pre-planned waypoint path, avoids obstacles in real time,
    and paints cut-grass marks onto the LawnWorld surface.
    """

    Kp:        float = 1.2   # proportional heading gain (legacy, kept for reference)
    LOOKAHEAD: int   = 0     # extra waypoint look-ahead index
    CUT_HALF:  int   = 22    # half-side of the square cut-grass mark (px)

    def __init__(
        self,
        waypoints:  List[Tuple[float, float, float, float]],
        bp:         BehaviourParams,
        lane_count: int,
    ) -> None:
        self.waypoints   = waypoints
        self.bp          = bp
        self.lane_count  = lane_count
        self.idx         = 0
        self.x           = float(waypoints[0][0]) if waypoints else 400.0
        self.y           = float(waypoints[0][1]) if waypoints else 400.0
        self.theta       = float(waypoints[0][2]) if waypoints else 0.0
        self.v           = 0.0
        self.done        = False
        self.sensor_ranges: List[float] = [300.0, 300.0, 300.0]
        self.avoid_side: int            = 0   # -1 left, +1 right, 0 none
        self._cut_acc:   float          = 0.0
        self.prev_positions: List[Tuple[float, float]] = []

    # ── Per-frame update ──────────────────────────────────────────────────────

    def update(self, dt: float, obstacles: List[Obstacle], lawn: LawnWorld) -> None:
        """Advance the mower physics, avoidance, sensor model, and grass cutting."""
        if self.done or not self.waypoints:
            return

        # ── Stuck detection ───────────────────────────────────────────────────
        self.prev_positions.append((self.x, self.y))
        if len(self.prev_positions) > 20:
            self.prev_positions.pop(0)
        stuck = (
            len(self.prev_positions) >= 20 and
            math.hypot(
                self.x - self.prev_positions[0][0],
                self.y - self.prev_positions[0][1],
            ) < 10
        )

        # ── Pure-pursuit: find first waypoint beyond lookahead distance ───────
        target = None
        for i in range(self.idx, min(self.idx + 20, len(self.waypoints))):
            wx, wy, _, _ = self.waypoints[i]
            if math.hypot(wx - self.x, wy - self.y) > 20:
                target = (wx, wy)
                break
        if target is None:
            target = self.waypoints[min(self.idx + 1, len(self.waypoints) - 1)][:2]
        tx, ty = target

        # ── Obstacle side-avoidance bias ──────────────────────────────────────
        closest, closest_d = None, 9999.0
        for obs in obstacles:
            ox, oy = obs.x - self.x, obs.y - self.y
            dist   = math.hypot(ox, oy)
            if (ox * math.cos(self.theta) + oy * math.sin(self.theta)) > 0 and dist < closest_d:
                closest, closest_d = obs, dist

        if closest and closest_d < 120:
            ox, oy = closest.x - self.x, closest.y - self.y
            perp_x, perp_y = -math.sin(self.theta), math.cos(self.theta)
            if self.avoid_side == 0:
                self.avoid_side = -1 if (ox * perp_x + oy * perp_y) > 0 else 1

        if self.avoid_side != 0:
            perp_x, perp_y = -math.sin(self.theta), math.cos(self.theta)

        if closest is None or closest_d > 160:
            self.avoid_side = 0

        # ── Heading + speed control ───────────────────────────────────────────
        dx, dy = tx - self.x, ty - self.y
        if stuck:
            dx, dy = tx - self.x, ty - self.y   # ignore avoidance when stuck

        alpha    = math.atan2(dy, dx) - self.theta
        alpha    = (alpha + math.pi) % (2 * math.pi) - math.pi
        L        = max(1.0, math.hypot(dx, dy))
        curvature = 3 * math.sin(alpha) / L

        self.theta += curvature * self.v * dt
        self.theta  = (self.theta + math.pi) % (2 * math.pi) - math.pi

        t_v = self.waypoints[min(self.idx + self.LOOKAHEAD, len(self.waypoints) - 1)][3]
        self.v = max(60.0, t_v * (1 - 0.5 * min(1.0, abs(curvature) * 20)))

        # ── Move and clamp to lawn bounds ─────────────────────────────────────
        self.x += math.cos(self.theta) * self.v * dt
        self.y += math.sin(self.theta) * self.v * dt
        self.x  = max(20.0, min(1580.0, self.x))
        self.y  = max(20.0, min(1180.0, self.y))

        # ── Hard push-out from obstacle interiors ─────────────────────────────
        for obs in obstacles:
            dx2, dy2 = self.x - obs.x, self.y - obs.y
            d = math.hypot(dx2, dy2)
            min_dist = obs.radius + self.bp.M_safe
            if 1e-3 < d < min_dist:
                overlap = min_dist - d
                self.x += (dx2 / d) * overlap * 0.5
                self.y += (dy2 / d) * overlap * 0.5

        # ── Advance waypoint index ────────────────────────────────────────────
        for i in range(self.idx, min(self.idx + self.LOOKAHEAD + 5, len(self.waypoints))):
            wx, wy, _, _ = self.waypoints[i]
            if math.hypot(self.x - wx, self.y - wy) < 20:
                self.idx = max(self.idx, i + 1)
        if self.idx >= len(self.waypoints) - 1:
            self.done = True

        # ── Sensor ray-cast ───────────────────────────────────────────────────
        for si, off in enumerate([-math.pi / 6, 0, math.pi / 6]):
            a = self.theta + off
            cdx, cdy = math.cos(a), math.sin(a)
            best = 300.0
            for obs in obstacles:
                ox, oy = obs.x - self.x, obs.y - self.y
                proj   = ox * cdx + oy * cdy
                if proj < 0:
                    continue
                perp = math.hypot(ox - proj * cdx, oy - proj * cdy)
                if perp < obs.radius:
                    hit = proj - math.sqrt(max(0, obs.radius ** 2 - perp ** 2))
                    if 0 < hit < best:
                        best = hit
            self.sensor_ranges[si] = min(best, 300.0)

        # ── Mark cut grass (square patch, rotated with mower heading) ─────────
        self._cut_acc += dt
        if self._cut_acc > 0.05:
            self._cut_acc = 0.0
            lawn.mark_cut(self.x, self.y, self.CUT_HALF, self.theta)

    def progress(self) -> float:
        """Return completion fraction in [0, 1]."""
        if not self.waypoints:
            return 1.0
        return min(1.0, self.idx / len(self.waypoints))
