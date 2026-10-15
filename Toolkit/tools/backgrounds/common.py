"""
Shared vocabulary for the DM Toolkit screen backgrounds — "Tango Aurora".

Palette from tavant.com: Tango #F36F26 with black and white, extended with amber
and coral for colour. Every plate is rendered twice: on warm light paper and on
Tavant black (dark theme). See ../../assets/backgrounds/DESIGN_PHILOSOPHY.md.

A plate module in plates/ exposes:

    SLUG = 'source_target'      # image file name
    NUMBER = 3                  # order in the contact sheet
    WORD = 'SOURCE / TARGET'    # name shown in the contact sheet
    SEED = 11
    def draw(p: Plate) -> None  # paints the scene; call p.col('ink') etc. for colours

Composition contract (the app lays a translucent content panel over the plate,
scaled to cover the window and anchored right; the left ~300 px sit under the
sidebar): the hero scene lives in the right ~50 % and the top band; the lower
left carries only a soft colour wash so text on top stays readable.
"""

import math
import os
import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

W, H = 1920, 1080
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')

# Brand palette
TANGO = "#F36F26"
TANGO_DEEP = "#D9571A"
TANGO_SOFT = "#FF8A3D"
AMBER = "#FFB547"
CORAL = "#FF5E6C"
PEACH = "#FFD3B5"
INK_BLACK = "#15151C"
CREAM = "#FFF8F3"

# --- legacy names (plates drawn in the earlier line-art style still import these) ---
PAPER = CREAM
PAPER_DEEP = "#FCE9DC"
INK = INK_BLACK
EMBER = TANGO
TEAL = "#0F8C7C"
GRID, MIST, QUIET, MID, LINE, STRONG = 0.055, 0.10, 0.14, 0.28, 0.50, 0.62

_MODE_COLOURS = {
    'light': {
        'paper': CREAM, 'ink': INK_BLACK, 'soft': '#6B6470', 'line': '#2A2230',
        'glass_fill': '#FFFFFF', 'glass_fill_opacity': 0.62, 'glass_stroke': '#FFFFFF',
        'glass_stroke_opacity': 0.95, 'shadow': '#7A3A14', 'shadow_opacity': 0.16,
        'grid': INK_BLACK, 'grid_opacity': 0.07, 'glow_boost': 1.0, 'aurora_boost': 1.0,
    },
    'dark': {
        'paper': '#101016', 'ink': '#FFFFFF', 'soft': '#B9B1AB', 'line': '#FFE9DC',
        'glass_fill': '#FFFFFF', 'glass_fill_opacity': 0.07, 'glass_stroke': '#FFFFFF',
        'glass_stroke_opacity': 0.22, 'shadow': '#000000', 'shadow_opacity': 0.45,
        'grid': '#FFFFFF', 'grid_opacity': 0.06, 'glow_boost': 1.35, 'aurora_boost': 0.85,
    },
}
BRAND = {'tango': TANGO, 'tango_deep': TANGO_DEEP, 'tango_soft': TANGO_SOFT, 'amber': AMBER,
         'coral': CORAL, 'peach': PEACH}

Point = Tuple[float, float]


def fmt(value: float) -> str:
    text = f"{value:.2f}".rstrip('0').rstrip('.')
    return text if text not in ('', '-0') else '0'


def path_d(points: Sequence[Point], closed: bool = False) -> str:
    if not points:
        return ''
    d = f"M{fmt(points[0][0])},{fmt(points[0][1])}" + ''.join(f"L{fmt(x)},{fmt(y)}" for x, y in points[1:])
    return d + ('Z' if closed else '')


def smooth_d(points: Sequence[Point], closed: bool = False, tension: float = 0.5) -> str:
    """Catmull-Rom spline through points, as cubic Bezier path data."""
    pts = list(points)
    if len(pts) < 3:
        return path_d(pts, closed)
    pts = ([pts[-1]] + pts + [pts[0], pts[1]]) if closed else ([pts[0]] + pts + [pts[-1]])
    d = f"M{fmt(pts[1][0])},{fmt(pts[1][1])}"
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        d += f"C{fmt(c1[0])},{fmt(c1[1])} {fmt(c2[0])},{fmt(c2[1])} {fmt(p2[0])},{fmt(p2[1])}"
    return d + ('Z' if closed else '')


