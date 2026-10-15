"""Step 10 · Multi Data File.

One wide glass file card, its columns grouped by colour, sends a single beam
of light into a glass prism. At the prism the beam splits into a fan of
ribbons (tango, amber, coral, soft tango), each landing on its own glass
object card in the matching accent.
"""
from common import W, H, fmt, smooth_d, arc_d

SLUG = 'multi_data_file'
NUMBER = 10
WORD = 'MULTI OBJECT'
SEED = 37

FILE = (1010, 276, 272, 372)          # x, y, w, h
PRISM = (1398, 462)                   # centre of the split point
PRISM_R = 62                          # half-diagonal of the glass diamond
OBJ_X, OBJ_W, OBJ_H = 1622, 222, 128
OBJECTS = [  # (centre y, accent, glyph, tint for the light card)
    (206, 'amber', 'table', '#FFE6BF'),
    (376, 'tango', 'database', '#FFD9C2'),
    (546, 'coral', 'table', '#FFD6DA'),
    (716, 'tango_soft', 'database', '#FFE0CC'),
]
COLUMN_GROUPS = ['amber', 'amber', 'tango', 'tango', 'coral', 'coral', 'tango_soft', 'tango_soft']


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


def draw(p):
    rng = p.rng
    px, py = PRISM
    fx, fy, fw, fh = FILE

    p.set_aurora([
        (1500, 440, 560, 480, 'tango', 0.60),
        (1880, 200, 480, 380, 'amber', 0.46),
        (1880, 820, 520, 400, 'coral', 0.38),
        (1120, -40, 620, 300, 'peach', 0.55),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Top-band sweep, echoing the family.
    sweep = [(860, 100), (1140, 54), (1440, 80), (1760, 30), (1990, 60)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=1.8, opacity=0.6, glow=12, glow_opacity=0.4))
    p.add(p.glow_path(smooth_d([(x, y + 24) for x, y in sweep]), 'tango', width=1.1, opacity=0.4,
                      glow=8, glow_opacity=0.26))

    # Orbit rings around the split point.
    for i, r in enumerate((150, 230, 320)):
        p.add(p.ring(px, py, r, 'tango', width=1.2, opacity=0.26 - i * 0.06, dash='2 10'))
    p.add(p.glow_path(arc_d(px, py, 230, 200, 262), 'tango', width=2.0, opacity=0.8, glow=10))
    p.add(p.glow_path(arc_d(px, py, 320, 96, 140), 'amber', width=1.8, opacity=0.7, glow=10))

    # The fan: one ribbon per object, leaving the prism's far vertex.
    exit_x = px + PRISM_R - 6
    for i, (cy, accent, glyph, tint) in enumerate(OBJECTS):
        start = (exit_x, py + (i - 1.5) * 6)
        end = (OBJ_X, cy)
        c1 = (start[0] + (end[0] - start[0]) * 0.42, start[1] + (end[1] - start[1]) * 0.30)
        c2 = (end[0] - 80, end[1])
        p.add(p.ribbon(start, c1, c2, end, width=11, colours=('tango' if accent != 'tango' else 'amber', accent),
                       opacity=0.66))
        p.add(p.particles_along(start, c1, c2, end, count=8, colour=accent, r=(1.6, 3.4), start=0.2))

    # The single beam from the file into the prism.
    b0 = (fx + fw + 6, fy + fh / 2 - 10)
    b3 = (px - PRISM_R + 8, py)
    b1 = (b0[0] + 50, b0[1])
    b2 = (b3[0] - 50, b3[1])
    p.add(p.ribbon(b0, b1, b2, b3, width=20, colours=('amber', 'tango'), opacity=0.7))
    p.add(p.particles_along(b0, b1, b2, b3, count=6, colour='#FFFFFF', r=(1.6, 2.8), opacity=(0.6, 0.95)))

    # The wide source file.
    p.add(_glass(p, fx, fy, fw, fh, r=30))
    p.add(p.glyph('file', fx + 46, fy + 50, 36, 'tango'))
    p.add(p.node(fx + fw, b0[1], 5, 'amber'))
    p.add(_bar(p, fx + 80, fy + 38, 120, 11, 0.5))
    p.add(_bar(p, fx + 80, fy + 58, 76, 8, 0.2))
    col_w, gap = 26, 6
    gx0 = fx + (fw - (len(COLUMN_GROUPS) * col_w + (len(COLUMN_GROUPS) - 1) * gap)) / 2
    for c, accent in enumerate(COLUMN_GROUPS):
        x = gx0 + c * (col_w + gap)
        p.add(f'<rect x="{fmt(x)}" y="{fmt(fy + 96)}" width="{col_w}" height="{fh - 124}" rx="8" '
              f'fill="{p.col(accent)}" fill-opacity="{0.12 if not p.dark else 0.14}"/>')
        p.add(_bar(p, x + 3, fy + 106, col_w - 6, 10, 0.9, accent))
        for r in range(7):
            w = col_w - 8 - ((r * 3 + c * 5) % 3) * 4
            p.add(_bar(p, x + 4, fy + 134 + r * 32, w, 6, 0.22 if not p.dark else 0.26))

    # The prism — a glass diamond holding the split point.
    halo = p.radial_gradient([(0, '#FFFFFF', 0.7 if not p.dark else 0.45), (0.25, 'amber', 0.45 * p.val('glow_boost')),
                              (1, 'tango', 0)])
    p.add(f'<circle cx="{px}" cy="{py}" r="{PRISM_R * 2.4}" fill="{halo}"/>')
    d = (f'M{fmt(px - PRISM_R)},{py} Q{fmt(px - PRISM_R + 4)},{fmt(py - 4)} {fmt(px - 6)},{fmt(py - PRISM_R + 6)}'
         f' Q{px},{fmt(py - PRISM_R)} {fmt(px + 6)},{fmt(py - PRISM_R + 6)}'
         f' L{fmt(px + PRISM_R - 6)},{fmt(py - 6)} Q{fmt(px + PRISM_R)},{py} {fmt(px + PRISM_R - 6)},{fmt(py + 6)}'
         f' L{fmt(px + 6)},{fmt(py + PRISM_R - 6)} Q{px},{fmt(py + PRISM_R)} {fmt(px - 6)},{fmt(py + PRISM_R - 6)}'
         f' Q{fmt(px - PRISM_R + 4)},{fmt(py + 4)} {fmt(px - PRISM_R)},{py}Z')
    body = p.linear_gradient([(0, '#FFFFFF', 0.85 if not p.dark else 0.3), (0.5, 'peach', 0.55 if not p.dark else 0.18),
                              (1, 'tango', 0.5 if not p.dark else 0.35)],
                             px - PRISM_R, py - PRISM_R, px + PRISM_R, py + PRISM_R)
    p.add(f'<path d="{d}" fill="{body}" stroke="#FFFFFF" stroke-opacity="{0.95 if not p.dark else 0.5}" '
          f'stroke-width="1.6" filter="{_soft_shadow(p)}"/>')
    # facet lines
    p.add(p.line(px - PRISM_R + 10, py, px + PRISM_R - 10, py, 0.5 if not p.dark else 0.3, 1.0, '#FFFFFF'))
    p.add(p.line(px, py - PRISM_R + 10, px, py + PRISM_R - 10, 0.5 if not p.dark else 0.3, 1.0, '#FFFFFF'))
    p.add(p.orb(px, py, 24, 'tango', halo=True))
    p.add(p.ring(px, py, 38, 'amber', width=1.4, opacity=0.8))

    # Object cards, one accent each.
    for i, (cy, accent, glyph, tint) in enumerate(OBJECTS):
        x, y = OBJ_X, cy - OBJ_H / 2
        p.add(_glass(p, x, y, OBJ_W, OBJ_H, r=24, tint=tint if not p.dark else None))
        p.add(p.glyph(glyph, x + 46, y + 44, 34, accent))
        p.add(_bar(p, x + 80, y + 32, 86, 10, 0.48))
        p.add(_bar(p, x + 80, y + 50, 58, 7, 0.2))
        for r in range(2):
            yy = y + 84 + r * 22
            p.add(p.dot(x + 32, yy + 3.5, 4, 0.9, accent))
            p.add(_bar(p, x + 46, yy, 100 - r * 28, 7, 0.2))
            p.add(_bar(p, x + OBJ_W - 64, yy, 36, 7, 0.55, accent))
        p.add(p.dot(x + OBJ_W - 20, y + 20, 4, 0.9, accent))
        p.add(p.node(x, cy, 5, accent))

    # Sparkles.
    for _ in range(70):
        sx = rng.uniform(980, W - 30)
        sy = rng.uniform(40, H - 40)
        p.add(p.dot(sx, sy, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
