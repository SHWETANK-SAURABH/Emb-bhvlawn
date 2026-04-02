"""
main.py – Entry point for the Lawn Mower LfD Simulator.

Run with:  python main.py
"""

import random
import sys
import pygame

from src.constants import load_fonts
from src.world     import LawnWorld
from src.screens   import set_fonts, run_chooser, run_demo, run_learning, run_auto


def make_lawns() -> list:
    """Generate four randomly-seeded, named LawnWorld instances for the chooser."""
    names = ["Garden Haven", "Meadow Dream", "Lush Retreat", "Sunlit Yard",
             "Wild Clearing", "Shaded Nook", "Butterfly Glade", "Morning Dew"]
    random.shuffle(names)
    seeds = [random.randint(1, 999_999) for _ in range(4)]
    pals  = list(range(4))
    random.shuffle(pals)
    return [LawnWorld(seeds[i], pals[i], names[i]) for i in range(4)]


def main() -> None:
    """Initialise pygame and run the four-screen application loop."""
    pygame.init()
    screen = pygame.display.set_mode((1280, 800), pygame.RESIZABLE | pygame.DOUBLEBUF)
    pygame.display.set_caption("🌿 Lawn Mower — Learning from Demonstration")

    # Share fonts with the screens module
    set_fonts(load_fonts())

    lawns = make_lawns()

    while True:
        # ── Chooser ──────────────────────────────────────────────────────────
        result, screen = run_chooser(screen, lawns)
        if result == "regen":
            lawns = make_lawns()
            continue
        if not isinstance(result, int):
            continue

        # ── Demo ─────────────────────────────────────────────────────────────
        lawn = lawns[result]
        lawn.build_surface()
        rec, screen = run_demo(screen, lawn)
        if rec is None or len(rec.poses) < 10:
            continue  # too short or cancelled – back to chooser

        # ── Learning ─────────────────────────────────────────────────────────
        bp, lanes, waypoints, screen = run_learning(screen, lawn, rec)

        # ── Auto ─────────────────────────────────────────────────────────────
        screen = run_auto(screen, lawn, bp, lanes, waypoints)


if __name__ == "__main__":
    main()
