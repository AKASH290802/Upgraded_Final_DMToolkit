"""Step 2 · Mapping & Validation.

A column of glass source-column chips on the left and a column of glass
target-field chips on the right. Every mapping is a luminous ribbon that is
drawn through one glossy shield orb in the middle: the validation gate. Five
rows pass in Tango and amber and land on their fields; one row turns coral as
it leaves the gate and falls away to a cross, and its target field stays empty.
"""
from common import W, H, cubic, fmt, lerp, smooth_d, arc_d, polar

SLUG = 'mapping_validation'
NUMBER = 4
WORD = 'MAP & VALIDATE'
SEED = 23

SRC_X, SRC_W, CHIP_H = 1036, 172, 62
TGT_X, TGT_W = 1668, 188
SRC_Y = [285, 367, 449, 531, 613, 695]          # chip centres
TGT_Y = [290, 370, 450, 530, 610, 690]
GATE = (1450, 490)                               # shield orb centre
ORB_R = 58
BAD = 4                                          # the invalid row
CROSS = (1512, 692)                              # where it is stopped
ROW_COLOURS = [('amber', 'tango'), ('tango', 'amber'), ('tango_soft', 'tango'),
               ('amber', 'tango'), ('tango', 'coral'), ('tango', 'amber')]


def _bar(p, x, y, w, h, opacity, colour='ink'):
    return (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(h / 2)}" '
            f'fill="{p._c(colour) if colour != "ink" else p.col("ink")}" fill-opacity="{fmt(opacity)}"/>')


def _column_glyph(p, cx, cy, colour):
    """A source column: three stacked cells, the header cell filled."""
    c = p._c(colour)
    out = ''
    for k in range(3):
        y = cy - 13 + k * 9
        fill = f'fill="{c}" fill-opacity="{0.9 if k == 0 else 0.14}"'
        out += (f'<rect x="{fmt(cx - 9)}" y="{fmt(y)}" width="18" height="8" rx="2.4" {fill} '
                f'stroke="{c}" stroke-width="1.8"/>')
    return out


def _field_glyph(p, cx, cy, colour):
    """A target field: a leading dot, then an input box holding a short value."""
    c = p._c(colour)
    return (f'<circle cx="{fmt(cx - 15)}" cy="{fmt(cy)}" r="3.6" fill="{c}"/>'
            f'<rect x="{fmt(cx - 8)}" y="{fmt(cy - 8)}" width="24" height="16" rx="4" fill="{c}" '
            f'fill-opacity="0.14" stroke="{c}" stroke-width="1.8"/>'
            f'<rect x="{fmt(cx - 4)}" y="{fmt(cy - 2.5)}" width="11" height="5" rx="2.5" fill="{c}" '
            f'fill-opacity="0.9"/>')


def _specular(cx, cy, r):
    """A small specular glint on the upper-left rim of an orb, clear of anything it carries."""
    sx, sy = polar(cx, cy, r * 0.74, -135)
    return (f'<ellipse cx="{fmt(sx)}" cy="{fmt(sy)}" rx="{fmt(r * 0.25)}" ry="{fmt(r * 0.12)}" fill="#FFFFFF" '
            f'fill-opacity="0.55" transform="rotate(-45 {fmt(sx)} {fmt(sy)})"/>')


def _shield_d(cx, cy, k):
    return (f'M{fmt(cx)},{fmt(cy - 16 * k)}l{fmt(13 * k)},{fmt(5 * k)}v{fmt(9 * k)}c0,{fmt(9 * k)} '
            f'{fmt(-6 * k)},{fmt(15 * k)} {fmt(-13 * k)},{fmt(18 * k)}c{fmt(-7 * k)},{fmt(-3 * k)} '
            f'{fmt(-13 * k)},{fmt(-9 * k)} {fmt(-13 * k)},{fmt(-18 * k)}v{fmt(-9 * k)}Z')


