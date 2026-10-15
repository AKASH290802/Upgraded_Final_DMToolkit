"""Step 3 · Data Operations (load).

A glass database tile launches batches of records, small stacks of glass
cards, along three rising ribbon arcs into one large glass cloud: the target
org. Where the arcs arrive a glossy orb flares on the cloud's rim, the landed
records line up inside it, and a glass progress card below counts the batches
loaded.
"""
import math

from common import W, H, cubic, fmt, lerp, smooth_d, arc_d, polar

SLUG = 'data_operations'
NUMBER = 5
WORD = 'LOAD'
SEED = 29

DB = (1040, 536, 176, 150)                 # source tile x, y, w, h
CLOUD_BASE, CLOUD_X = 452, 1508            # cloud baseline y, left x
CLOUD = [(1592, 382, 84), (1708, 314, 114), (1800, 378, 78)]   # bump circles (cx, cy, r)
ARRIVE = (1560, 392)                        # where the batches land
PROGRESS = (1566, 482, 274, 108)
ARCS = [  # control-point heights and colours; the three batch lanes
    (150, ('amber', 'tango')),
    (240, ('tango', 'amber')),
    (330, ('tango_soft', 'coral')),
]


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


def _cloud_d():
    """Outline of the cloud: three bump circles over a flat base, joined at their upper intersections."""
    def upper_cross(c1, c2):
        (x1, y1, r1), (x2, y2, r2) = c1, c2
        d = math.hypot(x2 - x1, y2 - y1)
        a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
        h = math.sqrt(max(0.0, r1 * r1 - a * a))
        mx, my = x1 + a * (x2 - x1) / d, y1 + a * (y2 - y1) / d
        pts = [(mx + h * (y2 - y1) / d, my - h * (x2 - x1) / d), (mx - h * (y2 - y1) / d, my + h * (x2 - x1) / d)]
        return min(pts, key=lambda q: q[1])

    def base_cross(c, side):
        x, y, r = c
        dx = math.sqrt(max(0.0, r * r - (CLOUD_BASE - y) ** 2))
        return (x - dx if side < 0 else x + dx, CLOUD_BASE)

    def arc_to(c, start, end):
        x, y, r = c
        a0 = math.atan2(start[1] - y, start[0] - x)
        a1 = math.atan2(end[1] - y, end[0] - x)
        span = (a1 - a0) % (2 * math.pi)
        return f"A{fmt(r)},{fmt(r)} 0 {1 if span > math.pi else 0} 1 {fmt(end[0])},{fmt(end[1])}"

    pts = [base_cross(CLOUD[0], -1)]
    for c1, c2 in zip(CLOUD, CLOUD[1:]):
        pts.append(upper_cross(c1, c2))
    pts.append(base_cross(CLOUD[-1], 1))
    d = f"M{fmt(pts[0][0])},{fmt(pts[0][1])}"
    for c, start, end in zip(CLOUD, pts, pts[1:]):
        d += arc_to(c, start, end)
    return d + 'Z'


def _glass_shape(p, d, x0, y0, x1, y1, tint=None):
    fo = p.val('glass_fill_opacity')
    if tint:
        fill = p.linear_gradient([(0, '#FFFFFF', fo + 0.12), (1, tint, fo * 0.9)], x0, y0, x1, y1)
        fo = 1
    else:
        fill = p.col('glass_fill')
    clip = 'cloudclip'
    p.define(f'<clipPath id="{clip}"><path d="{d}"/></clipPath>', clip)
    body = (f'<path d="{d}" fill="{fill}" fill-opacity="{fmt(fo)}" stroke="none" '
            f'filter="{p.shadow_filter()}"/>')
    # inner highlight: a wide white stroke clipped to the inside, so only its inner half shows
    inner = (f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-width="7" '
             f'stroke-opacity="{0.9 if not p.dark else 0.16}" clip-path="url(#{clip})"/>')
    # outer rim: an even edge all round, the flat base included
    if p.dark:
        edge = f'stroke="#FFFFFF" stroke-opacity="0.26"'
    else:
        edge = f'stroke="{p.col("tango")}" stroke-opacity="0.34"'
    rim = f'<path d="{d}" fill="none" {edge} stroke-width="1.4" stroke-linejoin="round"/>'
    return body + inner + rim


