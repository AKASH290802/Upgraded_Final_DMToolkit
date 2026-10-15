"""Step 9 · Migration Readiness.

A glowing readiness radar: concentric rings, a gradient sweep and blips (the
checks being scanned). At its centre a glossy score orb wrapped in a progress
gauge. Schema-sync and mapped-file chips feed it; below it a glass checklist
card reports the passes and the one open issue.
"""
from common import W, H, fmt, polar, arc_d, smooth_d

SLUG = 'migration_readiness'
NUMBER = 9
WORD = 'READINESS'
SEED = 29

C = (1580, 420)               # radar centre
RINGS = (150, 215, 280)
ORB_R = 70
GAUGE_R = 98
SCORE = 0.92
LEAD = -28                    # sweep leading edge, degrees (0 = east, clockwise)
TRAIL = 80                    # sweep length, degrees
CHIPS = [(1040, 120, 'gear', 'amber'), (1060, 300, 'file', 'coral')]
CHIP_W, CHIP_H = 150, 96
CHECK = (1040, 636, 300, 300)
ROWS = ['check', 'check', 'check', 'cross', 'check']


def _soft_shadow(p):
    """A drop shadow with a roomy filter region, so small shapes' shadows are never clipped."""
    fid = f'softshadow_{p.mode}'
    p.define(f'<filter id="{fid}" x="-40%" y="-80%" width="180%" height="300%">'
             f'<feDropShadow dx="0" dy="14" stdDeviation="16" flood-color="{p.col("shadow")}" '
             f'flood-opacity="{fmt(p.val("shadow_opacity"))}"/></filter>', fid)
    return f'url(#{fid})'


def _glass(p, x, y, w, h, r=22, tint=None):
    """p.glass with the roomier shadow."""
    return p.glass(x, y, w, h, r=r, tint=tint).replace(p.shadow_filter(), _soft_shadow(p))


def _bar(p, x, y, w, h=8, opacity=0.2, colour=None):
    c = p._c(colour) if colour else p.col('ink')
    return (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(h / 2)}" '
            f'fill="{c}" fill-opacity="{fmt(opacity)}"/>')


def _wedge(cx, cy, r0, r1, a0, a1):
    x0, y0 = polar(cx, cy, r1, a0)
    x1, y1 = polar(cx, cy, r1, a1)
    x2, y2 = polar(cx, cy, r0, a1)
    x3, y3 = polar(cx, cy, r0, a0)
    return (f'M{fmt(x0)},{fmt(y0)}A{fmt(r1)},{fmt(r1)} 0 0 1 {fmt(x1)},{fmt(y1)}'
            f'L{fmt(x2)},{fmt(y2)}A{fmt(r0)},{fmt(r0)} 0 0 0 {fmt(x3)},{fmt(y3)}Z')


