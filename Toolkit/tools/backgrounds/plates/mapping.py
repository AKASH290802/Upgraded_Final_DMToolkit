"""Step 11 · Mapping.

Two facing columns of glass field chips (source on the left, target on the
right) joined by a woven lattice of glowing connector ribbons — a loom of
mappings. One mapping is highlighted, with an orb on its ribbon; beneath it a
glass card shows its picklist values paired off, pill to pill, with arrows.
"""
from common import W, H, fmt, smooth_d, cubic

SLUG = 'mapping'
NUMBER = 11
WORD = 'MAPPING'
SEED = 41

LEFT_X, RIGHT_X = 1060, 1650
CHIP_W, CHIP_H = 184, 56
ROWS_Y = [150, 236, 322, 408, 494, 580]
RIGHT_OFFSET = 18
PAIRS = [(0, 1), (1, 0), (2, 4), (3, 2), (4, 5), (5, 3)]   # source row -> target row
HIGHLIGHT = (2, 4)
ACCENTS = ['amber', 'coral', 'tango', 'amber', 'coral', 'tango_soft']
PICK = (1296, 760, 300, 196)            # picklist card


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


def _chip(p, x, y, accent, side, lit=False):
    out = ''
    if lit:
        glow = p.radial_gradient([(0, 'tango', 0.5 * p.val('glow_boost')), (1, 'tango', 0)])
        out += (f'<ellipse cx="{fmt(x + CHIP_W / 2)}" cy="{fmt(y + CHIP_H / 2)}" rx="{fmt(CHIP_W * 0.8)}" '
                f'ry="{fmt(CHIP_H * 1.4)}" fill="{glow}"/>')
    out += _glass(p, x, y, CHIP_W, CHIP_H, r=CHIP_H / 2, tint=('#FFD9C2' if lit else None) if not p.dark else None)
    if lit:
        out += (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{CHIP_W}" height="{CHIP_H}" rx="{fmt(CHIP_H / 2)}" '
                f'fill="none" stroke="{p.col("tango")}" stroke-width="1.8" stroke-opacity="0.9"/>')
    dot_x = x + 28 if side == 'left' else x + CHIP_W - 28
    out += p.circle(dot_x, y + CHIP_H / 2, 11, 0.22, fill=accent)
    out += p.dot(dot_x, y + CHIP_H / 2, 5.5, 1, accent)
    bx = x + 50 if side == 'left' else x + 26
    out += _bar(p, bx, y + 20, 86 if not lit else 96, 8, 0.42 if lit else 0.26)
    out += _bar(p, bx, y + 33, 52, 6, 0.14)
    return out


def _arrow(p, x0, x1, y, colour, opacity=0.9):
    return (p.line(x0, y, x1 - 6, y, opacity, 2.0, colour) +
            f'<path d="M{fmt(x1 - 9)},{fmt(y - 5)}L{fmt(x1)},{fmt(y)}L{fmt(x1 - 9)},{fmt(y + 5)}" fill="none" '
            f'stroke="{p.col(colour)}" stroke-opacity="{fmt(opacity)}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')