def _record_stack(p, x, y, angle, colour, n=3):
    """A batch in flight: a small stack of glass record cards, tilted along its path."""
    w, h = 56, 38
    out = []
    front = '#2A2027' if p.dark else '#FFFFFF'
    for k in reversed(range(n)):
        ox, oy = -k * 7, k * 6
        fill, fo = (front, 0.92 if p.dark else 0.86) if k == 0 else ('#FFFFFF', 0.10 if p.dark else 0.45)
        out.append(f'<rect x="{fmt(-w / 2 + ox)}" y="{fmt(-h / 2 + oy)}" width="{w}" height="{h}" rx="9" '
                   f'fill="{fill}" fill-opacity="{fmt(fo)}" stroke="#FFFFFF" '
                   f'stroke-opacity="{fmt((0.5 if p.dark else 0.95) * (1 - k * 0.25))}" stroke-width="1.2"/>')
    out.append(p.dot(-w / 2 + 13, -3, 4.6, 0.95, colour))
    out.append(_bar(p, -w / 2 + 23, -8, 22, 5.5, 0.34))
    out.append(_bar(p, -w / 2 + 23, 2, 14, 5, 0.16))
    p.add(f'<g filter="{p.shadow_filter()}"><g transform="translate({fmt(x)} {fmt(y)}) rotate({fmt(angle)})">'
          + ''.join(out) + '</g></g>')


