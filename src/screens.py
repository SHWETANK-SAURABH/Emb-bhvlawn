"""
screens.py – The four game screens: Chooser, Demo, Learning, and Auto.

Each run_* function takes a pygame screen surface and returns the mutated
screen (which may be replaced on VIDEORESIZE events).
"""

import math
import random
import sys
import pygame
from typing import List, Optional, Tuple

from src.constants import (
    BG_DARK, CARD_IDLE, CARD_HOV, CARD_SEL,
    B_IDLE, B_HOV, B_SEL, T_HI, T_MID, T_DIM,
    BTN_A, BTN_H, BTN_D, BTN_T,
)
from src.world      import LawnWorld, draw_mower, draw_sensor_cone
from src.planner    import (
    DemoRecorder, BehaviourParams, Lane,
    extract_behaviour, generate_lanes, build_full_path, bezier_turn,
)
from src.controller import AutoMower


# Fonts are injected at startup from main.py
_FONTS: dict = {}


def set_fonts(fonts: dict) -> None:
    """Receive the application fonts from main.py after pygame.init."""
    global _FONTS
    _FONTS = fonts


def _f(key: str) -> pygame.font.Font:
    return _FONTS[key]


# ── Chooser ───────────────────────────────────────────────────────────────────

def run_chooser(screen: pygame.Surface, lawns: List[LawnWorld]):
    """
    Display four lawn thumbnails for selection.
    Returns (selected_index | 'regen', screen).
    """
    clock       = pygame.time.Clock()
    selected    = None
    thumb_cache = {}
    NAMES       = [l.name for l in lawns]

    while True:
        sw, sh   = screen.get_size()
        margin_x = max(38, int(sw * 0.04))
        margin_y = max(75, int(sh * 0.11))
        gap_x    = max(22, int(sw * 0.024))
        gap_y    = max(24, int(sh * 0.038))
        tw       = max(150, (sw - margin_x * 2 - gap_x) // 2)
        th       = max(110, (sh - margin_y - gap_y - int(sh * 0.13)) // 2)
        key      = (tw, th)
        if key not in thumb_cache:
            thumb_cache = {key: [l.thumbnail(tw, th) for l in lawns]}
        thumbs = thumb_cache[key]

        def card_rect(i: int) -> pygame.Rect:
            c, r = i % 2, i // 2
            return pygame.Rect(
                margin_x + c * (tw + gap_x),
                margin_y + r * (th + gap_y),
                tw, th,
            )

        mx, my  = pygame.mouse.get_pos()
        hov     = next((i for i in range(4) if card_rect(i).collidepoint(mx, my)), None)
        btn_w   = max(180, int(sw * 0.17))
        btn_r   = pygame.Rect(sw // 2 - btn_w // 2, sh - int(sh * 0.09), btn_w, 44)
        btn_on  = selected is not None
        btn_hv  = btn_r.collidepoint(mx, my) and btn_on
        regen_r = pygame.Rect(sw - int(sw * 0.15) - 18, 16, int(sw * 0.15), 34)
        regen_hv = regen_r.collidepoint(mx, my)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE | pygame.DOUBLEBUF)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if hov is not None:
                    selected = hov
                if btn_hv:
                    return selected, screen
                if regen_hv:
                    return "regen", screen

        screen.fill(BG_DARK)
        t = _f("FT").render("🌿  Choose Your Lawn", True, T_HI)
        screen.blit(t, (sw // 2 - t.get_width() // 2, 12))
        h = _f("FS").render("Click layout · resize freely · Confirm to start demo", True, T_DIM)
        screen.blit(h, (sw // 2 - h.get_width() // 2, 54))

        for i in range(4):
            rect = card_rect(i)
            is_s, is_h = (i == selected), (i == hov)
            pygame.draw.rect(screen, (5, 10, 5), rect.move(4, 4), border_radius=10)
            bg = CARD_SEL if is_s else (CARD_HOV if is_h else CARD_IDLE)
            pygame.draw.rect(screen, bg, rect, border_radius=10)
            screen.blit(pygame.transform.scale(thumbs[i], (rect.w - 4, rect.h - 34)), (rect.x + 2, rect.y + 2))
            bar = pygame.Rect(rect.x, rect.y + rect.h - 32, rect.w, 32)
            pygame.draw.rect(screen, (8, 16, 8), bar)
            ns = _f("FC").render(NAMES[i], True, B_SEL if is_s else T_MID)
            screen.blit(ns, (bar.x + 7, bar.y + 8))
            if is_s:
                ck = _f("FS").render("✔", True, B_SEL)
                screen.blit(ck, (bar.right - ck.get_width() - 8, bar.y + 10))
            bc = B_SEL if is_s else (B_HOV if is_h else B_IDLE)
            pygame.draw.rect(screen, bc, rect, 3 if is_s else 1, border_radius=10)
            screen.blit(_f("FS").render(f"#{i+1}", True, B_SEL if is_s else T_DIM), (rect.x + 6, rect.y + 5))

        pygame.draw.rect(screen, BTN_H if btn_hv else (BTN_A if btn_on else BTN_D), btn_r, border_radius=10)
        bt = _f("FM").render("Start Demo  →", True, BTN_T if btn_on else T_DIM)
        screen.blit(bt, (btn_r.x + btn_r.w // 2 - bt.get_width() // 2,
                         btn_r.y + btn_r.h // 2 - bt.get_height() // 2))
        rc = (50, 92, 44) if regen_hv else (33, 62, 28)
        pygame.draw.rect(screen, rc, regen_r, border_radius=8)
        rt = _f("FS").render("⟳  New Layouts", True, T_MID)
        screen.blit(rt, (regen_r.x + regen_r.w // 2 - rt.get_width() // 2,
                         regen_r.y + regen_r.h // 2 - rt.get_height() // 2))
        pygame.display.flip()
        clock.tick(60)


# ── Demo ──────────────────────────────────────────────────────────────────────

def run_demo(
    screen: pygame.Surface, lawn: LawnWorld
) -> Tuple[Optional[DemoRecorder], pygame.Surface]:
    """
    Manual driving screen where the user demonstrates mowing behaviour.
    Arrow keys to drive; SPACE to finish, ESC to go back.
    Returns (recorder | None, screen).
    """
    clock     = pygame.time.Clock()
    rec       = DemoRecorder()
    lawn_surf = lawn.surface
    mx2 = float(lawn.W // 2)
    my2 = float(lawn.H // 2)
    theta = 0.0
    v     = 0.0
    SPEED = 160.0
    trail: list = []

    while True:
        dt      = clock.tick(60) / 1000.0
        sw, sh  = screen.get_size()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE | pygame.DOUBLEBUF)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    return rec, screen
                if event.key == pygame.K_ESCAPE:
                    return None, screen

        keys = pygame.key.get_pressed()
        vx = vy = 0
        if keys[pygame.K_UP]:    vy -= 1
        if keys[pygame.K_DOWN]:  vy += 1
        if keys[pygame.K_LEFT]:  vx -= 1
        if keys[pygame.K_RIGHT]: vx += 1
        if vx or vy:
            mag   = math.hypot(vx, vy)
            theta = math.atan2(vy / mag, vx / mag)
            v     = SPEED
        else:
            v = 0

        nx2 = max(20, min(lawn.W - 20, mx2 + math.cos(theta) * v * dt))
        ny2 = max(20, min(lawn.H - 20, my2 + math.sin(theta) * v * dt))
        for obs in lawn.obstacles:
            d = math.hypot(nx2 - obs.x, ny2 - obs.y)
            if d < obs.radius + 16:
                ang = math.atan2(ny2 - obs.y, nx2 - obs.x)
                nx2 = obs.x + math.cos(ang) * (obs.radius + 17)
                ny2 = obs.y + math.sin(ang) * (obs.radius + 17)
        mx2, my2 = nx2, ny2
        rec.tick(dt, mx2, my2, theta, abs(v), lawn.obstacles)
        if v > 0:
            trail.append((int(mx2), int(my2)))
            if len(trail) > 3000:
                trail = trail[-2000:]

        cam_x = max(0, min(lawn.W - sw, int(mx2 - sw // 2)))
        cam_y = max(0, min(lawn.H - sh, int(my2 - sh // 2)))
        screen.blit(lawn_surf, (0, 0), pygame.Rect(cam_x, cam_y, min(sw, lawn.W), min(sh, lawn.H)))

        if len(trail) > 2:
            rel = [(p[0] - cam_x, p[1] - cam_y) for p in trail[-800:]]
            ts  = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for j in range(1, len(rel)):
                a = max(30, int(180 * (j / len(rel))))
                pygame.draw.line(ts, (255, 255, 80, a), rel[j - 1], rel[j], 3)
            screen.blit(ts, (0, 0))

        for si, off in enumerate([-math.pi / 6, 0, math.pi / 6]):
            r = min(rec.ranges[-1][si] if rec.ranges else 300, 200)
            draw_sensor_cone(screen, mx2 - cam_x, my2 - cam_y, theta, off, int(r))
        draw_mower(screen, int(mx2 - cam_x), int(my2 - cam_y), theta)

        hud = pygame.Surface((380, 110), pygame.SRCALPHA)
        hud.fill((8, 16, 8, 190))
        pygame.draw.rect(hud, (60, 110, 50), (0, 0, 380, 110), 1, border_radius=8)
        hud.blit(_f("FM").render("DEMO  MODE", True, (120, 220, 80)), (10, 8))
        hud.blit(_f("FS").render("Drive the mower over the entire lawn", True, T_MID), (10, 34))
        hud.blit(_f("FS").render("Arrow keys to steer", True, T_DIM), (10, 52))
        hud.blit(_f("FS").render(
            f"Samples: {len(rec.poses):4d}   SPACE=finish   ESC=back", True, T_DIM), (10, 70))
        sensor_txt = (
            f"Sensors  L:{rec.ranges[-1][0]:.0f}  C:{rec.ranges[-1][1]:.0f}  R:{rec.ranges[-1][2]:.0f}"
            if rec.ranges else "Sensors: --"
        )
        hud.blit(_f("FS").render(sensor_txt, True, (80, 200, 220)), (10, 88))
        screen.blit(hud, (12, 12))

        mmw = max(90, int(sw * 0.09))
        mmh = int(mmw * lawn.H / lawn.W)
        mms = pygame.Surface((mmw, mmh), pygame.SRCALPHA)
        mms.fill((40, 80, 40, 160))
        for p in trail[::5]:
            pygame.draw.circle(mms, (255, 240, 80, 120),
                               (int(p[0] / lawn.W * mmw), int(p[1] / lawn.H * mmh)), 1)
        pygame.draw.circle(mms, (255, 220, 40),
                           (int(mx2 / lawn.W * mmw), int(my2 / lawn.H * mmh)), 4)
        pygame.draw.rect(mms, (80, 140, 60), (0, 0, mmw, mmh), 1)
        screen.blit(mms, (sw - mmw - 12, 12))
        pygame.display.flip()


# ── Learning ──────────────────────────────────────────────────────────────────

def run_learning(
    screen: pygame.Surface,
    lawn:   LawnWorld,
    rec:    DemoRecorder,
) -> Tuple[BehaviourParams, List[Lane], list, pygame.Surface]:
    """
    Animated analysis panel showing extracted parameters and plan preview.
    Returns (bp, lanes, waypoints, screen) when the user proceeds.
    """
    clock = pygame.time.Clock()
    bp, straight_idx, turning_idx = extract_behaviour(rec.poses, rec.ranges)
    lanes     = generate_lanes(bp, lawn.W, lawn.H)
    waypoints = build_full_path(lanes, bp, lawn.obstacles)

    steps = [
        ("Smoothing trajectory (Savitzky-Golay)...",                 0.8),
        ("Segmenting by curvature κ...",                              0.8),
        (f"θ_pref = {math.degrees(bp.theta_pref):.1f}°",             0.7),
        (f"d_pass = {bp.d_pass:.1f} px",                             0.7),
        (f"R_turn = {bp.R_turn:.1f} px",                             0.7),
        (f"M_safe = {bp.M_safe:.1f} px",                             0.7),
        (f"V_pref = {bp.V_pref:.1f} px/s",                           0.7),
        ("Generating parallel coverage lanes...",                     0.8),
        ("Building Bézier turn transitions...",                       0.8),
        ("Planning obstacle bypass S-curves...",                      0.8),
        (f"Total waypoints: {len(waypoints)}  |  Lanes: {len(lanes)}", 0.5),
        ("✅  Ready to mow autonomously!",                            1.0),
    ]
    revealed: list = []
    step_i = 0
    acc    = 0.0
    done_anim = False
    start_btn = pygame.Rect(0, 0, 220, 46)

    while True:
        dt     = clock.tick(60) / 1000.0
        sw, sh = screen.get_size()
        start_btn.center = (sw // 2, sh - 55)
        mx2, my2 = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE | pygame.DOUBLEBUF)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if done_anim and start_btn.collidepoint(mx2, my2):
                    return bp, lanes, waypoints, screen
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN and done_anim:
                return bp, lanes, waypoints, screen

        if not done_anim:
            acc += dt
            if step_i < len(steps) and acc >= steps[step_i][1]:
                revealed.append(steps[step_i][0])
                step_i += 1
                acc = 0.0
                if step_i >= len(steps):
                    done_anim = True

        screen.fill(BG_DARK)
        title = _f("FT").render("🧠  Learning from Demonstration", True, T_HI)
        screen.blit(title, (sw // 2 - title.get_width() // 2, 16))
        sub = _f("FS").render(
            f"Demo samples: {len(rec.poses)}   "
            f"Straight pts: {len(straight_idx)}   "
            f"Turn pts: {len(turning_idx)}", True, T_DIM)
        screen.blit(sub, (sw // 2 - sub.get_width() // 2, 58))

        # Lane preview
        preview_w = min(340, sw // 3)
        preview_h = int(preview_w * lawn.H / lawn.W)
        px, py    = sw // 2 + 60, 80
        if px + preview_w < sw and py + preview_h < sh - 80:
            scx, scy = preview_w / lawn.W, preview_h / lawn.H
            pygame.draw.rect(screen, (20, 40, 20),  (px, py, preview_w, preview_h))
            pygame.draw.rect(screen, (50, 90, 45),  (px, py, preview_w, preview_h), 1)
            for lane in lanes:
                p1 = (px + int(lane.p_start[0] * scx), py + int(lane.p_start[1] * scy))
                p2 = (px + int(lane.p_end[0]   * scx), py + int(lane.p_end[1]   * scy))
                pygame.draw.line(screen, (60, 160, 240, 160), p1, p2, 1)
            for i in range(len(lanes) - 1):
                pts = bezier_turn(lanes[i], lanes[i + 1], bp.R_turn)
                for j in range(len(pts) - 1):
                    a = (px + int(pts[j][0]   * scx), py + int(pts[j][1]   * scy))
                    b = (px + int(pts[j+1][0] * scx), py + int(pts[j+1][1] * scy))
                    pygame.draw.line(screen, (255, 150, 50), a, b, 1)
            for obs in lawn.obstacles:
                pygame.draw.circle(screen, (200, 80, 80),
                                   (px + int(obs.x * scx), py + int(obs.y * scy)),
                                   max(2, int(obs.radius * scx)), 1)
            screen.blit(_f("FS").render("Coverage plan preview", True, T_DIM),
                        (px, py + preview_h + 4))

        for i, line in enumerate(revealed):
            col = (100, 255, 80) if "✅" in line else (
                  (100, 200, 62) if i == len(revealed) - 1 else T_MID)
            screen.blit(_f("FC").render(f"  {line}", True, col), (40, 90 + i * 26))

        if done_anim:
            bhov = start_btn.collidepoint(mx2, my2)
            pygame.draw.rect(screen, BTN_H if bhov else BTN_A, start_btn, border_radius=10)
            bt = _f("FM").render("Start Autonomous Mow  →", True, BTN_T)
            screen.blit(bt, (start_btn.x + start_btn.w // 2 - bt.get_width() // 2,
                              start_btn.y + start_btn.h // 2 - bt.get_height() // 2))
        pygame.display.flip()


# ── Auto ──────────────────────────────────────────────────────────────────────

def run_auto(
    screen:    pygame.Surface,
    lawn:      LawnWorld,
    bp:        BehaviourParams,
    lanes:     List[Lane],
    waypoints: list,
) -> pygame.Surface:
    """
    Autonomous mowing screen. The mower follows the learned plan.
    Press R or ESC to return to the chooser.
    """
    clock     = pygame.time.Clock()
    mower     = AutoMower(waypoints, bp, len(lanes))
    lawn_surf = lawn.surface

    while True:
        dt     = min(clock.tick(60) / 1000.0, 0.05)
        sw, sh = screen.get_size()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE | pygame.DOUBLEBUF)
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_r, pygame.K_ESCAPE):
                return screen

        if not mower.done:
            mower.update(dt, lawn.obstacles, lawn)

        cam_x = max(0, min(lawn.W - sw, int(mower.x - sw // 2)))
        cam_y = max(0, min(lawn.H - sh, int(mower.y - sh // 2)))

        screen.blit(lawn_surf,      (0, 0), pygame.Rect(cam_x, cam_y, min(sw, lawn.W), min(sh, lawn.H)))
        screen.blit(lawn.cut_surface, (0, 0), pygame.Rect(cam_x, cam_y, min(sw, lawn.W), min(sh, lawn.H)))

        lane_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for lane in lanes:
            col = (60, 240, 100, 35) if lane.completed else (60, 180, 240, 45)
            p1  = (int(lane.p_start[0] - cam_x), int(lane.p_start[1] - cam_y))
            p2  = (int(lane.p_end[0]   - cam_x), int(lane.p_end[1]   - cam_y))
            pygame.draw.line(lane_surf, col, p1, p2, 2)
        for i in range(len(lanes) - 1):
            pts = bezier_turn(lanes[i], lanes[i + 1], bp.R_turn)
            for j in range(len(pts) - 1):
                a = (int(pts[j][0]   - cam_x), int(pts[j][1]   - cam_y))
                b = (int(pts[j+1][0] - cam_x), int(pts[j+1][1] - cam_y))
                pygame.draw.line(lane_surf, (255, 150, 50, 60), a, b, 2)
        screen.blit(lane_surf, (0, 0))

        path_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for i in range(mower.idx, min(mower.idx + 120, len(waypoints)), 3):
            wx, wy, _, _ = waypoints[i]
            sx2, sy2 = int(wx - cam_x), int(wy - cam_y)
            if 0 < sx2 < sw and 0 < sy2 < sh:
                pygame.draw.circle(path_surf, (255, 220, 60, 120), (sx2, sy2), 2)
        screen.blit(path_surf, (0, 0))

        for si, off in enumerate([-math.pi / 6, 0, math.pi / 6]):
            r = int(min(mower.sensor_ranges[si], 160))
            draw_sensor_cone(screen, mower.x - cam_x, mower.y - cam_y, mower.theta, off, r)
        draw_mower(screen, int(mower.x - cam_x), int(mower.y - cam_y), mower.theta)

        # HUD
        prog = mower.progress()
        hud  = pygame.Surface((400, 130), pygame.SRCALPHA)
        hud.fill((8, 16, 8, 185))
        pygame.draw.rect(hud, (55, 105, 45), (0, 0, 400, 130), 1, border_radius=8)
        hud.blit(_f("FM").render(f"AUTO  –  {lawn.name}", True, (110, 215, 75)), (10, 8))
        hud.blit(_f("FS").render(
            f"θ_pref={math.degrees(bp.theta_pref):.1f}°  "
            f"d_pass={bp.d_pass:.0f}  R_turn={bp.R_turn:.0f}  M_safe={bp.M_safe:.0f}",
            True, T_MID), (10, 34))
        hud.blit(_f("FS").render(
            f"V_pref={bp.V_pref:.0f} px/s   wp {mower.idx}/{len(waypoints)}",
            True, T_DIM), (10, 52))
        hud.blit(_f("FS").render(
            f"Sensor L:{mower.sensor_ranges[0]:.0f}  C:{mower.sensor_ranges[1]:.0f}  R:{mower.sensor_ranges[2]:.0f}",
            True, (80, 200, 220)), (10, 70))
        pygame.draw.rect(hud, (30, 60, 25),      (10, 90, 380, 14), border_radius=6)
        pygame.draw.rect(hud, (100, 210, 65),    (10, 90, int(380 * prog), 14), border_radius=6)
        pct = _f("FS").render(
            f"{prog * 100:.0f}%  {'DONE – R to restart' if mower.done else 'mowing...'}", True, T_HI)
        hud.blit(pct, (10, 108))
        screen.blit(hud, (12, 12))

        # Minimap
        mmw = max(90, int(sw * 0.09))
        mmh = int(mmw * lawn.H / lawn.W)
        mms = pygame.Surface((mmw, mmh), pygame.SRCALPHA)
        mms.fill((35, 70, 35, 180))
        for i in range(0, mower.idx, 8):
            wx, wy, _, _ = waypoints[i]
            pygame.draw.circle(mms, (145, 200, 110, 160),
                               (int(wx / lawn.W * mmw), int(wy / lawn.H * mmh)), 1)
        pygame.draw.circle(mms, (255, 220, 40),
                           (int(mower.x / lawn.W * mmw), int(mower.y / lawn.H * mmh)), 4)
        vw = int(sw / lawn.W * mmw)
        vh = int(sh / lawn.H * mmh)
        pygame.draw.rect(mms, (200, 240, 160, 140),
                         (int(cam_x / lawn.W * mmw), int(cam_y / lawn.H * mmh), vw, vh), 1)
        pygame.draw.rect(mms, (80, 140, 60), (0, 0, mmw, mmh), 1)
        screen.blit(mms, (sw - mmw - 12, 12))

        pygame.display.flip()

    return screen
