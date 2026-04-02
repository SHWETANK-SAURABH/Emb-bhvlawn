"""
constants.py – Colour palettes, font helpers, and shared type aliases.
"""

import pygame
from typing import Tuple

# ── Colours ──────────────────────────────────────────────────────────────────
BG_DARK   = (12, 20, 12)
CARD_IDLE = (26, 42, 26)
CARD_HOV  = (34, 56, 34)
CARD_SEL  = (38, 66, 30)
B_IDLE    = (48, 82, 42)
B_HOV     = (78, 150, 60)
B_SEL     = (112, 218, 72)
T_HI      = (212, 244, 182)
T_MID     = (138, 192, 108)
T_DIM     = (78,  118,  62)
BTN_A     = (52,  132,  38)
BTN_H     = (72,  168,  52)
BTN_D     = (32,   62,  26)
BTN_T     = (228, 252, 208)

GRASS_PAL = [
    [(34,90,34),(45,112,40),(55,132,48),(38,100,35),(62,142,52),(30,80,30)],
    [(82,112,50),(96,127,60),(72,102,45),(92,122,56),(62,92,40),(78,108,48)],
    [(18,68,28),(28,82,36),(22,72,31),(34,88,40),(14,62,26),(24,76,34)],
    [(102,134,62),(118,148,72),(92,122,56),(112,140,66),(88,118,52),(106,136,64)],
]
CUT_PAL = [
    (145,190,110),(152,198,118),(140,185,106),(148,193,114),
]

MOWER_COL   = (210, 170,  40)
MOWER_DARK  = (160, 120,  28)
SENSOR_COL  = (80, 220, 255, 55)
TRAIL_COL   = (255, 220,  80, 100)
PATH_COL    = (255, 220,  60)
LANE_COL    = (80, 200, 255, 70)
BEZIER_COL  = (255, 160,  60)
BYPASS_COL  = (255, 100, 100)
DEMO_TRAIL  = (255, 255, 100, 80)

# ── Type alias ────────────────────────────────────────────────────────────────
Vec2 = Tuple[float, float]

# ── Fonts ─────────────────────────────────────────────────────────────────────
def _fnt(name: str, sz: int, bold: bool = False) -> pygame.font.Font:
    """Load a named system font, falling back to Arial on failure."""
    try:
        return pygame.font.SysFont(name, sz, bold=bold)
    except Exception:
        return pygame.font.SysFont("Arial", sz, bold=bold)


def load_fonts():
    """Return the five application fonts as a dict (call after pygame.init)."""
    return {
        "FT":  _fnt("Georgia",  32, True),
        "FM":  _fnt("Georgia",  18),
        "FC":  _fnt("Consolas", 14),
        "FS":  _fnt("Consolas", 12),
        "FXS": _fnt("Consolas", 11),
    }