def cubic(p0: Point, p1: Point, p2: Point, p3: Point, t: float) -> Point:
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


def cubic_d(p0: Point, p1: Point, p2: Point, p3: Point) -> str:
    return (f"M{fmt(p0[0])},{fmt(p0[1])}C{fmt(p1[0])},{fmt(p1[1])} {fmt(p2[0])},{fmt(p2[1])} "
            f"{fmt(p3[0])},{fmt(p3[1])}")


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def polar(cx: float, cy: float, r: float, angle_deg: float) -> Point:
    a = math.radians(angle_deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def arc_d(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    x0, y0 = polar(cx, cy, r, a0)
    x1, y1 = polar(cx, cy, r, a1)
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{fmt(x0)},{fmt(y0)}A{fmt(r)},{fmt(r)} 0 {large} 1 {fmt(x1)},{fmt(y1)}"


def quiet_factor(x: float, y: float) -> float:
    """1.0 in the scene zone (right half / top band), fading to 0.25 in the lower left."""
    fx = ease(min(1.0, max(0.0, (x - 760) / 520)))
    fy = ease(min(1.0, max(0.0, (320 - y) / 260)))
    return 0.25 + 0.75 * max(fx, fy)


class Noise:
    """Deterministic smooth 2-D value noise."""

    def __init__(self, seed: int, cell: float = 220.0):
        self.seed, self.cell = seed, cell

    def _hash(self, ix: int, iy: int) -> float:
        n = (ix * 374761393 + iy * 668265263 + self.seed * 2147483647) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 0xFFFF

    def __call__(self, x: float, y: float) -> float:
        gx, gy = x / self.cell, y / self.cell
        ix, iy = math.floor(gx), math.floor(gy)
        fx, fy = gx - ix, gy - iy
        sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a, b = self._hash(ix, iy), self._hash(ix + 1, iy)
        c, d = self._hash(ix, iy + 1), self._hash(ix + 1, iy + 1)
        return (a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sy

    def fbm(self, x: float, y: float, octaves: int = 3) -> float:
        total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
        for _ in range(octaves):
            total += amp * self(x * freq, y * freq)
            norm, amp, freq = norm + amp, amp * 0.5, freq * 2.0
        return total / norm


# Default aurora: warm light pooled on the right and along the top.
DEFAULT_AURORA = [
    # (cx, cy, rx, ry, colour, opacity)
    (1620, 180, 760, 520, 'tango', 0.55),
    (1880, 760, 620, 520, 'coral', 0.34),
    (1180, -60, 720, 360, 'amber', 0.42),
    (1400, 1080, 700, 360, 'peach', 0.40),
    (420, 1180, 900, 420, 'peach', 0.22),
]


class Plate:
    """An SVG plate: ground (paper + aurora + dot grid) and a toolbox of glowing primitives."""

    def __init__(self, number: int, word: str, seed: int = 7, mode: str = 'light'):
        self.number, self.word, self.mode = number, word, mode
        self.dark = mode == 'dark'
        self.rng = random.Random(seed * 1000 + number)
        self.noise = Noise(seed * 31 + number)
        self._defs: List[str] = []
        self._def_ids = set()
        self._body: List[str] = []
        self._aurora = list(DEFAULT_AURORA)
        self._uid = 0
        self._legacy = False

    # --- colours ------------------------------------------------------------
    def col(self, name: str) -> str:
        """Colour by role: 'ink' 'soft' 'line' 'paper' or brand: 'tango' 'amber' 'coral' 'peach'..."""
        if name in BRAND:
            return BRAND[name]
        return _MODE_COLOURS[self.mode][name]

    def val(self, name: str) -> float:
        return _MODE_COLOURS[self.mode][name]

    def _id(self, prefix: str) -> str:
        self._uid += 1
        return f"{prefix}{self._uid}"

    # --- composition ------------------------------------------------------------
    def set_aurora(self, blobs: Iterable[Tuple[float, float, float, float, str, float]]) -> None:
        """Replace the default glow pools: (cx, cy, rx, ry, colour-role, opacity)."""
        self._aurora = list(blobs)

    def add(self, element: str) -> None:
        self._body.append(element)

    def define(self, element: str, def_id: Optional[str] = None) -> None:
        if def_id and def_id in self._def_ids:
            return
        if def_id:
            self._def_ids.add(def_id)
        self._defs.append(element)

    def group(self, elements: Iterable[str], **attrs) -> None:
        self.add(f"<g{self._attrs(attrs)}>" + ''.join(elements) + "</g>")

    @staticmethod
    def _attrs(attrs) -> str:
        return ''.join(f' {k.rstrip("_").replace("_", "-")}="{v}"' for k, v in attrs.items() if v is not None)

    # --- filters & gradients ------------------------------------------------------
    def glow_filter(self, blur: float) -> str:
        fid = f"glow{int(blur)}"
        self.define(f'<filter id="{fid}" filterUnits="userSpaceOnUse" x="-200" y="-200" '
                    f'width="{W + 400}" height="{H + 400}">'
                    f'<feGaussianBlur stdDeviation="{fmt(blur)}"/></filter>', fid)
        return f"url(#{fid})"

    def shadow_filter(self) -> str:
        fid = f"shadow_{self.mode}"
        self.define(f'<filter id="{fid}" filterUnits="userSpaceOnUse" x="-200" y="-200" '
                    f'width="{W + 400}" height="{H + 400}">'
                    f'<feDropShadow dx="0" dy="18" stdDeviation="22" flood-color="{self.col("shadow")}" '
                    f'flood-opacity="{fmt(self.val("shadow_opacity"))}"/></filter>', fid)
        return f"url(#{fid})"

    def linear_gradient(self, stops: Sequence[Tuple[float, str, float]], x1, y1, x2, y2) -> str:
        """Gradient in user space from (x1,y1) to (x2,y2); stops = (offset, colour-role/hex, opacity)."""
        gid = self._id('lg')
        stop_xml = ''.join(f'<stop offset="{fmt(o)}" stop-color="{self._c(c)}" stop-opacity="{fmt(a)}"/>'
                           for o, c, a in stops)
        self.define(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{fmt(x1)}" y1="{fmt(y1)}" '
                    f'x2="{fmt(x2)}" y2="{fmt(y2)}">{stop_xml}</linearGradient>')
        return f"url(#{gid})"

    def radial_gradient(self, stops: Sequence[Tuple[float, str, float]], cx=0.5, cy=0.5, r=0.5,
                        fx=None, fy=None) -> str:
        gid = self._id('rg')
        stop_xml = ''.join(f'<stop offset="{fmt(o)}" stop-color="{self._c(c)}" stop-opacity="{fmt(a)}"/>'
                           for o, c, a in stops)
        focus = f' fx="{fmt(fx)}" fy="{fmt(fy)}"' if fx is not None else ''
        self.define(f'<radialGradient id="{gid}" cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}"{focus}>'
                    f'{stop_xml}</radialGradient>')
        return f"url(#{gid})"

    def _c(self, colour: str) -> str:
        if colour.startswith('#'):
            return colour
        return self.col(colour)

    # --- primitives -----------------------------------------------------------------
    def glow_path(self, d: str, colour='tango', width=2.4, opacity=0.95, glow=10.0, glow_opacity=0.55,
                  dash: Optional[str] = None) -> str:
        """A stroke with a soft halo of the same colour underneath."""
        c = self._c(colour)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ''
        boost = self.val('glow_boost')
        halo = (f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{fmt(width * 3.2)}" '
                f'stroke-opacity="{fmt(min(1, glow_opacity * boost))}" stroke-linecap="round" '
                f'filter="{self.glow_filter(glow)}"{dash_attr}/>')
        core = (f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{fmt(width)}" stroke-opacity="{fmt(opacity)}" '
                f'stroke-linecap="round" stroke-linejoin="round"{dash_attr}/>')
        return halo + core

    def ribbon(self, p0: Point, p1: Point, p2: Point, p3: Point, width=16.0,
               colours=('tango', 'amber'), opacity=0.55, core=True) -> str:
        """A luminous band along a cubic curve, gradient from start to end, with a bright core line."""
        d = cubic_d(p0, p1, p2, p3)
        grad = self.linear_gradient([(0, colours[0], 1), (1, colours[-1], 1)], p0[0], p0[1], p3[0], p3[1])
        out = (f'<path d="{d}" fill="none" stroke="{grad}" stroke-width="{fmt(width * 2.4)}" '
               f'stroke-opacity="{fmt(opacity * 0.45 * self.val("glow_boost"))}" stroke-linecap="round" '
               f'filter="{self.glow_filter(18)}"/>'
               f'<path d="{d}" fill="none" stroke="{grad}" stroke-width="{fmt(width)}" '
               f'stroke-opacity="{fmt(opacity)}" stroke-linecap="round"/>')
        if core:
            out += (f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-width="1.6" '
                    f'stroke-opacity="{fmt(0.85 if self.dark else 0.9)}" stroke-linecap="round"/>')
        return out

    def particles_along(self, p0: Point, p1: Point, p2: Point, p3: Point, count=12, colour='tango',
                        r=(1.6, 3.4), opacity=(0.5, 0.95), start=0.05, end=0.95) -> str:
        dots = []
        for i in range(count):
            t = lerp(start, end, (i + self.rng.uniform(-0.3, 0.3)) / max(1, count - 1))
            x, y = cubic(p0, p1, p2, p3, min(1, max(0, t)))
            dots.append(self.dot(x, y, self.rng.uniform(*r), self.rng.uniform(*opacity), colour))
        return ''.join(dots)

    def orb(self, cx, cy, r, colour='tango', highlight=True, halo=True) -> str:
        """A glowing sphere: halo, radial body, specular highlight."""
        c = self._c(colour)
        body = self.radial_gradient([(0, '#FFFFFF', 0.95), (0.35, c, 1), (1, TANGO_DEEP if colour != 'amber' else c, 1)],
                                    cx=0.38, cy=0.34, r=0.72)
        out = ''
        if halo:
            glow = self.radial_gradient([(0, c, 0.55 * self.val('glow_boost')), (1, c, 0)])
            out += f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r * 3.0)}" fill="{glow}"/>'
        out += f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="{body}"/>'
        if highlight:
            hx, hy = cx - r * 0.52, cy - r * 0.55
            out += (f'<ellipse cx="{fmt(hx)}" cy="{fmt(hy)}" rx="{fmt(r * 0.25)}" '
                    f'ry="{fmt(r * 0.13)}" fill="#FFFFFF" fill-opacity="0.55" '
                    f'transform="rotate(-40 {fmt(hx)} {fmt(hy)})"/>')
        return out

    def ring(self, cx, cy, r, colour='tango', width=1.6, opacity=0.8, dash: Optional[str] = None) -> str:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ''
        return (f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="none" stroke="{self._c(colour)}" '
                f'stroke-width="{fmt(width)}" stroke-opacity="{fmt(opacity)}"{dash_attr}/>')

    def node(self, cx, cy, r=7, colour='tango') -> str:
        """Small ringed data point."""
        return (self.circle(cx, cy, r * 2.2, fill=self._c(colour), opacity=0.16) +
                self.ring(cx, cy, r * 1.35, colour, width=1.4, opacity=0.9) +
                self.dot(cx, cy, r * 0.7, 1.0, colour))

    def glass(self, x, y, w, h, r=22, tint: Optional[str] = None) -> str:
        """A frosted glass card with a soft shadow and a bright rim."""
        fill_opacity = self.val('glass_fill_opacity')
        fill = self.col('glass_fill')
        if tint:
            fill = self.linear_gradient([(0, '#FFFFFF', fill_opacity + 0.1), (1, tint, fill_opacity * 0.85)],
                                        x, y, x + w, y + h)
            fill_opacity = 1
        rim = self.linear_gradient([(0, self.col('glass_stroke'), self.val('glass_stroke_opacity')),
                                    (1, self.col('glass_stroke'), self.val('glass_stroke_opacity') * 0.35)],
                                   x, y, x + w, y + h)
        return (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(r)}" '
                f'fill="{fill}" fill-opacity="{fmt(fill_opacity)}" stroke="{rim}" stroke-width="1.4" '
                f'filter="{self.shadow_filter()}"/>')

    # --- basic shapes (colour may be a role or a hex) ----------------------------------
    def line(self, x1, y1, x2, y2, opacity=MID, width=1.0, color=None, **extra) -> str:
        c = self._c(color) if color else self.col('line')
        return (f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}" stroke="{c}" '
                f'stroke-opacity="{fmt(opacity)}" stroke-width="{fmt(width)}" stroke-linecap="round"{self._attrs(extra)}/>')

    def circle(self, cx, cy, r, opacity=MID, fill=None, stroke=None, width=1.0, **extra) -> str:
        if fill:
            return (f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="{self._c(fill)}" '
                    f'fill-opacity="{fmt(opacity)}"{self._attrs(extra)}/>')
        s = self._c(stroke) if stroke else self.col('line')
        return (f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="none" stroke="{s}" '
                f'stroke-opacity="{fmt(opacity)}" stroke-width="{fmt(width)}"{self._attrs(extra)}/>')

    def dot(self, cx, cy, r=1.4, opacity=MID, color=None) -> str:
        c = self._c(color) if color else self.col('line')
        return f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="{c}" fill-opacity="{fmt(opacity)}"/>'

    def path(self, d: str, opacity=MID, width=1.0, color=None, fill=None, **extra) -> str:
        c = self._c(color) if color else self.col('line')
        fill_attr = f'fill="{self._c(fill)}"' if fill else 'fill="none"'
        return (f'<path d="{d}" {fill_attr} stroke="{c}" stroke-opacity="{fmt(opacity)}" '
                f'stroke-width="{fmt(width)}" stroke-linecap="round" stroke-linejoin="round"{self._attrs(extra)}/>')

    def text(self, x, y, content, size=13, opacity=0.45, family='Segoe UI', anchor='start',
             spacing=1.5, color=None, weight=600) -> str:
        c = self._c(color) if color else self.col('soft')
        return (f'<text x="{fmt(x)}" y="{fmt(y)}" font-family="\'{family}\', sans-serif" font-size="{fmt(size)}" '
                f'font-weight="{weight}" letter-spacing="{fmt(spacing)}" fill="{c}" fill-opacity="{fmt(opacity)}" '
                f'text-anchor="{anchor}">{content}</text>')

    # --- small glyphs for glass cards (drawn geometrically, not clip-art) --------------------
    def glyph(self, kind: str, cx: float, cy: float, s: float = 34, colour='tango') -> str:
        c = self._c(colour)
        k = s / 34.0
        if kind == 'database':
            rx, ry, h = 15 * k, 5.2 * k, 22 * k
            top = cy - h / 2
            return (f'<ellipse cx="{fmt(cx)}" cy="{fmt(top)}" rx="{fmt(rx)}" ry="{fmt(ry)}" fill="{c}" fill-opacity="0.9"/>'
                    + ''.join(f'<path d="M{fmt(cx - rx)},{fmt(top + i * h / 2)}a{fmt(rx)},{fmt(ry)} 0 0 0 {fmt(2 * rx)},0" '
                              f'fill="none" stroke="{c}" stroke-width="{fmt(2.4 * k)}"/>' for i in (1, 2))
                    + f'<path d="M{fmt(cx - rx)},{fmt(top)}v{fmt(h)}M{fmt(cx + rx)},{fmt(top)}v{fmt(h)}" '
                      f'stroke="{c}" stroke-width="{fmt(2.4 * k)}"/>')
        if kind == 'file':
            w, h, f = 22 * k, 28 * k, 7 * k
            x0, y0 = cx - w / 2, cy - h / 2
            lines = ''.join(f'<path d="M{fmt(x0 + 5 * k)},{fmt(y0 + (12 + i * 5) * k)}h{fmt((12 - (i % 2) * 4) * k)}" '
                            f'stroke="{c}" stroke-width="{fmt(2 * k)}" stroke-linecap="round"/>' for i in range(3))
            return (f'<path d="M{fmt(x0)},{fmt(y0)}h{fmt(w - f)}l{fmt(f)},{fmt(f)}v{fmt(h - f)}h{fmt(-w)}Z" '
                    f'fill="none" stroke="{c}" stroke-width="{fmt(2.4 * k)}" stroke-linejoin="round"/>'
                    f'<path d="M{fmt(x0 + w - f)},{fmt(y0)}v{fmt(f)}h{fmt(f)}" fill="none" stroke="{c}" '
                    f'stroke-width="{fmt(2 * k)}" stroke-linejoin="round"/>' + lines)
        if kind == 'cloud':
            return (f'<path d="M{fmt(cx - 15 * k)},{fmt(cy + 8 * k)}a{fmt(7 * k)},{fmt(7 * k)} 0 0 1 {fmt(1 * k)},{fmt(-13.5 * k)}'
                    f'a{fmt(9 * k)},{fmt(9 * k)} 0 0 1 {fmt(16 * k)},{fmt(-3 * k)}a{fmt(7 * k)},{fmt(7 * k)} 0 0 1 '
                    f'{fmt(11 * k)},{fmt(9 * k)}a{fmt(6 * k)},{fmt(6 * k)} 0 0 1 {fmt(-1 * k)},{fmt(7.5 * k)}Z" '
                    f'fill="{c}" fill-opacity="0.9"/>')
        if kind == 'table':
            w, h = 28 * k, 22 * k
            x0, y0 = cx - w / 2, cy - h / 2
            grid = (f'<path d="M{fmt(x0)},{fmt(y0 + h / 3)}h{fmt(w)}M{fmt(x0)},{fmt(y0 + 2 * h / 3)}h{fmt(w)}'
                    f'M{fmt(x0 + w / 3)},{fmt(y0)}v{fmt(h)}M{fmt(x0 + 2 * w / 3)},{fmt(y0)}v{fmt(h)}" '
                    f'stroke="{c}" stroke-width="{fmt(1.6 * k)}" stroke-opacity="0.8"/>')
            return (f'<rect x="{fmt(x0)}" y="{fmt(y0)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(3 * k)}" '
                    f'fill="{c}" fill-opacity="0.14" stroke="{c}" stroke-width="{fmt(2.2 * k)}"/>' + grid)
        if kind == 'check':
            return (f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(14 * k)}" fill="{c}"/>'
                    f'<path d="M{fmt(cx - 6.5 * k)},{fmt(cy + 0.5 * k)}l{fmt(4.5 * k)},{fmt(4.5 * k)}l{fmt(8.5 * k)},{fmt(-9 * k)}" '
                    f'fill="none" stroke="#FFFFFF" stroke-width="{fmt(3 * k)}" stroke-linecap="round" stroke-linejoin="round"/>')
        if kind == 'cross':
            return (f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(14 * k)}" fill="{c}"/>'
                    f'<path d="M{fmt(cx - 5 * k)},{fmt(cy - 5 * k)}l{fmt(10 * k)},{fmt(10 * k)}M{fmt(cx + 5 * k)},{fmt(cy - 5 * k)}'
                    f'l{fmt(-10 * k)},{fmt(10 * k)}" stroke="#FFFFFF" stroke-width="{fmt(3 * k)}" stroke-linecap="round"/>')
        if kind == 'gear':
            teeth = ''.join(
                f'<rect x="{fmt(cx - 3 * k)}" y="{fmt(cy - 16 * k)}" width="{fmt(6 * k)}" height="{fmt(7 * k)}" rx="{fmt(1.5 * k)}" '
                f'fill="{c}" transform="rotate({a} {fmt(cx)} {fmt(cy)})"/>' for a in range(0, 360, 45))
            return (teeth + f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(11 * k)}" fill="{c}"/>'
                    f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(4.5 * k)}" fill="{self.col("paper")}"/>')
        if kind == 'shield':
            return (f'<path d="M{fmt(cx)},{fmt(cy - 16 * k)}l{fmt(13 * k)},{fmt(5 * k)}v{fmt(9 * k)}c0,{fmt(9 * k)} '
                    f'{fmt(-6 * k)},{fmt(15 * k)} {fmt(-13 * k)},{fmt(18 * k)}c{fmt(-7 * k)},{fmt(-3 * k)} {fmt(-13 * k)},{fmt(-9 * k)} '
                    f'{fmt(-13 * k)},{fmt(-18 * k)}v{fmt(-9 * k)}Z" fill="{c}"/>'
                    f'<path d="M{fmt(cx - 5.5 * k)},{fmt(cy + 0.5 * k)}l{fmt(4 * k)},{fmt(4 * k)}l{fmt(7.5 * k)},{fmt(-8 * k)}" '
                    f'fill="none" stroke="#FFFFFF" stroke-width="{fmt(2.6 * k)}" stroke-linecap="round" stroke-linejoin="round"/>')
        if kind == 'chart':
            bars = ''.join(f'<rect x="{fmt(cx - 13 * k + i * 9 * k)}" y="{fmt(cy + 12 * k - hgt * k)}" width="{fmt(6 * k)}" '
                           f'height="{fmt(hgt * k)}" rx="{fmt(1.5 * k)}" fill="{c}" fill-opacity="{fmt(0.55 + i * 0.15)}"/>'
                           for i, hgt in enumerate((10, 17, 24)))
            return bars + (f'<path d="M{fmt(cx - 15 * k)},{fmt(cy + 14 * k)}h{fmt(30 * k)}" stroke="{c}" '
                           f'stroke-width="{fmt(2 * k)}" stroke-linecap="round"/>')
        raise ValueError(f"unknown glyph {kind}")

    # --- ground --------------------------------------------------------------------------
    def _ground(self) -> str:
        parts = [f'<rect width="{W}" height="{H}" fill="{self.col("paper")}"/>']
        boost = self.val('aurora_boost')
        for cx, cy, rx, ry, colour, opacity in self._aurora:
            if self.dark and colour == 'peach':
                colour, opacity = 'tango_deep', opacity * 0.45   # peach turns muddy on black
            grad = self.radial_gradient([(0, colour, min(1, opacity * boost)), (0.55, colour, opacity * boost * 0.45),
                                         (1, colour, 0)])
            parts.append(f'<ellipse cx="{fmt(cx)}" cy="{fmt(cy)}" rx="{fmt(rx)}" ry="{fmt(ry)}" fill="{grad}"/>')
        # a faint dot lattice, stronger toward the scene side
        dots = []
        for gx in range(24, W, 32):
            for gy in range(24, H, 32):
                q = quiet_factor(gx, gy)
                if q > 0.3:
                    dots.append(f'M{gx},{gy}h0.01')
        parts.append(f'<path d="{"".join(dots)}" stroke="{self.col("grid")}" stroke-opacity="{fmt(self.val("grid_opacity") * 1.6)}" '
                     f'stroke-width="2.2" stroke-linecap="round"/>')
        return ''.join(parts)

    def svg(self) -> str:
        ground = self._ground()          # defines the aurora gradients, so build it before <defs>
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
                f'<defs>{"".join(self._defs)}</defs>{ground}{"".join(self._body)}</svg>')
