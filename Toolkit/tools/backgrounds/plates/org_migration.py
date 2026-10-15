"""Org Migration.

Two large glass org tiles, each holding a cloud: the source org sits upper-left
of the scene, the target org lower-right. A great arcing ribbon of light carries
small record cards from one to the other; the target glows as it receives.
"""
import math

from common import W, H, cubic, cubic_d, lerp, smooth_d, arc_d, fmt, polar

SLUG = 'org_migration'
NUMBER = 12
WORD = 'ORG MIGRATION'
SEED = 23

SRC = (1060, 150, 290, 200)     # x, y, w, h
TGT = (1500, 600, 330, 240)


def _bar(p, x, y, w, h=8, opacity=0.2, colour=None):
    c = p._c(colour) if colour else p.col('ink')
    return (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(h / 2)}" '
            f'fill="{c}" fill-opacity="{fmt(opacity)}"/>')


def _sparkle(p, cx, cy, s, colour='amber', opacity=0.9):
    """A four-point star with a soft halo."""
    c = p._c(colour)
    k = s * 0.22
    d = (f"M{fmt(cx)},{fmt(cy - s)}Q{fmt(cx + k)},{fmt(cy - k)} {fmt(cx + s)},{fmt(cy)}"
         f"Q{fmt(cx + k)},{fmt(cy + k)} {fmt(cx)},{fmt(cy + s)}Q{fmt(cx - k)},{fmt(cy + k)} {fmt(cx - s)},{fmt(cy)}"
         f"Q{fmt(cx - k)},{fmt(cy - k)} {fmt(cx)},{fmt(cy - s)}Z")
    halo = p.radial_gradient([(0, c, 0.5 * p.val('glow_boost')), (1, c, 0)])
    return (f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(s * 1.6)}" fill="{halo}"/>'
            f'<path d="{d}" fill="{c}" fill-opacity="{fmt(opacity)}"/>'
            f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(s * 0.14)}" fill="#FFFFFF" fill-opacity="0.95"/>')


def _specular(cx, cy, r, angle=-135):
    """A small glint on the upper-left rim of an orb, kept clear of the glyph it carries."""
    sx, sy = polar(cx, cy, r * 0.74, angle)
    return (f'<ellipse cx="{fmt(sx)}" cy="{fmt(sy)}" rx="{fmt(r * 0.25)}" ry="{fmt(r * 0.12)}" fill="#FFFFFF" '
            f'fill-opacity="0.55" transform="rotate({fmt(angle + 90)} {fmt(sx)} {fmt(sy)})"/>')


def _pool(p, cx, cy, rx, ry, colour, opacity):
    """A glow pool with a steep alpha falloff (dark theme: keeps the fringe from going brown)."""
    grad = p.radial_gradient([(0, colour, opacity), (0.3, colour, opacity * 0.55), (0.62, colour, opacity * 0.14),
                              (1, colour, 0)])
    return f'<ellipse cx="{fmt(cx)}" cy="{fmt(cy)}" rx="{fmt(rx)}" ry="{fmt(ry)}" fill="{grad}"/>'


def _cloud_disc(p, cx, cy, r, colour, bright):
    """A luminous disc holding a white cloud glyph — the org's emblem."""
    c = p._c(colour)
    body = p.radial_gradient([(0, '#FFFFFF', 0.55 if bright else 0.35), (0.45, c, 1), (1, 'tango_deep', 1)],
                             cx=0.36, cy=0.3, r=0.8)
    out = ''
    if bright:
        halo = p.radial_gradient([(0, c, 0.6 * p.val('glow_boost')), (1, c, 0)])
        out += f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r * 2.6)}" fill="{halo}"/>'
    out += f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="{body}"/>'
    out += p.glyph('cloud', cx + r * 0.02, cy + r * 0.06, r * 1.05, '#FFFFFF')
    out += _specular(cx, cy, r)
    return out


