"""Step 8 · File Library.

Stored source files and generated outputs rest on two glass shelves as folder
cards with coloured tabs. Two files drift upward out of the shelves; the newest
file floats above them all, glowing, with a ribbon of light arcing down to the
empty slot waiting for it on the top shelf.
"""
from common import W, H, fmt, smooth_d, arc_d, polar

SLUG = 'file_library'
NUMBER = 8
WORD = 'FILE LIBRARY'
SEED = 23

CARD_W, CARD_H = 104, 132
SHELVES = [  # (rail y, first x, tab colours; None marks the empty slot)
    (640, 1090, [('amber', 'file'), None, ('coral', 'table'), ('tango', 'file'), ('amber', 'table'),
                 ('tango', 'file')]),
    (880, 1262, [('coral', 'file'), ('amber', 'file'), ('tango', 'table')]),
]
BOTTOM_SHELF_OPACITY = 0.6             # the lower shelf recedes; app tables sit over it
TAB_OPACITY = 0.6                      # shelf tabs stay quiet; only the newest file's tab is at full strength
NEWEST = (1400, 118, 236, 280)         # x, y, w, h


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


def _specular(cx, cy, r):
    """A small glint on the upper-left rim of an orb, clear of the glyph it carries."""
    sx, sy = polar(cx, cy, r * 0.76, -132)
    return (f'<ellipse cx="{fmt(sx)}" cy="{fmt(sy)}" rx="{fmt(r * 0.25)}" ry="{fmt(r * 0.12)}" fill="#FFFFFF" '
            f'fill-opacity="0.55" transform="rotate(-42 {fmt(sx)} {fmt(sy)})"/>')


def _folder(p, x, y, w, h, tab, r=18, glyph_size=30, tint=None, glyph='file', tab_opacity=TAB_OPACITY):
    """A glass file card with a coloured folder tab peeking over its top edge."""
    tab_w = w * 0.42
    grad = p.linear_gradient([(0, tab, 1), (1, 'tango_deep' if tab != 'tango_deep' else 'tango', 0.9)],
                             x, y - 14, x + tab_w, y + 10)
    out = (f'<rect x="{fmt(x + 12)}" y="{fmt(y - 13)}" width="{fmt(tab_w)}" height="{fmt(28)}" rx="7" '
           f'fill="{grad}" fill-opacity="{fmt(tab_opacity)}"/>')
    out += _glass(p, x, y, w, h, r=r, tint=tint)
    out += p.glyph(glyph, x + w / 2, y + h * 0.36, glyph_size, tab)
    out += _bar(p, x + w * 0.2, y + h * 0.66, w * 0.6, 7, 0.24)
    out += _bar(p, x + w * 0.2, y + h * 0.66 + 15, w * 0.38, 7, 0.13)
    return out


