"""Home · Dashboard — the migration command centre.

A glossy Tango orb sits at the centre of four tilted orbits. Each orbit carries
one glass card for a guided step (source/target, map & validate, load, test),
and a luminous progress ribbon spirals outward through them. Two KPI cards with
mini charts float at the edges of the scene.
"""
import math

from common import W, H, cubic, fmt, lerp, smooth_d

SLUG = 'dashboard'
NUMBER = 0
WORD = 'DASHBOARD'
SEED = 5

C = (1440.0, 520.0)          # centre of the command centre
TILT = -12.0                 # orbit tilt, degrees
SQUASH = 0.60                # orbit ry / rx
ORBITS = (205.0, 275.0, 345.0, 415.0)
CARD_W, CARD_H = 150, 96
# (orbit index, angle on orbit in degrees, glyph, colour, progress 0..1)
STEPS = [
    (0, 196, 'table', 'amber', 1.0),
    (1, 266, 'shield', 'tango', 1.0),
    (2, 356, 'cloud', 'coral', 0.62),
    (3, 84, 'check', 'tango', 0.0),
]
ACTIVE = 2


def _orbit_point(r, angle):
    a = math.radians(angle)
    x, y = r * math.cos(a), r * SQUASH * math.sin(a)
    t = math.radians(TILT)
    return (C[0] + x * math.cos(t) - y * math.sin(t), C[1] + x * math.sin(t) + y * math.cos(t))


def _orbit_d(r, a0=0, a1=360, steps=90):
    pts = [_orbit_point(r, lerp(a0, a1, i / steps)) for i in range(steps + 1)]
    return 'M' + 'L'.join(f"{fmt(x)},{fmt(y)}" for x, y in pts)


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


def _kpi_line(p, x, y, w, h):
    """KPI card with a glowing sparkline and a soft area fill."""
    p.add(p.glass(x, y, w, h, r=24))
    p.add(p.dot(x + 28, y + 30, 5, 0.95, 'amber'))
    p.add(_bar(p, x + 44, y + 25, 74, 9, 0.30))
    p.add(_bar(p, x + w - 72, y + 22, 46, 14, 0.85, 'tango'))
    vals = [0.30, 0.42, 0.36, 0.55, 0.50, 0.68, 0.62, 0.80, 0.92]
    x0, x1, yb, yt = x + 26, x + w - 26, y + h - 24, y + 62
    pts = [(lerp(x0, x1, i / (len(vals) - 1)), lerp(yb, yt, v)) for i, v in enumerate(vals)]
    d = smooth_d(pts)
    area = p.linear_gradient([(0, 'tango', 0.34 if not p.dark else 0.42), (1, 'tango', 0)], 0, yt, 0, yb)
    p.add(f'<path d="{d}L{fmt(x1)},{fmt(yb)}L{fmt(x0)},{fmt(yb)}Z" fill="{area}"/>')
    p.add(p.glow_path(d, 'tango', width=2.6, glow=6, glow_opacity=0.5))
    ex, ey = pts[-1]
    p.add(p.circle(ex, ey, 9, 0.22, fill='amber'))
    p.add(p.dot(ex, ey, 4.2, 1.0, 'amber'))


def _kpi_bars(p, x, y, w, h):
    """KPI card with a progress gauge and a small bar chart."""
    p.add(p.glass(x, y, w, h, r=24))
    gx, gy, gr = x + 58, y + h / 2, 32
    p.add(p.ring(gx, gy, gr, 'ink', width=7, opacity=0.08))
    frac = 0.78
    a0, a1 = -90, -90 + 360 * frac
    x0, y0 = gx + gr * math.cos(math.radians(a0)), gy + gr * math.sin(math.radians(a0))
    x1, y1 = gx + gr * math.cos(math.radians(a1)), gy + gr * math.sin(math.radians(a1))
    grad = p.linear_gradient([(0, 'amber', 1), (1, 'tango', 1)], gx - gr, gy - gr, gx + gr, gy + gr)
    arc = f"M{fmt(x0)},{fmt(y0)}A{gr},{gr} 0 1 1 {fmt(x1)},{fmt(y1)}"
    p.add(f'<path d="{arc}" fill="none" stroke="{grad}" stroke-width="7" stroke-linecap="round"/>')
    p.add(p.text(gx, gy + 5, '78%', size=14, opacity=0.8, color='ink', anchor='middle', spacing=0.2, weight=700))
    bx, base = x + 118, y + h - 26
    for i, hv in enumerate((0.35, 0.55, 0.45, 0.72, 0.62, 0.9)):
        bh = hv * (h - 58)
        colour = 'tango' if i == 5 else ('amber' if i % 2 else 'coral')
        p.add(f'<rect x="{fmt(bx + i * 18)}" y="{fmt(base - bh)}" width="10" height="{fmt(bh)}" rx="5" '
              f'fill="{p.col(colour)}" fill-opacity="{fmt(0.95 if i == 5 else 0.55)}"/>')
    p.add(_bar(p, x + 118, y + 22, 64, 8, 0.25))


