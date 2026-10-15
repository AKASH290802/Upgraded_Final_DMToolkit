"""Step 4 · Unit Testing.

A grid of small glass test tiles, nearly all passing with a check, one failing
in coral and the last two still running. Beside them a large circular gauge:
a gradient arc of light that has swept 96 % of the way round its track,
holding a glossy orb that carries the pass rate. Particles stream from the
grid into the gauge.
"""
import math

from common import W, H, cubic, fmt, lerp, smooth_d, arc_d, polar

SLUG = 'unit_testing'
NUMBER = 6
WORD = 'TEST'
SEED = 37

COLS, ROWS = 4, 5
TILE, GAP = 72, 16
GX, GY = 1028, 226                     # grid origin
FAIL = (2, 1)                          # (row, col)
RUNNING = {(4, 2), (4, 3)}
GAUGE = (1636, 440)
TRACK_R, TRACK_W = 182, 22
DISC = 212                             # outer glass disc radius
PASS_RATE = 0.96


def _filters(p):
    """Canvas-sized filter regions, so no halo or shadow is clipped to a hard edge."""
    region = f'filterUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"'
    for blur in (8, 10, 12, 18):
        p.define(f'<filter id="glow{blur}" {region}><feGaussianBlur stdDeviation="{blur}"/></filter>',
                 f'glow{blur}')
    p.define(f'<filter id="shadow_{p.mode}" {region}><feDropShadow dx="0" dy="18" stdDeviation="22" '
             f'flood-color="{p.col("shadow")}" flood-opacity="{fmt(p.val("shadow_opacity"))}"/></filter>',
             f'shadow_{p.mode}')


def _bar(p, x, y, w, h, opacity, colour=None):
    c = p._c(colour) if colour else p.col('ink')
    return (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(h / 2)}" '
            f'fill="{c}" fill-opacity="{fmt(opacity)}"/>')


def _mix(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(lerp(x, y, t)):02X}' for x, y in zip(ca, cb))


def _sweep_colour(p, t):
    """Amber -> Tango -> deep Tango along the gauge sweep (coral is kept for the failure)."""
    if t < 0.5:
        return _mix(p.col('amber'), p.col('tango_soft'), t / 0.5)
    return _mix(p.col('tango_soft'), p.col('tango_deep'), (t - 0.5) / 0.5)


def _specular(cx, cy, r):
    """A small specular glint on the upper-left rim of an orb, clear of the number it carries."""
    sx, sy = polar(cx, cy, r * 0.76, -135)
    return (f'<ellipse cx="{fmt(sx)}" cy="{fmt(sy)}" rx="{fmt(r * 0.25)}" ry="{fmt(r * 0.12)}" fill="#FFFFFF" '
            f'fill-opacity="0.55" transform="rotate(-45 {fmt(sx)} {fmt(sy)})"/>')


def _tile(p, row, col):
    x, y = GX + col * (TILE + GAP), GY + row * (TILE + GAP)
    cx = x + TILE / 2
    p.add(p.glass(x, y, TILE, TILE, r=18, tint=('#FFD9DC' if (row, col) == FAIL and not p.dark else None)))
    if (row, col) == FAIL:
        p.add(p.circle(cx, y + 31, 24, fill='coral', opacity=0.18 if not p.dark else 0.26))
        p.add(p.glyph('cross', cx, y + 31, 30, 'coral'))
        p.add(_bar(p, cx - 17, y + 54, 34, 6, 0.5, 'coral'))
    elif (row, col) in RUNNING:
        p.add(p.ring(cx, y + 31, 12, 'ink', width=2.4, opacity=0.12))
        start = 200 if col == 2 else 20
        p.add(p.glow_path(arc_d(cx, y + 31, 12, start, start + 110), 'tango', width=2.6, opacity=0.9,
                          glow=4, glow_opacity=0.4))
        p.add(_bar(p, cx - 17, y + 54, 34, 6, 0.12))
    else:
        colour = 'tango' if (row * COLS + col) % 3 else 'amber'
        p.add(p.glyph('check', cx, y + 31, 28, colour))
        p.add(_bar(p, cx - 17, y + 54, 34 - ((row + col) % 3) * 6, 6, 0.2))