def draw(p):
    rng = p.rng
    cx, cy = C
    boost = p.val('glow_boost')

    p.set_aurora([
        (1600, 420, 600, 500, 'tango', 0.62),
        (1920, 100, 480, 360, 'amber', 0.46),
        (1220, 980, 640, 360, 'coral', 0.30),
        (1120, -40, 620, 300, 'peach', 0.55),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Top-band sweep, echoing the family.
    sweep = [(860, 110), (1140, 58), (1440, 84), (1760, 34), (1990, 64)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=1.8, opacity=0.6, glow=12, glow_opacity=0.4))
    p.add(p.glow_path(smooth_d([(x, y + 24) for x, y in sweep]), 'tango', width=1.1, opacity=0.4,
                      glow=8, glow_opacity=0.26))

    # Radar disc: a soft glass face under the rings.
    if p.dark:
        face = p.radial_gradient([(0, 'tango', 0.0), (0.72, 'tango', 0.05), (1, 'amber', 0.08)])
    else:
        face = p.radial_gradient([(0, '#FFFFFF', 0.0), (0.72, '#FFFFFF', 0.18), (1, '#FFFFFF', 0.42)])
    p.add(f'<circle cx="{cx}" cy="{cy}" r="{RINGS[-1]}" fill="{face}"/>')

    # Crosshair and ticks.
    ink = 'line'
    for a in (0, 90, 180, 270):
        x0, y0 = polar(cx, cy, GAUGE_R + 18, a)
        x1, y1 = polar(cx, cy, RINGS[-1] + 24, a)
        p.add(p.line(x0, y0, x1, y1, 0.14 if not p.dark else 0.16, 1.0, p.col(ink)))
    for a in range(0, 360, 6):
        r0 = RINGS[-1] + (6 if a % 30 else 2)
        x0, y0 = polar(cx, cy, r0, a)
        x1, y1 = polar(cx, cy, RINGS[-1] + 12, a)
        p.add(p.line(x0, y0, x1, y1, 0.3 if a % 30 == 0 else 0.16, 1.2, 'tango'))

    # Rings.
    for i, r in enumerate(RINGS):
        p.add(p.ring(cx, cy, r, 'tango', width=1.3, opacity=0.34 - i * 0.05, dash=None if i == 2 else '2 8'))
    p.add(p.glow_path(arc_d(cx, cy, RINGS[-1], 150, 235), 'tango', width=2.2, opacity=0.85, glow=10))
    p.add(p.glow_path(arc_d(cx, cy, RINGS[1], 40, 110), 'amber', width=2.0, opacity=0.75, glow=10))
    for i, r in enumerate((360, 430)):
        p.add(p.ring(cx, cy, r, 'tango', width=1.1, opacity=0.18 - i * 0.06, dash='2 10'))

    # Sweep sector: many thin wedges fading toward the trailing edge.
    tx, ty = polar(cx, cy, (GAUGE_R + RINGS[-1]) / 2, LEAD - TRAIL)
    hx, hy = polar(cx, cy, (GAUGE_R + RINGS[-1]) / 2, LEAD)
    peak = 0.62 if not p.dark else 0.46
    sweep_fill = p.linear_gradient([(0, 'tango', 0), (0.55, 'tango', peak * 0.35), (1, 'tango_soft' if not p.dark else 'amber', peak)],
                                   tx, ty, hx, hy)
    wedge = _wedge(cx, cy, GAUGE_R + 14, RINGS[-1], LEAD - TRAIL, LEAD)
    p.add(f'<path d="{wedge}" fill="{sweep_fill}"/>')
    lx0, ly0 = polar(cx, cy, GAUGE_R + 14, LEAD)
    lx1, ly1 = polar(cx, cy, RINGS[-1], LEAD)
    p.add(p.glow_path(f'M{fmt(lx0)},{fmt(ly0)}L{fmt(lx1)},{fmt(ly1)}', 'amber' if p.dark else 'tango', width=2.6, opacity=1, glow=8,
                      glow_opacity=0.7))
    p.add(p.line(lx0, ly0, lx1, ly1, 0.9, 1.2, '#FFFFFF'))

    # Blips: checks being scanned; the ones just swept are brightest.
    blips = [(-40, 250, 'tango', 1.0), (-70, 180, 'amber', 0.9), (-95, 245, 'tango', 0.75),
             (20, 190, 'tango', 0.55), (70, 255, 'amber', 0.5), (140, 175, 'tango', 0.5),
             (200, 240, 'amber', 0.5), (250, 190, 'tango', 0.45)]
    for a, r, colour, strength in blips:
        bx, by = polar(cx, cy, r, a)
        if strength > 0.7:
            p.add(p.circle(bx, by, 16, 0.22 * strength, fill=colour))
            p.add(p.ring(bx, by, 11, colour, width=1.2, opacity=0.6 * strength))
        p.add(p.dot(bx, by, 5 if strength > 0.7 else 3.6, min(1, 0.4 + strength * 0.6), colour))
    # the one open issue, in coral with a pulse
    ix, iy = polar(cx, cy, 262, 118)
    p.add(p.circle(ix, iy, 20, 0.2, fill='coral'))
    p.add(p.ring(ix, iy, 14, 'coral', width=1.4, opacity=0.8))
    p.add(p.ring(ix, iy, 24, 'coral', width=1.0, opacity=0.35))
    p.add(p.dot(ix, iy, 5.5, 1, 'coral'))

    # Input chips (schema sync, mapped file) feeding the gauge.
    for i, (x, y, glyph, colour) in enumerate(CHIPS):
        start = (x + CHIP_W, y + CHIP_H / 2)
        end = polar(cx, cy, GAUGE_R + 4, 200 - i * 22)
        c1 = (start[0] + 140, start[1])
        c2 = (end[0] - 110, end[1] + (-30 if i == 0 else 20))
        p.add(p.ribbon(start, c1, c2, end, width=11, colours=(colour, 'tango'), opacity=0.6))
        p.add(p.particles_along(start, c1, c2, end, count=8, colour='tango', r=(1.6, 3.2)))
    for x, y, glyph, colour in CHIPS:
        p.add(_glass(p, x, y, CHIP_W, CHIP_H, r=22))
        p.add(p.glyph(glyph, x + 44, y + CHIP_H / 2, 36, colour))
        p.add(_bar(p, x + 76, y + 36, 56, 7, 0.22))
        p.add(_bar(p, x + 76, y + 52, 38, 7, 0.12))
        p.add(p.dot(x + CHIP_W - 18, y + 18, 4, 0.9, 'tango'))

    # Gauge around the score orb.
    p.add(p.ring(cx, cy, GAUGE_R, 'tango', width=10, opacity=0.12 if not p.dark else 0.16))
    a_end = -90 + SCORE * 360
    gauge = arc_d(cx, cy, GAUGE_R, -90, a_end)
    grad = p.linear_gradient([(0, 'amber', 1), (0.5, 'tango', 1), (1, 'coral', 1)],
                             cx - GAUGE_R, cy - GAUGE_R, cx + GAUGE_R, cy + GAUGE_R)
    p.add(f'<path d="{gauge}" fill="none" stroke="{grad}" stroke-width="22" stroke-opacity="{fmt(0.5 * boost)}" '
          f'stroke-linecap="round" filter="{p.glow_filter(10)}"/>')
    p.add(f'<path d="{gauge}" fill="none" stroke="{grad}" stroke-width="10" stroke-linecap="round"/>')
    p.add(f'<path d="{gauge}" fill="none" stroke="#FFFFFF" stroke-width="1.6" stroke-opacity="0.9" '
          f'stroke-linecap="round"/>')
    ex, ey = polar(cx, cy, GAUGE_R, a_end)
    p.add(p.dot(ex, ey, 8, 1, '#FFFFFF'))
    p.add(p.ring(ex, ey, 8, 'coral', width=2.4, opacity=1))

    # Score orb — the focal point.
    p.add(p.orb(cx, cy, ORB_R, 'tango', highlight=False))
    p.add(f'<ellipse cx="{fmt(cx - 30)}" cy="{fmt(cy - 38)}" rx="17" ry="8" fill="#FFFFFF" fill-opacity="0.55" '
          f'transform="rotate(-30 {fmt(cx - 30)} {fmt(cy - 38)})"/>')
    p.add(p.text(cx, cy + 13, '92%', size=34, opacity=0.96, family='Segoe UI', anchor='middle', spacing=0.5,
                 color='#FFFFFF', weight=700))

    # Checklist card with its rows, tied to the orb.
    x, y, w, h = CHECK
    o0 = polar(cx, cy, GAUGE_R + 6, 132)
    o3 = (x + w - 70, y + 4)
    o1 = (o0[0] - 40, o0[1] + 60)
    o2 = (o3[0] + 30, o3[1] - 70)
    p.add(p.ribbon(o0, o1, o2, o3, width=8, colours=('tango', 'amber'), opacity=0.55))
    p.add(p.particles_along(o0, o1, o2, o3, count=5, colour='amber', r=(1.6, 3.0)))
    p.add(_glass(p, x, y, w, h, r=28, tint='#FFE2CF' if not p.dark else None))
    p.add(p.glyph('shield', x + 44, y + 48, 34, 'tango'))
    p.add(_bar(p, x + 76, y + 36, 120, 11, 0.5))
    p.add(_bar(p, x + 76, y + 56, 76, 8, 0.2))
    for k, kind in enumerate(ROWS):
        yy = y + 106 + k * 36
        colour = 'coral' if kind == 'cross' else ('tango' if k % 2 == 0 else 'amber')
        p.add(p.glyph(kind, x + 40, yy, 22, colour))
        p.add(_bar(p, x + 64, yy - 4, 150 - (k % 3) * 28, 8, 0.22 if kind != 'cross' else 0.3))
        p.add(_bar(p, x + w - 70, yy - 4, 40, 8, 0.45, colour))

    # Sparkles.
    for _ in range(70):
        sx = rng.uniform(980, W - 30)
        sy = rng.uniform(40, H - 40)
        p.add(p.dot(sx, sy, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