def draw(p):
    rng = p.rng
    _filters(p)
    ax, ay = ARRIVE
    dx, dy, dw, dh = DB

    p.set_aurora([
        (1680, 330, 600, 420, 'tango', 0.62),
        (1900, 90, 480, 320, 'amber', 0.50),
        (1180, 820, 520, 340, 'coral', 0.30),
        (1120, -40, 620, 300, 'peach', 0.55),
        (1760, 900, 520, 320, 'amber', 0.26),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Top-band sweep, the family signature.
    sweep = [(860, 110), (1160, 62), (1440, 90), (1720, 36), (1990, 64)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=2.0, opacity=0.7, glow=12, glow_opacity=0.45))
    p.add(p.glow_path(smooth_d([(x, y + 24) for x, y in sweep]), 'tango', width=1.2, opacity=0.5,
                      glow=8, glow_opacity=0.3))

    # Ripple rings spreading from the arrival point.
    for i, r in enumerate((70, 130, 210, 300)):
        p.add(p.ring(ax, ay, r, 'tango', width=1.2, opacity=0.30 - i * 0.06, dash='2 10'))

    # Launch lanes: rising ribbon arcs from the database into the cloud.
    launch = (dx + dw / 2 + 30, dy)
    lanes = []
    for i, (peak, colours) in enumerate(ARCS):
        p0 = (launch[0] + (i - 1) * 38, launch[1])
        p3 = (ax - 10, ay + (i - 1) * 15)
        p1 = (p0[0] + 60 + i * 40, peak)
        p2 = (p3[0] - 230 + i * 40, peak - 40 + i * 30)
        lanes.append((p0, p1, p2, p3, colours))
        p.add(p.ribbon(p0, p1, p2, p3, width=12.5 - abs(i - 1) * 2.5, colours=colours, opacity=0.62))
        p.add(p.particles_along(p0, p1, p2, p3, count=12, colour=colours[1], r=(1.6, 3.4), start=0.12))

    # The target: one large glass cloud.
    d = _cloud_d()
    p.add(_glass_shape(p, d, CLOUD_X, 190, 1920, CLOUD_BASE, tint='#FFE2CF' if not p.dark else None))
    # landed records, lined up inside the cloud
    for row in range(3):
        yy = 348 + row * 30
        p.add(p.dot(1640, yy + 4, 5, 0.9, 'tango' if row != 1 else 'amber'))
        p.add(_bar(p, 1656, yy, (120, 96, 138)[row], 8, 0.22))
        p.add(_bar(p, 1808, yy, 34, 8, 0.45, 'tango'))
    p.add(p.glyph('cloud', 1712, 272, 46, 'tango'))
    p.add(_bar(p, 1680, 306, 64, 7, 0.26))

    # Batches in flight along each lane (the lowest lane carries the batch about to land).
    for i, (p0, p1, p2, p3, colours) in enumerate(lanes):
        for t in ((0.34, 0.66), (0.5,), (0.28, 0.78))[i]:
            x, y = cubic(p0, p1, p2, p3, t)
            x2, y2 = cubic(p0, p1, p2, p3, min(1, t + 0.01))
            angle = math.degrees(math.atan2(y2 - y, x2 - x)) * 0.35
            _record_stack(p, x, y, angle, colours[0])

    # The source database tile.
    p.add(p.glass(dx, dy, dw, dh, r=26))
    p.add(p.glyph('database', dx + 54, dy + 62, 58, 'tango'))
    p.add(_bar(p, dx + 96, dy + 44, 56, 8, 0.30))
    p.add(_bar(p, dx + 96, dy + 60, 38, 7, 0.14))
    for k in range(4):
        p.add(_bar(p, dx + 26 + k * 32, dy + 112, 24, 12, 0.55 if k < 3 else 0.18, 'tango' if k % 2 == 0 else 'amber'))
    for p0, _, _, _, colours in lanes:
        p.add(p.node(p0[0], p0[1], 4.2, colours[0]))

    # Batch progress card.
    x, y, w, h = PROGRESS
    p.add(p.glass(x, y, w, h, r=24))
    p.add(p.glyph('chart', x + 40, y + 40, 30, 'tango'))
    p.add(_bar(p, x + 70, y + 28, 100, 8, 0.30))
    p.add(_bar(p, x + 70, y + 44, 64, 7, 0.14))
    p.add(p.text(x + w - 24, y + 46, '75%', size=20, opacity=0.9, anchor='end', spacing=0.4,
                 color='tango', weight=700))
    seg_w, gap, segs = 23.75, 5, 8
    grad = p.linear_gradient([(0, 'amber', 1), (1, 'tango', 1)], x + 24, 0, x + 24 + 6 * (seg_w + gap), 0)
    for k in range(segs):
        sx = x + 24 + k * (seg_w + gap)
        filled = k < 6
        p.add(f'<rect x="{fmt(sx)}" y="{fmt(y + 72)}" width="{fmt(seg_w)}" height="14" rx="7" '
              f'fill="{grad if filled else p.col("ink")}" fill-opacity="{1 if filled else 0.1}"/>')
    p.add(f'<rect x="{fmt(x + 24 + 6 * (seg_w + gap))}" y="{fmt(y + 72)}" width="{fmt(seg_w)}" height="14" rx="7" '
          f'fill="none" stroke="{p.col("tango")}" stroke-width="1.6" stroke-dasharray="3 3"/>')

    # The arrival: a glossy orb flaring on the cloud's rim.
    p.add(p.ring(ax, ay, 46, 'tango', width=1.6, opacity=0.75))
    p.add(p.ring(ax, ay, 60, 'amber', width=1.2, opacity=0.55, dash='3 6'))
    p.add(p.glow_path(arc_d(ax, ay, 60, 96, 150), 'amber', width=2.2, opacity=0.85, glow=10))
    p.add(p.orb(ax, ay, 33, 'tango'))
    p.add(p.glyph('check', ax + 38, ay - 38, 22, 'tango'))

    # Sparkles.
    for _ in range(70):
        x = rng.uniform(1000, W - 30)
        y = rng.uniform(40, H - 40)
        p.add(p.dot(x, y, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