def draw(p):
    rng = p.rng
    _filters(p)
    gx, gy = GAUGE

    p.set_aurora([
        (1660, 440, 560, 480, 'tango', 0.62),
        (1900, 110, 480, 340, 'amber', 0.50),
        (1180, 860, 560, 320, 'coral', 0.30),
        (1120, -40, 640, 300, 'peach', 0.55),
        (1880, 860, 380, 360, 'coral', 0.20),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Top-band sweep, the family signature.
    sweep = [(860, 104), (1180, 56), (1480, 86), (1760, 34), (1990, 62)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=2.0, opacity=0.7, glow=12, glow_opacity=0.45))
    p.add(p.glow_path(smooth_d([(x, y + 24) for x, y in sweep]), 'tango', width=1.2, opacity=0.5,
                      glow=8, glow_opacity=0.3))

    # Orbit rings around the gauge.
    for i, r in enumerate((250, 310)):
        p.add(p.ring(gx, gy, r, 'tango', width=1.2, opacity=0.30 - i * 0.08, dash='2 10'))
    # lit segments on those rings, placed where no ribbon crosses them
    p.add(p.glow_path(arc_d(gx, gy, 250, 62, 104), 'tango', width=2.2, opacity=0.85, glow=10))
    p.add(p.glow_path(arc_d(gx, gy, 310, 232, 254), 'amber', width=2.0, opacity=0.75, glow=10))

    # Particle streams from the grid into the gauge.
    right = GX + COLS * (TILE + GAP) - GAP
    for k, (y0, colours) in enumerate(((GY + 36, ('amber', 'tango')), (GY + 2 * (TILE + GAP) + 36, ('tango', 'amber')),
                                       (GY + 4 * (TILE + GAP) + 36, ('tango_soft', 'tango')))):
        p0 = (right - 6, y0)
        p3 = polar(gx, gy, DISC - 5, (206, 180, 154)[k])   # tucked under the disc rim
        p1 = (p0[0] + 50, y0)
        p2 = (p3[0] - 40, p3[1])
        p.add(p.ribbon(p0, p1, p2, p3, width=6, colours=colours, opacity=0.55))
        p.add(p.particles_along(p0, p1, p2, p3, count=6, colour=colours[1], r=(1.6, 3.0), start=0.2))

    # Test tiles.
    for row in range(ROWS):
        for col in range(COLS):
            _tile(p, row, col)

    # The gauge: frosted disc, track, gradient sweep, ticks, orb.
    disc = DISC
    p.add(p.glass(gx - disc, gy - disc, 2 * disc, 2 * disc, r=disc, tint='#FFE2CF' if not p.dark else None))
    p.add(p.ring(gx, gy, TRACK_R, 'ink', width=TRACK_W, opacity=0.07 if not p.dark else 0.10))
    for k in range(60):
        a = -90 + k * 6
        r0, r1 = (TRACK_R + 15, TRACK_R + (25 if k % 5 == 0 else 20))
        x0, y0 = polar(gx, gy, r0, a)
        x1, y1 = polar(gx, gy, r1, a)
        lit = k < 60 * PASS_RATE
        p.add(p.line(x0, y0, x1, y1, opacity=(0.6 if lit else 0.2) if k % 5 == 0 else (0.35 if lit else 0.12),
                     width=1.6 if k % 5 == 0 else 1.1, color='tango' if lit else 'ink'))
    a_end = -90 + 360 * PASS_RATE
    full = arc_d(gx, gy, TRACK_R, -90, a_end)
    glow = p.linear_gradient([(0, 'amber', 1), (0.55, 'tango', 1), (1, 'tango_deep', 1)],
                             gx, gy - TRACK_R, gx, gy + TRACK_R)
    p.add(f'<path d="{full}" fill="none" stroke="{glow}" stroke-width="{TRACK_W * 2.2}" '
          f'stroke-opacity="{0.34 if not p.dark else 0.35}" stroke-linecap="round" filter="{p.glow_filter(18)}"/>')
    steps = 72
    for k in range(steps):
        a0 = lerp(-90, a_end, k / steps)
        a1 = lerp(-90, a_end, (k + 1) / steps) + (0.6 if k < steps - 1 else 0)
        p.add(f'<path d="{arc_d(gx, gy, TRACK_R, a0, a1)}" fill="none" stroke="{_sweep_colour(p, k / steps)}" '
              f'stroke-width="{TRACK_W}" stroke-linecap="{"round" if k in (0, steps - 1) else "butt"}"/>')
    p.add(f'<path d="{full}" fill="none" stroke="#FFFFFF" stroke-width="2" stroke-opacity="0.8" '
          f'stroke-linecap="round"/>')
    ex, ey = polar(gx, gy, TRACK_R, a_end)
    p.add(p.circle(ex, ey, 22, fill='tango', opacity=0.28))
    p.add(p.circle(ex, ey, 8, fill='#FFFFFF', opacity=0.95))
    p.add(p.ring(gx, gy, TRACK_R - 38, 'tango', width=1.2, opacity=0.4, dash='2 8'))

    orb_r = 92
    p.add(p.orb(gx, gy, orb_r, 'tango', highlight=False))
    p.add(_specular(gx, gy, orb_r))
    p.add(p.text(gx, gy + 24, '96%', size=40, opacity=0.97, anchor='middle', spacing=0.5,
                 color='#FFFFFF', weight=700))
    p.add(_bar(p, gx - 24, gy + 42, 48, 6, 0.55, '#FFFFFF'))

    # Sparkles.
    for _ in range(70):
        x = rng.uniform(1000, W - 30)
        y = rng.uniform(40, H - 40)
        p.add(p.dot(x, y, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