def _filters(p):
    """Canvas-sized filter regions, so no halo or shadow is ever clipped to a hard edge."""
    region = f'filterUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"'
    for blur in (8, 10, 12, 18):
        p.define(f'<filter id="glow{blur}" {region}><feGaussianBlur stdDeviation="{blur}"/></filter>',
                 f'glow{blur}')
    p.define(f'<filter id="shadow_{p.mode}" {region}><feDropShadow dx="0" dy="18" stdDeviation="22" '
             f'flood-color="{p.col("shadow")}" flood-opacity="{fmt(p.val("shadow_opacity"))}"/></filter>',
             f'shadow_{p.mode}')


def draw(p):
    rng = p.rng
    gx, gy = GATE
    _filters(p)

    p.set_aurora([
        (1470, 470, 560, 460, 'tango', 0.60),
        (1880, 150, 520, 360, 'amber', 0.50),
        (1560, 900, 520, 300, 'coral', 0.34),
        (1100, -40, 640, 300, 'peach', 0.55),
        (1900, 700, 360, 420, 'amber', 0.22),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Top-band sweep, the family signature.
    sweep = [(880, 96), (1200, 44), (1520, 78), (1800, 30), (1990, 58)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=2.0, opacity=0.7, glow=12, glow_opacity=0.45))
    p.add(p.glow_path(smooth_d([(x, y + 24) for x, y in sweep]), 'tango', width=1.2, opacity=0.5,
                      glow=8, glow_opacity=0.3))

    # Orbit rings around the gate.
    for i, r in enumerate((160, 232, 316)):
        p.add(p.ring(gx, gy, r, 'tango', width=1.2, opacity=0.28 - i * 0.07, dash='2 10'))
    p.add(p.glow_path(arc_d(gx, gy, 160, 250, 318), 'tango', width=2.2, opacity=0.85, glow=10))

    # Mapping ribbons: source -> through the gate -> target.
    rim = 103                                    # tucked under the lens ring
    spread = [(i - 2.5) * 7.5 for i in range(6)]  # entry angles off the horizontal
    for i, (sy, ty) in enumerate(zip(SRC_Y, TGT_Y)):
        c_in, c_out = ROW_COLOURS[i]
        a0 = (SRC_X + SRC_W, sy)
        a3 = polar(gx, gy, rim, 180 - spread[i])
        a1, a2 = (a0[0] + 110, sy), (a3[0] - 110, a3[1])
        w = 10.5 - abs(i - 2.5) * 0.9
        p.add(p.ribbon(a0, a1, a2, a3, width=w, colours=(c_in, 'tango'), opacity=0.62))
        p.add(p.particles_along(a0, a1, a2, a3, count=7, colour=c_in, r=(1.6, 3.2), end=0.8))
        b0 = polar(gx, gy, rim, spread[i])
        if i == BAD:
            end = CROSS
            b1, b2 = (b0[0] + 70, b0[1] + 10), (end[0] + 30, end[1] - 80)
            p.add(p.ribbon(b0, b1, b2, end, width=w, colours=('tango', 'coral'), opacity=0.7))
            p.add(p.particles_along(b0, b1, b2, end, count=6, colour='coral', r=(1.6, 3.0), start=0.25))
            continue
        b3 = (TGT_X, ty)
        b1, b2 = (b0[0] + 110, b0[1]), (b3[0] - 110, ty)
        p.add(p.ribbon(b0, b1, b2, b3, width=w, colours=('tango', c_out), opacity=0.62))
        p.add(p.particles_along(b0, b1, b2, b3, count=7, colour=c_out, r=(1.6, 3.2), start=0.2))

    # Column headers: a file above the sources, a cloud object above the targets.
    p.add(p.glass(SRC_X, 150, SRC_W, 70, r=20, tint='#FFE9C8' if not p.dark else None))
    p.add(p.glyph('file', SRC_X + 38, 185, 30, 'amber'))
    p.add(_bar(p, SRC_X + 66, 174, 78, 8, 0.30))
    p.add(_bar(p, SRC_X + 66, 190, 48, 7, 0.14))
    p.add(p.glass(TGT_X, 150, TGT_W, 70, r=20, tint='#FFE2CF' if not p.dark else None))
    p.add(p.glyph('cloud', TGT_X + 40, 187, 34, 'tango'))
    p.add(_bar(p, TGT_X + 72, 174, 86, 8, 0.30))
    p.add(_bar(p, TGT_X + 72, 190, 52, 7, 0.14))

    # Source column chips.
    widths = (74, 58, 82, 64, 70, 54)
    for i, sy in enumerate(SRC_Y):
        y = sy - CHIP_H / 2
        p.add(p.glass(SRC_X, y, SRC_W, CHIP_H, r=18))
        p.add(_column_glyph(p, SRC_X + 32, sy, 'amber' if i % 2 else 'tango'))
        p.add(_bar(p, SRC_X + 56, sy - 9, widths[i], 7, 0.24))
        p.add(_bar(p, SRC_X + 56, sy + 4, widths[i] - 24, 6, 0.12))
        p.add(p.node(SRC_X + SRC_W, sy, 4.2, 'coral' if i == BAD else 'tango'))

    # Target field chips.
    for i, ty in enumerate(TGT_Y):
        y = ty - CHIP_H / 2
        if i == BAD:   # empty, waiting slot
            p.add(f'<rect x="{TGT_X}" y="{fmt(y)}" width="{TGT_W}" height="{CHIP_H}" rx="18" fill="none" '
                  f'stroke="{p.col("coral")}" stroke-opacity="{0.5 if p.dark else 0.48}" stroke-width="1.6" '
                  f'stroke-dasharray="5 7"/>')
            p.add(_bar(p, TGT_X + 56, ty - 4, 80, 7, 0.16, 'coral'))
            continue
        p.add(p.glass(TGT_X, y, TGT_W, CHIP_H, r=18))
        p.add(p.node(TGT_X, ty, 4.2, 'tango'))
        p.add(_field_glyph(p, TGT_X + 38, ty, ROW_COLOURS[i][1]))
        p.add(_bar(p, TGT_X + 62, ty - 9, (70, 82, 64, 76, 0, 60)[i], 7, 0.24))
        p.add(_bar(p, TGT_X + 62, ty + 4, 44, 6, 0.12))
        p.add(p.glyph('check', TGT_X + TGT_W - 24, ty, 20, 'tango'))

    # The rejected row lands on a cross.
    cx, cy = CROSS
    p.add(p.circle(cx, cy, 36, fill='coral', opacity=0.16 if not p.dark else 0.22))
    p.add(p.ring(cx, cy, 27, 'coral', width=1.4, opacity=0.75, dash='3 5'))
    p.add(p.glyph('cross', cx, cy, 30, 'coral'))

    # The validation gate: a glass lens holding the shield orb.
    lens = 98
    p.add(p.glass(gx - lens, gy - lens, 2 * lens, 2 * lens, r=lens, tint='#FFE2CF' if not p.dark else None))
    grad = p.linear_gradient([(0, 'amber', 1), (0.5, 'tango', 1), (1, 'coral', 1)],
                             gx - 110, gy - 110, gx + 110, gy + 110)
    rr = lens + 10
    p.add(f'<circle cx="{gx}" cy="{gy}" r="{rr}" fill="none" stroke="{grad}" stroke-width="12" '
          f'stroke-opacity="{0.4 if not p.dark else 0.55}" filter="{p.glow_filter(10)}"/>')
    p.add(f'<circle cx="{gx}" cy="{gy}" r="{rr}" fill="none" stroke="{grad}" stroke-width="3.2"/>')
    p.add(f'<path d="{arc_d(gx, gy, rr, 200, 300)}" fill="none" stroke="#FFFFFF" stroke-width="1.3" '
          f'stroke-opacity="0.85" stroke-linecap="round"/>')
    p.add(p.orb(gx, gy, ORB_R, 'tango', highlight=False))
    p.add(_specular(gx, gy, ORB_R))
    k = 1.85
    p.add(f'<path d="{_shield_d(gx, gy + 1, k)}" fill="#FFFFFF" fill-opacity="0.96"/>')
    p.add(f'<path d="M{fmt(gx - 10)},{fmt(gy + 2)}l7,7l14,-15" fill="none" stroke="{p.col("tango_deep")}" '
          f'stroke-width="4.6" stroke-linecap="round" stroke-linejoin="round"/>')

    # Sparkles.
    for _ in range(70):
        x = rng.uniform(1000, W - 30)
        y = rng.uniform(40, H - 40)
        p.add(p.dot(x, y, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