def draw(p):
    rng = p.rng
    nx, ny, nw, nh = NEWEST
    ncx, ncy = nx + nw / 2, ny + nh / 2

    p.set_aurora([
        (1540, 300, 620, 460, 'tango', 0.60),
        (1900, 820, 520, 420, 'coral', 0.36),
        (1150, -40, 640, 300, 'amber', 0.50),
        (1350, 1060, 700, 340, 'peach', 0.46),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Top-band sweep, echoing the family.
    sweep = [(860, 96), (1120, 52), (1380, 70), (1700, 30), (1990, 58)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=1.8, opacity=0.62, glow=12, glow_opacity=0.4))
    p.add(p.glow_path(smooth_d([(x, y + 24) for x, y in sweep]), 'tango', width=1.1, opacity=0.42,
                      glow=8, glow_opacity=0.26))

    # Halo rings behind the newest file.
    for i, r in enumerate((190, 250, 320)):
        p.add(p.ring(ncx, ncy, r, 'tango', width=1.2, opacity=0.26 - i * 0.06, dash='2 10'))
    # arcs concentric with the newest file, kept below the sweep and clear of every card
    p.add(p.glow_path(arc_d(ncx, ncy, 250, 155, 205), 'tango', width=2.0, opacity=0.8, glow=10))
    p.add(p.glow_path(arc_d(ncx, ncy, 320, -20, 10), 'amber', width=1.8, opacity=0.7, glow=10))

    # Glass shelves (rails) with their cards.
    slot = None
    for shelf, (rail_y, x0, tabs) in enumerate(SHELVES):
        if shelf == 1:
            p.add(f'<g opacity="{BOTTOM_SHELF_OPACITY}">')
        rail_x1 = x0 + len(tabs) * (CARD_W + 18) + 40
        rx0, rw = x0 - 50, rail_x1 - x0 + 40
        if p.dark:   # warm glass on black: peach catching the light, falling to tango_deep
            slab = p.linear_gradient([(0, 'peach', 0.24), (0.5, 'tango', 0.13), (1, 'tango_deep', 0.08)],
                                     0, rail_y, 0, rail_y + 16)
            pool = p.linear_gradient([(0, 'tango', 0), (0.2, 'tango', 1), (0.7, 'tango_deep', 1), (1, 'tango_deep', 0)],
                                     rx0, 0, rx0 + rw, 0)
        else:
            slab = p.linear_gradient([(0, '#FFFFFF', 0.95), (1, '#FFFFFF', 0.35)], 0, rail_y, 0, rail_y + 16)
        fade = p.linear_gradient([(0, 'tango', 0), (0.18, 'tango', 1), (0.6, 'amber', 1), (1, 'amber', 0)],
                                 rx0, 0, rx0 + rw, 0)
        if not p.dark:
            pool = fade
        # warm light pooled under the shelf
        p.add(f'<rect x="{fmt(rx0 + 40)}" y="{fmt(rail_y + 4)}" width="{fmt(rw - 80)}" height="34" rx="17" '
              f'fill="{pool}" fill-opacity="{0.34 if p.dark else 0.22}" filter="{p.glow_filter(16)}"/>')
        p.add(f'<rect x="{fmt(rx0)}" y="{fmt(rail_y)}" width="{fmt(rw)}" height="16" rx="8" fill="{slab}" '
              f'stroke="{p.col('peach') if p.dark else '#FFFFFF'}" stroke-opacity="{0.34 if p.dark else 0.95}" stroke-width="1.2" filter="{_soft_shadow(p)}"/>')
        line_d = f'M{fmt(rx0 + 30)},{fmt(rail_y + 1)}H{fmt(rx0 + rw - 30)}'
        p.add(f'<path d="{line_d}" stroke="{fade}" stroke-width="7" stroke-opacity="{0.7 if p.dark else 0.55}" '
              f'filter="{p.glow_filter(6)}"/>')
        p.add(f'<path d="{line_d}" stroke="{fade}" stroke-width="2.2" stroke-linecap="round"/>')
        for k, tab in enumerate(tabs):
            cx = x0 + k * (CARD_W + 18)
            cy = rail_y - 8 - CARD_H + rng.uniform(-2, 2)
            if tab is None:
                slot = (cx, rail_y - 8 - CARD_H)
                inner = p.radial_gradient([(0, 'amber', 0.6 if p.dark else 0.5), (0.5, 'tango', 0.18), (1, 'tango', 0)])
                p.add(f'<ellipse cx="{fmt(cx + CARD_W / 2)}" cy="{fmt(slot[1] + CARD_H * 0.4)}" rx="{CARD_W * 0.75}" '
                      f'ry="{CARD_H * 0.62}" fill="{inner}"/>')
                p.add(f'<rect x="{fmt(cx)}" y="{fmt(slot[1])}" width="{CARD_W}" height="{CARD_H}" rx="18" '
                      f'fill="{p.col("tango")}" fill-opacity="{0.10 if p.dark else 0.08}" stroke="{p.col("tango")}" '
                      f'stroke-opacity="0.75" stroke-width="1.6" stroke-dasharray="6 7"/>')
                continue
            p.add(_folder(p, cx, cy, CARD_W, CARD_H, tab[0], glyph=tab[1]))
        if shelf == 1:
            p.add('</g>')

    # Ribbon from the newest file down into its empty slot.
    sx, sy = slot[0] + CARD_W / 2, slot[1] + 2
    p0 = (nx + 60, ny + nh - 4)
    c1 = (nx + 60, ny + nh + 120)
    c2 = (sx, sy - 130)
    p3 = (sx, sy)
    p.add(p.ribbon(p0, c1, c2, p3, width=13, colours=('tango', 'amber'), opacity=0.62))
    p.add(p.particles_along(p0, c1, c2, p3, count=11, colour='amber', r=(1.8, 3.6), end=0.88))
    p.add(p.node(sx, sy, 6, 'amber'))

    # Two files drifting upward out of the library, with rising trails.
    floaters = [(1140, 250, -11, 'coral', 0.9), (1690, 300, 9, 'amber', 0.9)]
    for fx, fy, angle, tab, scale in floaters:
        w, h = CARD_W * scale, CARD_H * scale
        trail = [(fx + w / 2 + angle * 0.8, fy + h + 150), (fx + w / 2 + angle * 0.3, fy + h + 70),
                 (fx + w / 2, fy + h + 14)]
        p.add(p.glow_path(smooth_d(trail), tab, width=1.6, opacity=0.5, glow=8, glow_opacity=0.35, dash='1 9'))
        for j in range(5):
            p.add(p.dot(fx + w / 2 + rng.uniform(-18, 18), fy + h + 30 + j * 26, rng.uniform(1.4, 3.0),
                        0.75 - j * 0.12, tab))
        p.add(f'<g transform="rotate({angle} {fmt(fx + w / 2)} {fmt(fy + h / 2)})">'
              + _folder(p, fx, fy, w, h, tab, r=16, glyph_size=28, tab_opacity=0.72) + '</g>')

    # The newest file: large, tinted, glowing.
    halo = p.radial_gradient([(0, 'tango', 0.5 * p.val('glow_boost')), (0.6, 'amber', 0.14), (1, 'amber', 0)])
    p.add(f'<ellipse cx="{fmt(ncx)}" cy="{fmt(ncy)}" rx="{fmt(nw * 1.05)}" ry="{fmt(nh * 0.95)}" fill="{halo}"/>')
    tab_grad = p.linear_gradient([(0, 'amber', 1), (1, 'tango', 1)], nx, ny, nx + 110, ny)
    p.add(f'<rect x="{fmt(nx + 18)}" y="{fmt(ny - 20)}" width="104" height="40" rx="10" fill="{tab_grad}"/>')
    p.add(_glass(p, nx, ny, nw, nh, r=30, tint='#FFE2CF' if not p.dark else None))
    p.add(p.orb(nx + 70, ny + 78, 36, 'tango', highlight=False))
    p.add(_specular(nx + 70, ny + 78, 36))
    p.add(p.glyph('file', nx + 71, ny + 80, 27, '#FFFFFF'))
    p.add(_bar(p, nx + 124, ny + 62, 84, 11, 0.55))
    p.add(_bar(p, nx + 124, ny + 86, 56, 8, 0.22))
    for row in range(4):
        yy = ny + 142 + row * 28
        p.add(p.dot(nx + 34, yy + 4, 4.5, 0.9, 'tango' if row % 2 == 0 else 'amber'))
        p.add(_bar(p, nx + 50, yy, 110 - (row % 3) * 22, 8, 0.2))
        p.add(_bar(p, nx + 176, yy, 34, 8, 0.45, 'tango'))
    p.add(p.glyph('check', nx + nw - 34, ny + nh - 34, 30, 'tango'))
    # sparkle star at the tab corner
    sx0, sy0 = nx + nw - 8, ny + 6
    star = (f'M{fmt(sx0)},{fmt(sy0 - 16)}Q{fmt(sx0 + 2)},{fmt(sy0 - 2)} {fmt(sx0 + 16)},{fmt(sy0)}'
            f'Q{fmt(sx0 + 2)},{fmt(sy0 + 2)} {fmt(sx0)},{fmt(sy0 + 16)}Q{fmt(sx0 - 2)},{fmt(sy0 + 2)} '
            f'{fmt(sx0 - 16)},{fmt(sy0)}Q{fmt(sx0 - 2)},{fmt(sy0 - 2)} {fmt(sx0)},{fmt(sy0 - 16)}Z')
    p.add(f'<path d="{star}" fill="{p.col("amber")}" filter="{p.glow_filter(6)}" opacity="0.8"/>')
    p.add(f'<path d="{star}" fill="#FFFFFF"/>')

    # Sparkles.
    for _ in range(70):
        x = rng.uniform(980, W - 30)
        y = rng.uniform(40, H - 40)
        p.add(p.dot(x, y, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
