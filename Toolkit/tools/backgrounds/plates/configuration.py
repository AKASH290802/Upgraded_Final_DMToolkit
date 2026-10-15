"""Configuration — connection settings.

Three glass connection tiles (a cloud org and two databases) send glowing
cables into one bright junction orb: the connection that tested true. A thick
ribbon carries it on into a glass settings panel of toggles and sliders,
guarded by a shield and a gear.
"""
import math

from common import W, H, cubic, fmt, lerp, smooth_d

SLUG = 'configuration'
NUMBER = 2
WORD = 'CONFIGURATION'
SEED = 23

TILE_W, TILE_H = 150, 104
TILES = [  # (x, y, glyph, glyph colour, cable colours, exit side)
    (1070, 150, 'cloud', 'tango', ('amber', 'tango'), 'right'),
    (1020, 440, 'database', 'tango', ('coral', 'tango'), 'right'),
    (1110, 730, 'database', 'amber', ('amber', 'coral'), 'right'),
]
JUNCTION = (1375.0, 500.0)
JR = 46
PANEL = (1500, 250, 330, 470)     # x, y, w, h


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


def _lock(p, cx, cy, s, colour):
    c = p.col(colour) if not colour.startswith('#') else colour
    k = s / 34.0
    return (f'<path d="M{fmt(cx - 7 * k)},{fmt(cy - 2 * k)}v{fmt(-5 * k)}a{fmt(7 * k)},{fmt(7 * k)} 0 0 1 '
            f'{fmt(14 * k)},0v{fmt(5 * k)}" fill="none" stroke="{c}" stroke-width="{fmt(2.6 * k)}" '
            f'stroke-linecap="round"/>'
            f'<rect x="{fmt(cx - 11 * k)}" y="{fmt(cy - 3 * k)}" width="{fmt(22 * k)}" height="{fmt(17 * k)}" '
            f'rx="{fmt(3.5 * k)}" fill="{c}"/>'
            f'<circle cx="{fmt(cx)}" cy="{fmt(cy + 4.5 * k)}" r="{fmt(2.4 * k)}" fill="#FFFFFF"/>')


def _badge(p, cx, cy, r):
    """A round glass badge; on dark it gets a smoked body so the glyph never sinks into a ribbon."""
    body = '#FFFFFF' if not p.dark else '#231C22'
    return (f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="{body}" '
            f'fill-opacity="{fmt(0.86 if not p.dark else 0.92)}" stroke="#FFFFFF" '
            f'stroke-opacity="{fmt(0.95 if not p.dark else 0.3)}" stroke-width="1.4" filter="{_badge_shadow(p)}"/>')


def _badge_shadow(p):
    """A soft drop shadow with a filter region generous enough for small round badges."""
    fid = f"badge_shadow_{p.mode}"
    p.define(f'<filter id="{fid}" x="-100%" y="-100%" width="300%" height="340%">'
             f'<feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="{p.col("shadow")}" '
             f'flood-opacity="{fmt(p.val("shadow_opacity"))}"/></filter>', fid)
    return f"url(#{fid})"


def _toggle(p, x, y, on):
    w, h = 46, 24
    if on:
        g = p.linear_gradient([(0, 'amber', 1), (1, 'tango', 1)], x, y, x + w, y)
        out = f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{w}" height="{h}" rx="12" fill="{g}"/>'
        kx = x + w - 12
    else:
        out = (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{w}" height="{h}" rx="12" fill="{p.col("ink")}" '
               f'fill-opacity="0.12"/>')
        kx = x + 12
    out += (f'<circle cx="{fmt(kx)}" cy="{fmt(y + h / 2 + 1)}" r="9.5" fill="#000000" fill-opacity="0.12"/>'
            f'<circle cx="{fmt(kx)}" cy="{fmt(y + h / 2)}" r="9" fill="#FFFFFF"/>')
    return out


def _slider(p, x, y, w, frac, colours):
    g = p.linear_gradient([(0, colours[0], 1), (1, colours[1], 1)], x, y, x + w * frac, y)
    kx = x + w * frac
    return (_bar(p, x, y - 3, w, 6, 0.10)
            + f'<rect x="{fmt(x)}" y="{fmt(y - 3)}" width="{fmt(w * frac)}" height="6" rx="3" fill="{g}"/>'
            + p.circle(kx, y, 15, 0.22, fill=colours[1])
            + f'<circle cx="{fmt(kx)}" cy="{fmt(y)}" r="9" fill="#FFFFFF" stroke="{p.col(colours[1])}" stroke-width="3"/>')