def _record(p, cx, cy, colour, scale=1.0):
    """A small record card riding the ribbon."""
    w, h = 96 * scale, 56 * scale
    x, y = cx - w / 2, cy - h / 2
    out = ''
    if p.dark:   # a smoked backing so the small card reads over the bright ribbon
        out += (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(14 * scale)}" '
                f'fill="#221A20" fill-opacity="0.74"/>')
    out += p.glass(x, y, w, h, r=14 * scale, tint='#FFE7D6' if not p.dark else None)
    out += p.dot(x + 21 * scale, cy, 8 * scale, 0.95, colour)
    out += _bar(p, x + 37 * scale, cy - 10 * scale, 44 * scale, 8 * scale, 0.42)
    out += _bar(p, x + 37 * scale, cy + 3 * scale, 28 * scale, 7 * scale, 0.2)
    return out


def _t_at(p0, p1, p2, p3, u, n=200):
    """Curve parameter at fraction u of the arc length."""
    pts = [cubic(p0, p1, p2, p3, i / n) for i in range(n + 1)]
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    goal = u * acc[-1]
    for i, d in enumerate(acc):
        if d >= goal:
            return i / n
    return 1.0


def draw(p):
    rng = p.rng
    sx, sy, sw, sh = SRC
    tx, ty, tw, th = TGT

    if not p.dark:
        p.set_aurora([
            (1680, 740, 600, 460, 'tango', 0.62),
            (1240, 200, 520, 340, 'amber', 0.46),
            (1900, 200, 480, 360, 'coral', 0.32),
            (1150, 1020, 620, 340, 'coral', 0.26),
            (1000, -60, 620, 280, 'peach', 0.55),
            (1470, 450, 320, 240, 'amber', 0.26),
            (380, 1150, 900, 420, 'peach', 0.22),
        ])
    else:
        # Night: fewer, tighter pools that stay tango/coral instead of fading to brown.
        p.set_aurora([
            (1680, 740, 560, 430, 'tango', 0.6),
            (1470, 450, 300, 220, 'tango', 0.2),
            (1300, 1040, 520, 280, 'coral', 0.16),
            (380, 1150, 900, 420, 'peach', 0.22),
        ])
        p.add(_pool(p, 1240, 190, 390, 255, 'tango', 0.34))
        p.add(_pool(p, 1900, 190, 360, 270, 'coral', 0.28))

    # Faint star field in the scene zone.
    for _ in range(90):
        x = rng.uniform(1000, W - 24)
        y = rng.uniform(30, H - 30)
        p.add(p.dot(x, y, rng.uniform(0.7, 2.0), rng.uniform(0.15, 0.5), rng.choice(['tango', 'amber', 'coral'])))

    # The standard two-line sweep across the top band, clear of the source tile.
    sweep = [(860, 120), (1180, 60), (1500, 92), (1780, 40), (1990, 70)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=2.0, opacity=0.7, glow=12, glow_opacity=0.45))
    p.add(p.glow_path(smooth_d([(x, y + 26) for x, y in sweep]), 'tango', width=1.2, opacity=0.5, glow=8,
                      glow_opacity=0.3))

    # The landing system: dashed orbits around the target org, with two glowing arcs riding them.
    tcx, tcy = tx + tw / 2, ty + th / 2
    for i, r in enumerate((230, 300, 380)):
        p.add(p.ring(tcx, tcy, r, 'tango', width=1.3, opacity=0.42 - i * 0.1, dash='2 10'))
    p.add(p.glow_path(arc_d(tcx, tcy, 230, 162, 234), 'coral', width=2.0, opacity=0.8, glow=10))
    p.add(p.glow_path(arc_d(tcx, tcy, 300, 56, 104), 'amber', width=2.0, opacity=0.75, glow=10))

    # Faint orbit around the source.
    scx, scy = sx + sw / 2, sy + sh / 2
    p.add(p.ring(scx, scy, 190, 'amber', width=1.1, opacity=0.22, dash='2 9'))

    # The great arc: leaves the source's right rim at a port, bows up and right, lands on the target.
    a0 = (sx + sw, sy + sh * 0.42)
    a1 = (sx + sw + 240, sy - 50)
    a2 = (tx + tw + 50, ty - 300)
    a3 = (tx + tw * 0.62, ty)
    # two fine companion trails inside the arc make it read as a flyway
    for k, (col, op) in enumerate((('amber', 0.55), ('coral', 0.4))):
        o = 34 * (k + 1)
        b1 = (a1[0] - o * 0.6, a1[1] + o)
        b2 = (a2[0] - o, a2[1] + o * 0.6)
        p.add(p.glow_path(cubic_d((a0[0] - 2, a0[1] + 3 + k * 4), b1, b2, (a3[0] - 8 - k * 8, a3[1])), col,
                          width=1.3, opacity=op, glow=8, glow_opacity=0.3))
    p.add(p.ribbon(a0, a1, a2, a3, width=16, colours=('amber', 'tango'), opacity=0.68))
    p.add(p.particles_along(a0, a1, a2, a3, count=18, colour='amber', r=(1.6, 3.4), start=0.08))

    # Record cards riding the great arc, evenly spaced by arc length.
    for u, colour, scale in ((0.2, 'amber', 0.9), (0.44, 'tango', 1.0), (0.68, 'coral', 1.0), (0.88, 'tango', 0.9)):
        x, y = cubic(a0, a1, a2, a3, _t_at(a0, a1, a2, a3, u))
        p.add(_record(p, x, y, colour, scale))

    # Source org tile.
    p.add(p.glass(sx, sy, sw, sh, r=28))
    p.add(_cloud_disc(p, sx + 62, sy + 64, 34, 'amber', bright=False))
    p.add(_bar(p, sx + 114, sy + 48, 120, 11, 0.45))
    p.add(_bar(p, sx + 114, sy + 70, 78, 8, 0.2))
    for row in range(3):
        yy = sy + 124 + row * 22
        fade = 1.0 - row * 0.28
        p.add(p.dot(sx + 36, yy + 3, 4.5, 0.85 * fade, 'amber'))
        p.add(_bar(p, sx + 50, yy, 150 - row * 30, 7, 0.18 * fade))
        p.add(_bar(p, sx + 222, yy, 36, 7, 0.4 * fade, 'amber'))
    p.add(p.dot(sx + sw - 22, sy + 22, 4.5, 0.9, 'amber'))
    # the port where the great arc leaves the source: it caps the ribbon's end on the rim
    p.add(p.ring(a0[0], a0[1], 19, 'amber', width=1.2, opacity=0.5))
    p.add(p.orb(a0[0], a0[1], 11, 'amber', halo=False))

    # Target org tile — the focal point.
    p.add(p.glass(tx, ty, tw, th, r=32, tint='#FFE0CA' if not p.dark else None))
    if p.dark:
        rim = p.linear_gradient([(0, 'tango_soft', 0.8), (1, 'coral', 0.25)], tx, ty, tx + tw, ty + th)
        p.add(f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="32" fill="none" stroke="{rim}" '
              f'stroke-width="1.4"/>')
    p.add(_cloud_disc(p, tx + 76, ty + 80, 42, 'tango', bright=True))
    p.add(_bar(p, tx + 142, ty + 60, 136, 12, 0.55))
    p.add(_bar(p, tx + 142, ty + 84, 92, 9, 0.22))
    for row in range(3):
        yy = ty + 150 + row * 24
        p.add(p.dot(tx + 40, yy + 4, 5, 0.95, 'tango' if row != 1 else 'amber'))
        p.add(_bar(p, tx + 58, yy, 160 - (row % 2) * 34, 8, 0.2))
        p.add(_bar(p, tx + 232, yy, 50, 8, 0.5, 'tango'))
    p.add(p.glyph('check', tx + tw - 38, ty + th - 36, 34, 'tango'))

    # Landing flare where the arc meets the target.
    p.add(p.orb(a3[0], a3[1] - 2, 9, 'tango'))
    p.add(p.ring(a3[0], a3[1] - 2, 20, 'tango', width=1.4, opacity=0.6))
    p.add(p.ring(a3[0], a3[1] - 2, 32, 'amber', width=1.0, opacity=0.35))

    # A few sparkles to set the rhythm.
    for x, y, s, c in ((1880, 150, 10, 'amber'), (1860, 410, 9, 'coral'), (1420, 470, 7, 'tango'),
                       (1896, 1004, 8, 'amber'), (1120, 470, 6, 'coral')):
        p.add(_sparkle(p, x, y, s, c))
