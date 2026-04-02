"""
planner.py – Demonstration recording, behaviour extraction, and path planning.

Implements spec §7.2 – §7.8:
  §7.2  DemoRecorder        – records mower pose + simulated ultrasonic ranges
  §7.3  extract_behaviour   – Savitzky-Golay smooth + curvature segmentation
  §7.4  BehaviourParams     – extracted parameter container
  §7.5  generate_lanes      – parallel coverage lanes from θ_pref / d_pass
  §7.6  bezier_turn         – cubic Bézier lane-end transition curves
  §7.7  obstacle_bypass     – S-curve bypass via two Bézier segments
  §7.8  build_full_path     – full waypoint list with bypasses and smoothing
"""

import math
from typing import List, Tuple

from src.constants import Vec2
from src.math_utils import (
    v2add, v2sub, v2scale, v2len, v2norm, v2dot, v2perp,
    angle_diff, sample_bezier,
    savgol_smooth, smooth_angle_list,
    clip_segment_to_rect,
)
from src.world import Obstacle


# ── §7.2  Demo recorder ───────────────────────────────────────────────────────

class DemoRecorder:
    """
    Records mower pose samples and simulated 3-zone ultrasonic range readings
    at a fixed sample rate during manual demonstration.
    """

    SAMPLE_HZ: int = 20

    def __init__(self) -> None:
        self.poses:  List[Tuple[float, float, float, float]] = []  # (x,y,θ,v)
        self.ranges: List[Tuple[float, float, float]] = []         # (left,centre,right)
        self._acc: float = 0.0

    def tick(
        self,
        dt: float,
        x: float, y: float, theta: float, v: float,
        obstacles: List[Obstacle],
        m_safe_hint: float = 40,
    ) -> None:
        """Accumulate dt and append a sample at SAMPLE_HZ; simulate sensor ranges."""
        self._acc += dt
        if self._acc < 1.0 / self.SAMPLE_HZ:
            return
        self._acc = 0.0
        ranges = []
        for off in [-math.pi / 6, 0, math.pi / 6]:
            a = theta + off
            dx, dy = math.cos(a), math.sin(a)
            best = 300.0
            for obs in obstacles:
                ox, oy = obs.x - x, obs.y - y
                proj = ox * dx + oy * dy
                if proj < 0:
                    continue
                perp = math.hypot(ox - proj * dx, oy - proj * dy)
                if perp < obs.radius:
                    hit = proj - math.sqrt(max(0, obs.radius ** 2 - perp ** 2))
                    if 0 < hit < best:
                        best = hit
            ranges.append(min(best, 300.0))
        self.poses.append((x, y, theta, v))
        self.ranges.append(tuple(ranges))


# ── §7.4  Behaviour parameter container ──────────────────────────────────────

class BehaviourParams:
    """Extracted behavioural parameters learned from demonstration."""

    def __init__(self) -> None:
        self.theta_pref: float = 0.0    # preferred mowing heading (radians)
        self.d_pass:     float = 50.0   # lane spacing (px)
        self.R_turn:     float = 60.0   # turning radius (px)
        self.M_safe:     float = 35.0   # safety margin around obstacles (px)
        self.V_pref:     float = 120.0  # preferred straight-line speed (px/s)
        self.start_u:    float = 0.0    # perpendicular offset of first lane


# ── §7.3  Behaviour extraction ────────────────────────────────────────────────