def _round_rect_d(x, y, w, h, r):
    return (f"M{fmt(x + r)},{fmt(y)}H{fmt(x + w - r)}A{r},{r} 0 0 1 {fmt(x + w)},{fmt(y + r)}"
            f"V{fmt(y + h - r)}A{r},{r} 0 0 1 {fmt(x + w - r)},{fmt(y + h)}H{fmt(x + r)}"
            f"A{r},{r} 0 0 1 {fmt(x)},{fmt(y + h - r)}V{fmt(y + r)}A{r},{r} 0 0 1 {fmt(x + r)},{fmt(y)}Z")


def draw(p):
    rng = p.rng
    cx, cy = C

    p.set_aurora([
        (1440, 520, 600, 480, 'tango', 0.50),
        (1900, 140, 520, 380, 'amber' if not p.dark else 'tango_soft', 0.50 if not p.dark else 0.40),
        (1760, 980, 560, 360, 'coral', 0.36 if not p.dark else 0.28),
        (1120, -40, 620, 300, 'peach', 0.55),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Decorative sweep across the top band.
    sweep = [(900, 96), (1180, 44), (1460, 80), (1720, 34), (1990, 64)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=1.8, opacity=0.65, glow=12, glow_opacity=0.4))
    p.add(p.glow_path(smooth_d([(x, y + 24) for x, y in sweep]), 'tango', width=1.1, opacity=0.45,
                      glow=8, glow_opacity=0.28))

    # Orbits: dashed ellipses; the outermost carries a lit comet segment riding it.
    for i, r in enumerate(ORBITS):
        p.add(p.path(_orbit_d(r), opacity=max(0.30, 0.46 - i * 0.06), width=1.4, color='tango',
                     stroke_dasharray='2 9'))
    lit_k = 0.6 if p.dark else 0.75
    a_tail, a_head, n = 206, 136, 7
    for k in range(n):
        f = (k + 1) / n                                  # 0 = tail .. 1 = head
        a0, a1 = lerp(a_tail, a_head, k / n), lerp(a_tail, a_head, (k + 1) / n)
        p.add(p.glow_path(_orbit_d(ORBITS[3], a0, a1, 10), 'amber', width=lerp(1.0, 2.2, f),
                          opacity=lit_k * lerp(0.12, 0.95, f), glow=8, glow_opacity=0.4 * f))
    hx_, hy_ = _orbit_point(ORBITS[3], a_head)
    p.add(p.circle(hx_, hy_, 9, 0.22 * lit_k, fill='amber'))
    p.add(p.dot(hx_, hy_, 3.6, 0.95, 'amber'))
    # small satellites riding the orbits
    for oi, ang, col in ((0, 40, 'coral'), (1, 140, 'amber'), (3, 250, 'tango')):
        sx, sy = _orbit_point(ORBITS[oi], ang)
        p.add(p.node(sx, sy, 5, col))

    centres = [_orbit_point(ORBITS[oi], ang) for oi, ang, *_ in STEPS]
    boxes = [(sx - CARD_W / 2, sy - CARD_H / 2) for sx, sy in centres]

    # Progress ribbon spiralling outward, card edge to card edge; every end tucks under a rim.
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = boxes
    T = 5      # tuck under the card rim
    k = 0.56   # quarter-ellipse handle length
    s1 = (x1 + CARD_W / 2, y1 + T)
    e1 = (x2 + T, y2 + CARD_H / 2)
    s2 = (x2 + CARD_W - T, y2 + CARD_H / 2)
    e2 = (x3 + T, y3 + CARD_H / 2)
    s3 = (x3 + CARD_W / 2, y3 + CARD_H - T)
    e3 = (x4 + CARD_W - T, y4 + CARD_H / 2)
    segs = [
        # orb -> step 1 (right edge)
        ((cx - 48, y1 + CARD_H / 2), (cx - 90, y1 + CARD_H / 2), (x1 + CARD_W + 30, y1 + CARD_H / 2),
         (x1 + CARD_W - T, y1 + CARD_H / 2), ('tango', 'amber'), True),
        # step 1 top -> step 2 left (a quarter arc rising and turning right)
        (s1, (s1[0], s1[1] - (s1[1] - e1[1]) * k), (e1[0] - (e1[0] - s1[0]) * k, e1[1]), e1,
         ('amber', 'tango'), True),
        # step 2 right -> step 3 left: a gentle arc that dips below the chord and enters from the side
        (s2, (lerp(s2[0], e2[0], 0.38), s2[1] + 70), (lerp(s2[0], e2[0], 0.72), e2[1] + 36), e2,
         ('tango', 'coral'), True),
        # step 3 bottom -> step 4 right (still to come)
        (s3, (s3[0], s3[1] + (e3[1] - s3[1]) * k), (e3[0] + (s3[0] - e3[0]) * k, e3[1]), e3,
         ('coral', 'coral'), False),
    ]
    for a, c1, c2, b, cols, done in segs:
        if done:
            p.add(_ribbon(p, a, c1, c2, b, width=11, colours=cols, opacity=0.64))
            p.add(p.particles_along(a, c1, c2, b, count=8, colour=cols[1], r=(1.6, 3.2)))
        else:
            d = (f"M{fmt(a[0])},{fmt(a[1])}C{fmt(c1[0])},{fmt(c1[1])} {fmt(c2[0])},{fmt(c2[1])} "
                 f"{fmt(b[0])},{fmt(b[1])}")
            p.add(p.glow_path(d, 'coral', width=2.2, opacity=0.75, glow=8, glow_opacity=0.35, dash='3 9'))

    # Central orb: halo rings, a lit arc, then the glossy sphere.
    p.add(p.ring(cx, cy, 116, 'tango', width=1.2, opacity=0.24, dash='1 6'))
    p.add(p.ring(cx, cy, 92, 'tango', width=1.3, opacity=0.36))
    p.add(p.glow_path(f"M{fmt(cx - 92)},{fmt(cy)}A92,92 0 0 1 {fmt(cx + 30)},{fmt(cy - 87)}", 'amber',
                      width=2.6, opacity=0.95, glow=8))
    p.add(p.dot(cx + 30, cy - 87, 4.5, 1.0, 'amber'))
    # Bloom and halo kept compact so the orb glows without glaring through the app's panels.
    bloom = p.radial_gradient([(0, '#FFFFFF' if not p.dark else 'amber', 0.41 if not p.dark else 0.35),
                               (0.5, 'tango_soft', 0.19 if not p.dark else 0.25), (1, 'tango', 0)])
    p.add(f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="120" fill="{bloom}"/>')
    halo = p.radial_gradient([(0, 'tango', 0.55 * p.val('glow_boost') * (0.75 if not p.dark else 1.0)),
                              (1, 'tango', 0)])
    p.add(f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="134" fill="{halo}"/>')
    p.add(p.orb(cx, cy, 56, 'tango', halo=False))

    # Step cards.
    for idx, ((oi, ang, glyph, colour, prog), (x, y)) in enumerate(zip(STEPS, boxes)):
        active = idx == ACTIVE
        pending = prog == 0
        tint = ('#FFC9A6' if not p.dark else '#FF8A3D') if active else None
        if active:
            p.add(p.glow_path(_round_rect_d(x - 5, y - 5, CARD_W + 10, CARD_H + 10, 26), 'tango',
                              width=1.6, opacity=0.9, glow=10, glow_opacity=0.6))
        p.add(p.glass(x, y, CARD_W, CARD_H, r=22, tint=tint))
        inner = [p.glyph(glyph, x + 40, y + 42, 36, colour),
                 _bar(p, x + 72, y + 30, 56, 7, 0.26), _bar(p, x + 72, y + 46, 38, 7, 0.13),
                 _bar(p, x + 20, y + CARD_H - 20, CARD_W - 40, 5, 0.10)]
        if prog > 0:
            g = p.linear_gradient([(0, 'amber', 1), (1, 'tango', 1)], x + 20, 0, x + CARD_W - 20, 0)
            inner.append(f'<rect x="{fmt(x + 20)}" y="{fmt(y + CARD_H - 20)}" width="{fmt((CARD_W - 40) * prog)}" '
                         f'height="5" rx="2.5" fill="{g}"/>')
        inner.append(p.text(x + CARD_W - 16, y + 24, f"0{idx + 1}", size=11, opacity=0.55, color='ink',
                            anchor='end', spacing=0.6, weight=700))
        p.group(inner, opacity='0.55' if pending else None)

    # KPI cards.
    _kpi_line(p, 1090, 114, 236, 146)
    _kpi_bars(p, 1600, 172, 250, 128)

    # Sparkles.
    for _ in range(70):
        x = rng.uniform(980, W - 30)
        y = rng.uniform(40, H - 40)
        p.add(p.dot(x, y, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
