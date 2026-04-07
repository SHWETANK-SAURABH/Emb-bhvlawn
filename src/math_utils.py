"""
math_utils.py – Vector math, Bézier curves, and signal-smoothing utilities.
"""

import math
from typing import List, Optional, Tuple
from src.constants import Vec2


# ── Vector helpers ────────────────────────────────────────────────────────────

def v2add(a: Vec2, b: Vec2) -> Vec2:
    """Add two 2-D vectors."""
    return (a[0] + b[0], a[1] + b[1])


def v2sub(a: Vec2, b: Vec2) -> Vec2:
    """Subtract vector b from vector a."""
    return (a[0] - b[0], a[1] - b[1])


def v2scale(a: Vec2, s: float) -> Vec2:
    """Scale a 2-D vector by scalar s."""
    return (a[0] * s, a[1] * s)


def v2len(a: Vec2) -> float:
    """Return the Euclidean length of a vector."""
    return math.hypot(a[0], a[1])


def v2norm(a: Vec2) -> Vec2:
    """Return the unit vector of a; returns (1,0) if length is near-zero."""
    l = v2len(a)
    return (a[0] / l, a[1] / l) if l > 1e-9 else (1.0, 0.0)


def v2dot(a: Vec2, b: Vec2) -> float:
    """Dot product of two 2-D vectors."""
    return a[0] * b[0] + a[1] * b[1]


def v2perp(a: Vec2) -> Vec2:
    """Return the left-perpendicular of a vector (90° CCW rotation)."""
    return (-a[1], a[0])


def angle_diff(a: float, b: float) -> float:
    """Signed angular difference a − b, wrapped to (−π, π]."""
    return (a - b + math.pi) % (2 * math.pi) - math.pi


# ── Bézier curves ─────────────────────────────────────────────────────────────

def bezier4(P0: Vec2, P1: Vec2, P2: Vec2, P3: Vec2, u: float) -> Vec2:
    """Evaluate a cubic Bézier at parameter u ∈ [0, 1]."""
    t = 1 - u
    return (
        t**3 * P0[0] + 3 * t**2 * u * P1[0] + 3 * t * u**2 * P2[0] + u**3 * P3[0],
        t**3 * P0[1] + 3 * t**2 * u * P1[1] + 3 * t * u**2 * P2[1] + u**3 * P3[1],
    )


def sample_bezier(P0: Vec2, P1: Vec2, P2: Vec2, P3: Vec2, n: int = 24) -> List[Vec2]:
    """Sample n evenly-spaced points along a cubic Bézier curve."""
    return [bezier4(P0, P1, P2, P3, i / (n - 1)) for i in range(n)]


# ── Signal smoothing ──────────────────────────────────────────────────────────

def savgol_smooth(vals: List[float], window: int = 7, poly: int = 2) -> List[float]:
    """Apply a Savitzky-Golay smooth via least-squares polynomial fitting."""
    if len(vals) < window:
        return list(vals)
    half = window // 2
    out = list(vals)
    for i in range(half, len(vals) - half):
        seg = vals[i - half: i + half + 1]
        xs  = list(range(-half, half + 1))
        try:
            coeffs = _poly_fit(xs, seg, poly)
            out[i] = coeffs[0]
        except Exception:
            out[i] = sum(seg) / len(seg)
    return out


def _poly_fit(xs: List[float], ys: List[float], deg: int) -> List[float]:
    """
    Fit a polynomial of degree deg and return its coefficients.
    Index 0 is the constant term (value at x=0), solved via Gaussian elimination.
    """
    n = len(xs)
    A = [[x ** p for p in range(deg + 1)] for x in xs]
    AtA = [
        [sum(A[r][i] * A[r][j] for r in range(n)) for j in range(deg + 1)]
        for i in range(deg + 1)
    ]
    Aty = [sum(A[r][i] * ys[r] for r in range(n)) for i in range(deg + 1)]
    m = deg + 1
    M = [AtA[i] + [Aty[i]] for i in range(m)]
    for col in range(m):
        pivot = max(range(col, m), key=lambda r: abs(M[r][col]))
        M[col], M[pivot] = M[pivot], M[col]
        if abs(M[col][col]) < 1e-12:
            continue
        for row in range(m):
            if row == col:
                continue
            f = M[row][col] / M[col][col]
            M[row] = [M[row][k] - f * M[col][k] for k in range(m + 1)]
    return [M[i][m] / M[i][i] if abs(M[i][i]) > 1e-12 else 0 for i in range(m)]


def smooth_angle_list(thetas: List[float]) -> List[float]:
    """Unwrap a list of angles, smooth with Savitzky-Golay, then re-wrap."""
    unwrapped = [thetas[0]]
    for i in range(1, len(thetas)):
        d = angle_diff(thetas[i], thetas[i - 1])
        unwrapped.append(unwrapped[-1] + d)
    s = savgol_smooth(unwrapped)
    return [a % (2 * math.pi) for a in s]


# ── Geometry ──────────────────────────────────────────────────────────────────

def clip_segment_to_rect(
    p1: Vec2, p2: Vec2, rect: Tuple[float, float, float, float]
) -> Optional[Tuple[Vec2, Vec2]]:
    """
    Cohen-Sutherland line clip against axis-aligned rectangle (xmin,ymin,xmax,ymax).
    Returns clipped (p1, p2) or None if entirely outside.
    """
    x1, y1 = p1
    x2, y2 = p2
    xmin, ymin, xmax, ymax = rect

    def out(x, y):
        c = 0
        if x < xmin: c |= 1
        if x > xmax: c |= 2
        if y < ymin: c |= 4
        if y > ymax: c |= 8
        return c

    c1, c2 = out(x1, y1), out(x2, y2)
    for _ in range(10):
        if not (c1 | c2):
            return (x1, y1), (x2, y2)
        if c1 & c2:
            return None
        c = c1 if c1 else c2
        if c & 8:   x = x1 + (x2 - x1) * (ymax - y1) / (y2 - y1 + 1e-12); y = ymax
        elif c & 4: x = x1 + (x2 - x1) * (ymin - y1) / (y2 - y1 + 1e-12); y = ymin
        elif c & 2: y = y1 + (y2 - y1) * (xmax - x1) / (x2 - x1 + 1e-12); x = xmax
        else:       y = y1 + (y2 - y1) * (xmin - x1) / (x2 - x1 + 1e-12); x = xmin
        if c == c1: x1, y1, c1 = x, y, out(x, y)
        else:       x2, y2, c2 = x, y, out(x, y)
    return None