def _glyph_orb(p, cx, cy, r):
    """An orb that carries a glyph: its halo and body, with the lit core and a small specular
    pushed to the upper-left rim so nothing pale sits under the glyph."""
    halo = p.radial_gradient([(0, 'tango', 0.55 * p.val('glow_boost')), (1, 'tango', 0)])
    body = p.radial_gradient([(0, '#FFFFFF', 0.9), (0.2, 'tango_soft', 1), (0.55, 'tango', 1), (1, 'tango_deep', 1)],
                             cx=0.3, cy=0.26, r=0.8)
    a = math.radians(-128)
    sx, sy = cx + r * 0.7 * math.cos(a), cy + r * 0.7 * math.sin(a)
    return (f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r * 3)}" fill="{halo}"/>'
            f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="{body}"/>'
            f'<ellipse cx="{fmt(sx)}" cy="{fmt(sy)}" rx="{fmt(r * 0.14)}" ry="{fmt(r * 0.075)}" fill="#FFFFFF" '
            f'fill-opacity="0.55" transform="rotate(-38 {fmt(sx)} {fmt(sy)})"/>')


def draw(p):
    rng = p.rng
    jx, jy = JUNCTION
    px, py, pw, ph = PANEL

    p.set_aurora([
        (1420, 500, 560, 460, 'tango', 0.56),
        (1860, 200, 520, 380, 'amber' if not p.dark else 'tango_soft', 0.48 if not p.dark else 0.38),
        (1700, 980, 600, 360, 'coral', 0.34 if not p.dark else 0.28),
        (1120, -40, 620, 300, 'peach', 0.55),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Decorative sweep across the top band.
    sweep = [(880, 110), (1180, 64), (1480, 100), (1760, 46), (1990, 80)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=1.8, opacity=0.65, glow=12, glow_opacity=0.4))
    p.add(p.glow_path(smooth_d([(x, y + 24) for x, y in sweep]), 'tango', width=1.1, opacity=0.45,
                      glow=8, glow_opacity=0.28))

    # Signal rings radiating from the junction.
    for i, r in enumerate((96, 150, 214)):
        p.add(p.ring(jx, jy, r, 'tango', width=1.2, opacity=0.34 - i * 0.08, dash='2 10' if i else None))
    # A lit segment of the inner ring, clear of every cable and of the main ribbon.
    ax0, ay0 = jx + 96 * math.cos(math.radians(22)), jy + 96 * math.sin(math.radians(22))
    ax1, ay1 = jx + 96 * math.cos(math.radians(100)), jy + 96 * math.sin(math.radians(100))
    p.add(p.glow_path(f"M{fmt(ax0)},{fmt(ay0)}A96,96 0 0 1 {fmt(ax1)},{fmt(ay1)}",
                      'amber', width=2.4, opacity=0.9, glow=8, glow_opacity=0.45))
    p.add(p.dot(ax0, ay0, 4, 1.0, 'amber'))

    # Cables: each tile -> junction orb, with particles.
    approach = (218, 180, 138)       # angle at which each cable meets the orb
    lock_at = None
    for i, ((x, y, glyph, gc, cols, side), ang) in enumerate(zip(TILES, approach)):
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)
        end = (jx + ux * (JR - 2), jy + uy * (JR - 2))
        start = (x + TILE_W - 5, y + TILE_H / 2)   # tucked under the tile rim
        reach = abs(end[0] - start[0])
        c1 = (start[0] + reach * 0.55, start[1])
        c2 = (jx + ux * (JR + reach * 0.55), jy + uy * (JR + reach * 0.55))
        p.add(_ribbon(p, start, c1, c2, end, width=10, colours=cols, opacity=0.62))
        p.add(p.particles_along(start, c1, c2, end, count=8, colour=cols[1], r=(1.6, 3.2), end=0.85))
        if i == 0:
            lock_at = cubic(start, c1, c2, end, 0.42)

    # Junction -> settings panel: the main ribbon.
    a, b = (jx + JR - 10, jy), (px - 4, jy)          # ends on a port on the panel rim
    p.add(_ribbon(p, a, (a[0] + 40, a[1]), (b[0] - 40, b[1]), b, width=16, colours=('tango', 'amber'), opacity=0.7))
    p.add(p.particles_along(a, (a[0] + 40, a[1]), (b[0] - 40, b[1]), b, count=5, colour='amber', r=(2, 3.4)))

    # Lock badge riding the cloud cable.
    lx, ly = lock_at
    p.add(_badge(p, lx, ly, 26))
    p.add(_lock(p, lx, ly - 1, 30, 'tango'))

    # Connection tiles.
    for x, y, glyph, gc, cols, side in TILES:
        p.add(p.glass(x, y, TILE_W, TILE_H, r=22))
        p.add(p.glyph(glyph, x + 46, y + TILE_H / 2, 40, gc))
        p.add(_bar(p, x + 78, y + 38, 58, 7, 0.24))
        p.add(_bar(p, x + 78, y + 54, 40, 7, 0.12))
        p.add(p.dot(x + TILE_W - 18, y + 18, 4, 0.95, 'tango'))

    # Settings panel.
    p.add(p.glass(px, py, pw, ph, r=30))
    p.add(p.glyph('shield', px + 50, py + 54, 38, 'tango'))
    p.add(_bar(p, px + 86, py + 42, 120, 11, 0.5))
    p.add(_bar(p, px + 86, py + 62, 80, 8, 0.2))
    p.add(p.line(px + 28, py + 102, px + pw - 28, py + 102, opacity=0.10, color='ink'))
    for row, on in enumerate((True, True, False)):
        yy = py + 128 + row * 52
        p.add(p.dot(px + 36, yy + 12, 5, 0.9, ('tango', 'amber', 'coral')[row]))
        p.add(_bar(p, px + 54, yy + 8, (130, 104, 118)[row], 8, 0.22))
        p.add(_toggle(p, px + pw - 78, yy, on))
    p.add(p.line(px + 28, py + 292, px + pw - 28, py + 292, opacity=0.10, color='ink'))
    for row, (frac, cols) in enumerate(((0.72, ('amber', 'tango')), (0.45, ('coral', 'tango')))):
        yy = py + 330 + row * 48
        p.add(_bar(p, px + 30, yy - 22, 70, 7, 0.18))
        p.add(_slider(p, px + 30, yy, pw - 60, frac, cols))
    # "test connection" pill
    g = p.linear_gradient([(0, 'tango', 1), (1, 'coral', 1)], px + 30, 0, px + pw - 30, 0)
    p.add(f'<rect x="{fmt(px + 30)}" y="{fmt(py + ph - 64)}" width="{fmt(pw - 60)}" height="38" rx="19" fill="{g}"/>')
    p.add(f'<rect x="{fmt(px + pw / 2 - 40)}" y="{fmt(py + ph - 49)}" width="80" height="8" rx="4" '
          f'fill="#FFFFFF" fill-opacity="0.9"/>')

    # The port where the main ribbon lands on the panel rim.
    p.add(p.circle(px, jy, 14, 0.22 if not p.dark else 0.3, fill='amber'))
    p.add(f'<circle cx="{fmt(px)}" cy="{fmt(jy)}" r="7" fill="#FFFFFF" stroke="{p.col("tango")}" stroke-width="3"/>')

    # Gear disc on the panel's top-right corner.
    gx, gy = px + pw - 6, py - 4
    p.add(p.ring(gx, gy, 54, 'amber', width=1.4, opacity=0.6, dash='3 8'))
    p.add(_badge(p, gx, gy, 40))
    p.add(p.glyph('gear', gx, gy, 40, 'tango').replace(p.col('paper'), '#FFFFFF'))

    # The junction orb: the connection that tested true.
    bloom = p.radial_gradient([(0, '#FFFFFF' if not p.dark else 'amber', 0.6 if not p.dark else 0.35),
                               (0.5, 'tango_soft', 0.25), (1, 'tango', 0)])
    p.add(f'<circle cx="{fmt(jx)}" cy="{fmt(jy)}" r="140" fill="{bloom}"/>')
    p.add(_glyph_orb(p, jx, jy, JR))
    check = f"M{fmt(jx - 16)},{fmt(jy + 1)}l11,11l22,-23"
    p.add(f'<path d="{check}" fill="none" stroke="{p.col("tango_deep")}" stroke-opacity="0.45" '
          f'stroke-width="7.5" stroke-linecap="round" stroke-linejoin="round" transform="translate(0 1.6)"/>')
    p.add(f'<path d="{check}" fill="none" stroke="#FFFFFF" '
          f'stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>')

    # Sparkles.
    for _ in range(70):
        x = rng.uniform(980, W - 30)
        y = rng.uniform(40, H - 40)
        p.add(p.dot(x, y, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