def draw(p):
    rng = p.rng

    p.set_aurora([
        (1480, 380, 620, 460, 'tango', 0.60),
        (1900, 140, 480, 360, 'amber', 0.46),
        (1860, 860, 520, 380, 'coral', 0.36),
        (1120, -40, 620, 300, 'peach', 0.55),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Top-band sweep, echoing the family.
    sweep = [(860, 58), (1140, 24), (1440, 46), (1760, 18), (1990, 38)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=1.8, opacity=0.6, glow=12, glow_opacity=0.4))
    p.add(p.glow_path(smooth_d([(x, y + 20) for x, y in sweep]), 'tango', width=1.1, opacity=0.4,
                      glow=8, glow_opacity=0.26))

    # The loom: faint warp threads between the columns.
    x_a, x_b = LEFT_X + CHIP_W + 30, RIGHT_X - 30
    n = 11
    y_top, y_bot = ROWS_Y[0] - 30, ROWS_Y[-1] + CHIP_H + 50
    warp = p.linear_gradient([(0, 'line', 0), (0.2, 'line', 1), (0.8, 'line', 1), (1, 'line', 0)],
                             0, y_top, 0, y_bot)
    for k in range(n):
        x = x_a + (x_b - x_a) * k / (n - 1)
        p.add(f'<path d="M{fmt(x)},{fmt(y_top)}V{fmt(y_bot)}" stroke="{warp}" '
              f'stroke-opacity="{0.10 if not p.dark else 0.11}" stroke-width="1"/>')

    # Mapping ribbons, the highlighted one last (on top).
    geo = {}
    for a, b in PAIRS:
        start = (LEFT_X + CHIP_W + 4, ROWS_Y[a] + CHIP_H / 2)
        end = (RIGHT_X - 4, ROWS_Y[b] + RIGHT_OFFSET + CHIP_H / 2)
        c1 = (start[0] + 150, start[1])
        c2 = (end[0] - 150, end[1])
        geo[(a, b)] = (start, c1, c2, end)
    # candidate threads: every other pairing, as faint hairlines — the weave
    for a in range(len(ROWS_Y)):
        for b in range(len(ROWS_Y)):
            if (a, b) in PAIRS or abs(a - b) > 3 or (a + b) % 2:
                continue
            s0 = (LEFT_X + CHIP_W + 4, ROWS_Y[a] + CHIP_H / 2)
            e0 = (RIGHT_X - 4, ROWS_Y[b] + RIGHT_OFFSET + CHIP_H / 2)
            d = (f'M{fmt(s0[0])},{fmt(s0[1])}C{fmt(s0[0] + 150)},{fmt(s0[1])} {fmt(e0[0] - 150)},{fmt(e0[1])} '
                 f'{fmt(e0[0])},{fmt(e0[1])}')
            p.add(p.path(d, 0.2 if not p.dark else 0.24, 0.9, 'tango'))
    for a, b in PAIRS:
        if (a, b) == HIGHLIGHT:
            continue
        s, c1, c2, e = geo[(a, b)]
        p.add(p.ribbon(s, c1, c2, e, width=6, colours=(ACCENTS[a], ACCENTS[b]), opacity=0.42))
        p.add(p.particles_along(s, c1, c2, e, count=5, colour=ACCENTS[a], r=(1.2, 2.4), opacity=(0.35, 0.7)))
    s, c1, c2, e = geo[HIGHLIGHT]
    p.add(p.ribbon(s, c1, c2, e, width=15, colours=('amber', 'tango'), opacity=0.78))
    p.add(p.particles_along(s, c1, c2, e, count=12, colour='amber', r=(1.8, 3.6)))

    # Ports where ribbons meet the chips.
    for a, b in PAIRS:
        s, _, _, e = geo[(a, b)]
        lit = (a, b) == HIGHLIGHT
        p.add(p.node(s[0], s[1], 5 if lit else 3.6, 'tango' if lit else ACCENTS[a]))
        p.add(p.node(e[0], e[1], 5 if lit else 3.6, 'tango' if lit else ACCENTS[b]))

    # Column headers: source file, target object.
    for x, glyph, side in ((LEFT_X, 'file', 'left'), (RIGHT_X, 'database', 'right')):
        p.add(p.glyph(glyph, x + (22 if side == 'left' else CHIP_W - 22), 96, 30, 'tango'))
        bx = x + 48 if side == 'left' else x + CHIP_W - 48 - 80
        p.add(_bar(p, bx, 88, 80, 9, 0.42))
        p.add(_bar(p, bx if side == 'left' else bx + 30, 102, 50, 6, 0.16))

    # Field chips.
    for i, y in enumerate(ROWS_Y):
        p.add(_chip(p, LEFT_X, y, ACCENTS[i], 'left', lit=i == HIGHLIGHT[0]))
        p.add(_chip(p, RIGHT_X, y + RIGHT_OFFSET, ACCENTS[i], 'right', lit=i == HIGHLIGHT[1]))

    # The highlighted mapping's orb, and its link to the picklist card.
    ox, oy = cubic(s, c1, c2, e, 0.5)
    px, py, pw, ph = PICK
    p.add(p.glow_path(f'M{fmt(ox)},{fmt(oy + 26)}C{fmt(ox)},{fmt(oy + 150)} {fmt(px + pw / 2)},{fmt(py - 150)} '
                      f'{fmt(px + pw / 2)},{fmt(py - 4)}', 'tango', width=1.8, opacity=0.8, glow=8,
                      glow_opacity=0.45, dash='2 8'))
    p.add(p.orb(ox, oy, 25, 'tango'))
    p.add(p.ring(ox, oy, 37, 'amber', width=1.4, opacity=0.8))
    p.add(p.ring(ox, oy, 52, 'tango', width=1.0, opacity=0.35, dash='2 6'))

    # Picklist value card: value pills mapped with arrows.
    p.add(_glass(p, px, py, pw, ph, r=26, tint='#FFE2CF' if not p.dark else None))
    p.add(p.dot(px + 30, py + 34, 5, 1, 'tango'))
    p.add(_bar(p, px + 46, py + 29, 110, 10, 0.46))
    rows = [('amber', 'tango', 76, 88), ('coral', 'tango', 60, 72), ('amber', 'tango', 88, 64)]
    for k, (ca, cb, wa, wb) in enumerate(rows):
        yy = py + 76 + k * 38
        pill_a = p.linear_gradient([(0, ca, 0.9), (1, ca, 0.65)], px + 28, 0, px + 28 + wa, 0)
        p.add(f'<rect x="{fmt(px + 28)}" y="{fmt(yy - 12)}" width="{wa}" height="24" rx="12" fill="{pill_a}"/>')
        p.add(_bar(p, px + 40, yy - 3, wa - 26, 6, 0.85, '#FFFFFF'))
        p.add(_arrow(p, px + 130, px + 170, yy, 'tango'))
        pill_b = p.linear_gradient([(0, cb, 0.95), (1, 'tango_deep', 0.85)], px + 182, 0, px + 182 + wb, 0)
        p.add(f'<rect x="{fmt(px + 182)}" y="{fmt(yy - 12)}" width="{wb}" height="24" rx="12" fill="{pill_b}"/>')
        p.add(_bar(p, px + 194, yy - 3, wb - 26, 6, 0.85, '#FFFFFF'))

    # Sparkles.
    for _ in range(70):
        sx = rng.uniform(980, W - 30)
        sy = rng.uniform(40, H - 40)
        p.add(p.dot(sx, sy, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
