"""Data Hub — the store of loaded datasets.

A glossy hub orb rests on a stacked glass platform (the store). Ribbons of light
rise from it like a fountain and fan out to six glass dataset tiles set on an
arc above; the dataset in use is tinted and ringed with light.
"""
import math

from common import W, H, cubic, fmt, lerp, smooth_d

SLUG = 'data_hub'
NUMBER = 7
WORD = 'DATA HUB'
SEED = 37

HUB = (1480.0, 720.0)
HR = 58
ARC_R = 410
TILE_W, TILE_H = 136, 92
ANGLES = (200, 225, 250, 275, 300, 325)
COLOURS = ('amber', 'coral', 'tango', 'tango', 'amber', 'coral')
ACTIVE = 3


def _wide_glow(p, blur):
    """Blur filter over the whole canvas, so glows of straight (zero-height) strokes are never clipped."""
    fid = f"wglow{int(blur)}"
    p.define(f'<filter id="{fid}" filterUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
             f'<feGaussianBlur stdDeviation="{fmt(blur)}"/></filter>', fid)
    return f"url(#{fid})"


def _ribbon(p, p0, p1, p2, p3, width=12.0, colours=('tango', 'amber'), opacity=0.6):
    """Like Plate.ribbon, but with an unclipped halo."""
    d = (f"M{fmt(p0[0])},{fmt(p0[1])}C{fmt(p1[0])},{fmt(p1[1])} {fmt(p2[0])},{fmt(p2[1])} "
         f"{fmt(p3[0])},{fmt(p3[1])}")
    grad = p.linear_gradient([(0, colours[0], 1), (1, colours[-1], 1)], p0[0], p0[1],
                             p3[0] + (0.01 if p3[0] == p0[0] else 0), p3[1])
    return (f'<path d="{d}" fill="none" stroke="{grad}" stroke-width="{fmt(width * 2.4)}" '
            f'stroke-opacity="{fmt(opacity * 0.45 * p.val("glow_boost"))}" stroke-linecap="round" '
            f'filter="{_wide_glow(p, 18)}"/>'
            f'<path d="{d}" fill="none" stroke="{grad}" stroke-width="{fmt(width)}" '
            f'stroke-opacity="{fmt(opacity)}" stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-width="1.6" '
            f'stroke-opacity="{fmt(0.85 if p.dark else 0.9)}" stroke-linecap="round"/>')


def _bar(p, x, y, w, h, opacity, colour=None):
    c = p.col(colour) if colour else p.col('ink')
    return (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(h / 2)}" '
            f'fill="{c}" fill-opacity="{fmt(opacity)}"/>')


def _round_rect_d(x, y, w, h, r):
    return (f"M{fmt(x + r)},{fmt(y)}H{fmt(x + w - r)}A{r},{r} 0 0 1 {fmt(x + w)},{fmt(y + r)}"
            f"V{fmt(y + h - r)}A{r},{r} 0 0 1 {fmt(x + w - r)},{fmt(y + h)}H{fmt(x + r)}"
            f"A{r},{r} 0 0 1 {fmt(x)},{fmt(y + h - r)}V{fmt(y + r)}A{r},{r} 0 0 1 {fmt(x + r)},{fmt(y)}Z")


def _arc(cx, cy, r, a0, a1):
    x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{fmt(x0)},{fmt(y0)}A{r},{r} 0 {large} 1 {fmt(x1)},{fmt(y1)}"


def _platform(p, cx, cy):
    """Three stacked glass discs under the hub: the store itself."""
    out = ''
    for i, (rx, ry, dy) in enumerate(((190, 46, 92), (150, 36, 58), (112, 27, 28))):
        y = cy + dy
        rim = p.linear_gradient([(0, '#FFFFFF', 0.95 if not p.dark else 0.4),
                                 (1, '#FFFFFF', 0.3 if not p.dark else 0.1)], cx - rx, y - ry, cx + rx, y + ry)
        body = p.linear_gradient([(0, '#FFFFFF', 0.7 if not p.dark else 0.1),
                                  (1, 'tango' if i == 2 else 'peach', 0.35 if not p.dark else 0.16)],
                                 cx, y - ry, cx, y + ry)
        out += (f'<ellipse cx="{fmt(cx)}" cy="{fmt(y)}" rx="{rx}" ry="{ry}" fill="{body}" stroke="{rim}" '
                f'stroke-width="1.4" filter="{p.shadow_filter()}"/>')
        # a lit front edge on each disc
        out += p.glow_path(f"M{fmt(cx - rx * 0.8)},{fmt(y + ry * 0.6)}A{rx},{ry} 0 0 0 {fmt(cx + rx * 0.8)},{fmt(y + ry * 0.6)}",
                           ('amber', 'coral', 'tango')[i], width=1.6, opacity=0.85, glow=7, glow_opacity=0.45)
    return out