def extract_behaviour(
    poses:  List[Tuple[float, float, float, float]],
    ranges: List[Tuple[float, float, float]],
) -> Tuple[BehaviourParams, List[int], List[int]]:
    """
    Smooth the demo trajectory, segment by curvature, and extract
    θ_pref, d_pass, R_turn, M_safe, V_pref from straight and turning segments.
    Returns (params, straight_indices, turning_indices).
    """
    if len(poses) < 6:
        return BehaviourParams(), [], []

    xs  = [p[0] for p in poses]
    ys  = [p[1] for p in poses]
    ths = [p[2] for p in poses]
    vs  = [p[3] for p in poses]

    xs2  = savgol_smooth(xs,  window=9)
    ys2  = savgol_smooth(ys,  window=9)
    ths2 = smooth_angle_list(ths)
    vs2  = savgol_smooth(vs,  window=5)

    N = len(xs2)
    kappa = []
    for i in range(N - 1):
        ds  = math.hypot(xs2[i + 1] - xs2[i], ys2[i + 1] - ys2[i])
        dth = angle_diff(ths2[i + 1], ths2[i])
        kappa.append(abs(dth) / (ds + 1e-6))
    kappa.append(kappa[-1])

    kth          = 0.012
    straight_idx = [i for i in range(N) if kappa[i] <  kth]
    turning_idx  = [i for i in range(N) if kappa[i] >= kth]

    bp = BehaviourParams()
    bp.d_pass = max(40.0, min(50.0,  bp.d_pass))
    bp.R_turn = max(40.0, min(120.0, bp.R_turn))
    bp.M_safe = max(25.0, min(30.0,  bp.M_safe))
    bp.V_pref = max(80.0, min(160.0, bp.V_pref))

    # ── θ_pref via orientation histogram ─────────────────────────────────────
    if straight_idx:
        dirs = []
        for i in straight_idx:
            th = ths2[i]
            vx, vy = math.cos(th), math.sin(th)
            if dirs:
                rx = sum(d[0] for d in dirs)
                ry = sum(d[1] for d in dirs)
                if vx * rx + vy * ry < 0:
                    vx, vy = -vx, -vy
            dirs.append((vx, vy))

        if dirs:
            mx = sum(d[0] for d in dirs)
            my = sum(d[1] for d in dirs)
            bp.theta_pref = math.atan2(my, mx)

        nx = -math.sin(bp.theta_pref)
        ny =  math.cos(bp.theta_pref)
        first_i    = straight_idx[0]
        bp.start_u = nx * xs2[first_i] + ny * ys2[first_i]

        us = [nx * xs2[i] + ny * ys2[i] for i in straight_idx]
        us.sort()
        clusters: list = []
        current  = [us[0]]
        for u in us[1:]:
            if abs(u - current[-1]) < 25:
                current.append(u)
            else:
                clusters.append(current)
                current = [u]
            clusters.append(current)

        centers = [sum(c) / len(c) for c in clusters]
        diffs   = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
        if diffs:
            bp.d_pass = sum(diffs) / len(diffs)
        bp.d_pass = max(38.0, min(50.0, bp.d_pass))

        sv = [vs2[i] for i in straight_idx if vs2[i] > 5]
        if sv:
            sv.sort()
            sv = sv[len(sv) // 10: len(sv) - len(sv) // 10]
            bp.V_pref = max(60.0, sum(sv) / max(1, len(sv)))

        # Snap theta_pref to dominant axis (0 or π/2)
        angles       = [0, math.pi / 2]
        bp.theta_pref = min(angles, key=lambda a: abs(angle_diff(bp.theta_pref, a)))

        # ── d_pass via lateral clustering (second pass) ───────────────────────
        nx2 = -math.sin(bp.theta_pref)
        ny2 =  math.cos(bp.theta_pref)
        us2 = [nx2 * xs2[i] + ny2 * ys2[i] for i in straight_idx]
        us2.sort()
        clusters2: list = []
        cur2 = [us2[0]]
        for u in us2[1:]:
            if abs(u - cur2[-1]) < 25:
                cur2.append(u)
            else:
                clusters2.append(cur2)
                cur2 = [u]
        clusters2.append(cur2)
        centers2 = [sum(c) / len(c) for c in clusters2]
        diffs2   = [centers2[i + 1] - centers2[i] for i in range(len(centers2) - 1)]
        if diffs2:
            bp.d_pass = sum(diffs2) / len(diffs2)
        bp.d_pass = max(50.0, min(50.0, bp.d_pass))

        sv2 = [vs2[i] for i in straight_idx if vs2[i] > 5]
        if sv2:
            sv2.sort()
            sv2 = sv2[len(sv2) // 10: len(sv2) - len(sv2) // 10]
            bp.V_pref = max(60.0, sum(sv2) / max(1, len(sv2)))

    # ── R_turn via median curvature radius ───────────────────────────────────
    if turning_idx:
        rs = [1.0 / max(kappa[i], 1e-6) for i in turning_idx if kappa[i] > kth]
        rs.sort()
        bp.R_turn = max(20.0, min(200.0, rs[len(rs) // 2]))

    # ── M_safe via lower-quartile minimum range ───────────────────────────────
    near = [min(rl, rc, rr) for rl, rc, rr in ranges if min(rl, rc, rr) < 200]
    if near:
        near.sort()
        bp.M_safe = min(30.0, max(20.0, near[int(len(near) * 0.25)]))
    bp.M_safe = max(20.0, min(30.0, bp.M_safe))

    return bp, straight_idx, turning_idx


# ── §7.5  Lane generation ─────────────────────────────────────────────────────

class Lane:
    """A single straight mowing lane defined by start/end world coordinates."""

    def __init__(
        self,
        index: int,
        p_start: Vec2,
        p_end: Vec2,
        completed: bool = False,
    ) -> None:
        self.index     = index
        self.p_start   = p_start
        self.p_end     = p_end
        self.completed = completed


def generate_lanes(bp: BehaviourParams, W: int, H: int) -> List[Lane]:
    """
    Generate a full set of parallel coverage lanes across the lawn,
    snapped to the nearest cardinal axis and ordered closest-first.
    """
    angles = [0, math.pi / 2, math.pi, 3 * math.pi / 2]
    th = min(angles, key=lambda a: abs(angle_diff(bp.theta_pref, a)))
    dx, dy = math.cos(th), math.sin(th)
    nx, ny = -dy, dx

    corners = [(0, 0), (W, 0), (W, H), (0, H)]
    us      = [nx * cx + ny * cy for cx, cy in corners]
    u_min, u_max = min(us), max(us)
    dp   = bp.d_pass * 0.75

    lanes = []
    idx   = 0
    u     = u_min
    while u <= u_max + dp * 0.1:
        cx, cy = nx * u, ny * u
        ts = [dx * (cx2 - cx) + dy * (cy2 - cy) for cx2, cy2 in corners]
        t_min, t_max = min(ts) - 50, max(ts) + 50
        p1 = (cx + dx * t_min, cy + dy * t_min)
        p2 = (cx + dx * t_max, cy + dy * t_max)
        clipped = clip_segment_to_rect(p1, p2, (0, 0, W, H))
        if clipped:
            if idx % 2 == 0:
                lanes.append(Lane(idx, clipped[0], clipped[1]))
            else:
                lanes.append(Lane(idx, clipped[1], clipped[0]))
        u   += dp
        idx += 1

    # Extend endpoints slightly beyond lawn edges
    for lane in lanes:
        d = v2norm(v2sub(lane.p_end, lane.p_start))
        lane.p_start = v2sub(lane.p_start, v2scale(d, 20))
        lane.p_end   = v2add(lane.p_end,   v2scale(d, 20))

    # Order so the lane closest to demo start is first
    if lanes:
        def lane_u(lane: Lane) -> float:
            mx = (lane.p_start[0] + lane.p_end[0]) * 0.5
            my = (lane.p_start[1] + lane.p_end[1]) * 0.5
            return nx * mx + ny * my

        if abs(lane_u(lanes[-1]) - bp.start_u) < abs(lane_u(lanes[0]) - bp.start_u):
            lanes.reverse()
        for i, lane in enumerate(lanes):
            lane.index = i

    return lanes


# ── §7.6  Bézier turn transitions ────────────────────────────────────────────

def bezier_turn(lane_a: Lane, lane_b: Lane, R_turn: float) -> List[Vec2]:
    """Cubic Bézier arc connecting the end of lane_a to the start of lane_b."""
    P0 = lane_a.p_end
    P3 = lane_b.p_start
    t0  = v2norm(v2sub(lane_a.p_end,   lane_a.p_start))
    t3  = v2norm(v2sub(lane_b.p_end,   lane_b.p_start))
    lam = 0.9 * R_turn
    P1  = v2add(P0, v2scale(t0,  lam))
    P2  = v2sub(P3, v2scale(t3, lam))
    return sample_bezier(P0, P1, P2, P3, n=28)


# ── §7.7  Obstacle S-curve bypass ────────────────────────────────────────────

def obstacle_bypass(
    p_entry: Vec2, p_exit: Vec2,
    obs: Obstacle, M_safe: float, R_turn: float,
) -> List[Vec2]:
    """
    Generate a smooth S-curve detour around an obstacle using two Bézier arcs.
    The bypass side (left/right) is chosen to minimise lateral deviation.
    """
    lane_dir = v2norm(v2sub(p_exit, p_entry))
    perp     = v2perp(lane_dir)
    offset   = obs.radius + M_safe + 20
    mid_x    = (p_entry[0] + p_exit[0]) * 0.5
    mid_y    = (p_entry[1] + p_exit[1]) * 0.5
    side     = 1 if v2dot(perp, (obs.x - mid_x, obs.y - mid_y)) < 0 else -1
    P_mid    = (obs.x + perp[0] * offset * side, obs.y + perp[1] * offset * side)
    lam      = 0.5 * R_turn

    t_in  = lane_dir
    t_out = v2norm(v2sub(p_exit, P_mid))
    P1a   = v2add(p_entry, v2scale(t_in,  lam))
    P2a   = v2sub(P_mid,   v2scale(t_out, lam))
    seg1  = sample_bezier(p_entry, P1a, P2a, P_mid, n=18)

    t_in2  = t_out
    t_out2 = lane_dir
    P1b    = v2add(P_mid,  v2scale(t_in2,  lam))
    P2b    = v2sub(p_exit, v2scale(t_out2, lam))
    seg2   = sample_bezier(P_mid, P1b, P2b, p_exit, n=18)

    return seg1[:-1] + seg2


# ── §7.8  Full path construction ──────────────────────────────────────────────

def build_full_path(
    lanes:     List[Lane],
    bp:        BehaviourParams,
    obstacles: List[Obstacle],
) -> List[Tuple[float, float, float, float]]:
    """
    Build the complete ordered waypoint list (x, y, θ, v) by combining lane
    straights, obstacle bypasses, and Bézier turn transitions, then applying
    a 5-point running-average smoothing pass.
    """

    def seg_waypoints(
        p_start: Vec2, p_end: Vec2,
        v_straight: float,
        obstacles: List[Obstacle],
        bp: BehaviourParams,
    ) -> List[Tuple[float, float, float, float]]:
        """Waypoints for one straight segment, inserting detours around obstacles."""
        pts     = []
        seg_dir = v2norm(v2sub(p_end, p_start))
        th      = math.atan2(seg_dir[1], seg_dir[0])
        byp_obs = []
        for obs in obstacles:
            lx, ly = v2sub((obs.x, obs.y), p_start)
            proj   = v2dot((lx, ly), seg_dir)
            if proj < 0 or proj > v2len(v2sub(p_end, p_start)):
                continue
            perp_dist = abs(lx * seg_dir[1] - ly * seg_dir[0])
            if perp_dist < obs.radius + bp.M_safe + 18:
                byp_obs.append((proj, obs))
        byp_obs.sort(key=lambda x: x[0])
        cur = p_start
        for _, obs in byp_obs:
            entry = v2sub((obs.x, obs.y), v2scale(seg_dir, obs.radius + bp.M_safe + 20))
            ep    = v2add(p_start, v2scale(seg_dir, max(0, min(
                v2len(v2sub(p_end, p_start)),
                v2dot(v2sub(entry, p_start), seg_dir)
            ))))
            xp    = v2add(p_start, v2scale(seg_dir, min(
                v2len(v2sub(p_end, p_start)),
                v2dot(v2sub((obs.x, obs.y), p_start), seg_dir) + obs.radius + bp.M_safe + 20
            )))
            n_mid = max(2, int(v2len(v2sub(ep, cur)) / 8))
            for j in range(n_mid):
                t = j / (n_mid - 1) if n_mid > 1 else 0
                p = v2add(cur, v2scale(v2sub(ep, cur), t))
                pts.append((p[0], p[1], th, v_straight))
            for p in obstacle_bypass(ep, xp, obs, bp.M_safe, bp.R_turn):
                d = v2norm(v2sub(xp, ep))
                pts.append((p[0], p[1], math.atan2(d[1], d[0]), v_straight * 0.45))
            cur = xp
        n_end = max(2, int(v2len(v2sub(p_end, cur)) / 8))
        for j in range(n_end):
            t = j / (n_end - 1) if n_end > 1 else 0
            p = v2add(cur, v2scale(v2sub(p_end, cur), t))
            pts.append((p[0], p[1], th, v_straight))
        return pts

    all_wp: List[Tuple[float, float, float, float]] = []
    for i, lane in enumerate(lanes):
        all_wp.extend(seg_waypoints(lane.p_start, lane.p_end, bp.V_pref, obstacles, bp))
        if i + 1 < len(lanes):
            turn_pts = bezier_turn(lane, lanes[i + 1], bp.R_turn)
            for j, p in enumerate(turn_pts):
                if j + 1 < len(turn_pts):
                    nxt = turn_pts[j + 1]
                    th  = math.atan2(nxt[1] - p[1], nxt[0] - p[0])
                else:
                    th = math.atan2(
                        lanes[i + 1].p_end[1] - lanes[i + 1].p_start[1],
                        lanes[i + 1].p_end[0] - lanes[i + 1].p_start[0],
                    )
                all_wp.append((p[0], p[1], th, bp.V_pref * 0.55))

    # 5-point running-average smoothing pass
    if len(all_wp) >= 3:
        smoothed = [all_wp[0]]
        for i in range(1, len(all_wp) - 1):
            if 1 < i < len(all_wp) - 2:
                x = sum(all_wp[i + k][0] for k in range(-2, 3)) / 5
                y = sum(all_wp[i + k][1] for k in range(-2, 3)) / 5
            else:
                x, y = all_wp[i][0], all_wp[i][1]
            x = max(10, min(1590, x))
            y = max(10, min(1190, y))
            smoothed.append((x, y, all_wp[i][2], all_wp[i][3]))
        smoothed.append(all_wp[-1])
        return smoothed

    return all_wp