def draw(p):
    rng = p.rng
    hx, hy = HUB

    p.set_aurora([
        (1480, 560, 620, 500, 'tango', 0.54),
        (1880, 160, 520, 380, 'amber' if not p.dark else 'tango_soft', 0.48 if not p.dark else 0.38),
        (1560, 1040, 620, 300, 'coral', 0.36),
        (1120, -40, 620, 300, 'peach', 0.55),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Decorative sweep across the top band.
    sweep = [(880, 118), (1180, 70), (1480, 104), (1760, 52), (1990, 86)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=1.8, opacity=0.65, glow=12, glow_opacity=0.4))
    p.add(p.glow_path(smooth_d([(x, y + 24) for x, y in sweep]), 'tango', width=1.1, opacity=0.45,
                      glow=8, glow_opacity=0.28))

    # Guide arcs echoing the tile arc.
    p.add(p.path(_arc(hx, hy, ARC_R - 120, 190, 350), opacity=0.32, width=1.3, color='tango',
                 stroke_dasharray='2 9'))
    p.add(p.path(_arc(hx, hy, ARC_R + 120, 196, 344), opacity=0.24, width=1.2, color='tango',
                 stroke_dasharray='2 10'))
    p.add(p.glow_path(_arc(hx, hy, ARC_R + 120, 214, 250), 'amber', width=2.0, opacity=0.8, glow=9,
                      glow_opacity=0.45))
    p.add(p.glow_path(_arc(hx, hy, ARC_R + 120, 300, 330), 'coral', width=1.8, opacity=0.75, glow=9,
                      glow_opacity=0.4))

    tiles = []
    for ang in ANGLES:
        tx, ty = hx + ARC_R * math.cos(math.radians(ang)), hy + ARC_R * math.sin(math.radians(ang))
        tiles.append((tx - TILE_W / 2, ty - TILE_H / 2))

    # Fountain ribbons: rise from the hub, fan out, enter each tile on the side facing the hub.
    for i, ((x, y), colour) in enumerate(zip(tiles, COLOURS)):
        active = i == ACTIVE
        cx_, cy_ = x + TILE_W / 2, y + TILE_H / 2
        vx, vy = hx - cx_, hy - cy_
        if abs(vx) > abs(vy) * 1.1:      # mostly sideways: enter through the inner side edge
            side = 1 if vx > 0 else -1
            end = (cx_ + side * TILE_W / 2, cy_ + 8)
            c2 = (end[0] + side * 130, end[1] + 10)
            lift = 90
        else:                            # enter through the bottom edge
            end = (cx_, y + TILE_H)
            c2 = (end[0] + vx * 0.08, end[1] + 120)
            lift = 170
        dx = end[0] - hx
        start = (hx + dx * 0.05, hy - HR + 6)
        c1 = (hx + dx * (0.22 if lift > 100 else 0.3), hy - lift)
        cols = ('tango', colour) if not active else ('amber', 'tango')
        p.add(_ribbon(p, start, c1, c2, end, width=13 if active else 8, colours=cols,
                      opacity=0.74 if active else 0.5))
        p.add(p.particles_along(start, c1, c2, end, count=9 if active else 6, colour=colour, r=(1.5, 3.2),
                                start=0.14, end=0.92))

    # The store platform, then the hub orb resting on it.
    p.add(_platform(p, hx, hy))
    bloom = p.radial_gradient([(0, '#FFFFFF' if not p.dark else 'amber', 0.55 if not p.dark else 0.35),
                               (0.5, 'tango_soft', 0.25), (1, 'tango', 0)])
    p.add(f'<circle cx="{fmt(hx)}" cy="{fmt(hy)}" r="170" fill="{bloom}"/>')
    p.add(p.ring(hx, hy, 92, 'tango', width=1.3, opacity=0.38))
    p.add(p.glow_path(_arc(hx, hy, 92, 196, 300), 'amber', width=2.6, opacity=0.95, glow=8))
    p.add(p.dot(hx + 92 * math.cos(math.radians(300)), hy + 92 * math.sin(math.radians(300)), 4.5, 1.0, 'amber'))
    p.add(p.orb(hx, hy, HR, 'tango'))

    # Dataset tiles.
    for i, ((x, y), colour) in enumerate(zip(tiles, COLOURS)):
        active = i == ACTIVE
        if active:
            p.add(p.glow_path(_round_rect_d(x - 6, y - 6, TILE_W + 12, TILE_H + 12, 26), 'tango',
                              width=1.6, opacity=0.9, glow=10, glow_opacity=0.6))
        tint = ('#FFC9A6' if not p.dark else '#FF8A3D') if active else None
        p.add(p.glass(x, y, TILE_W, TILE_H, r=20, tint=tint))
        p.add(p.glyph('table', x + 38, y + 40, 36, colour))
        p.add(_bar(p, x + 66, y + 30, 50, 7, 0.26))
        p.add(_bar(p, x + 66, y + 45, 34, 7, 0.13))
        # a row-count strip
        for k in range(4):
            p.add(_bar(p, x + 20 + k * 25, y + TILE_H - 20, 19, 5,
                       0.9 if k <= (i % 3) + 1 or active else 0.12, colour if (k <= (i % 3) + 1 or active) else None))
        if active:
            p.add(p.dot(x + TILE_W - 16, y + 16, 4.5, 1.0, 'tango'))
            p.add(p.circle(x + TILE_W - 16, y + 16, 9, 0.25, fill='tango'))

    # Sparkles.
    for _ in range(70):
        x = rng.uniform(980, W - 30)
        y = rng.uniform(40, H - 40)
        p.add(p.dot(x, y, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
