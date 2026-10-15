"""Logs & Reports.

A floating dashboard of glass cards: a large line chart whose glowing curve
climbs to a peak over a gradient area fill, a donut of outcomes, a bar chart of
volumes and a log list with status dots, where one error row flares coral.
The chart peak is the focal point.
"""
import math

from common import W, H, lerp, smooth_d, arc_d, fmt, polar

SLUG = 'logs_reports'
NUMBER = 14
WORD = 'REPORTS'
SEED = 31

LINE_CARD = (1040, 150, 560, 340)
DONUT_CARD = (1630, 150, 220, 250)
BAR_CARD = (1040, 522, 300, 290)
LOG_CARD = (1370, 522, 480, 290)


def _bar(p, x, y, w, h=8, opacity=0.2, colour=None):
    c = p._c(colour) if colour else p.col('ink')
    return (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(h / 2)}" '
            f'fill="{c}" fill-opacity="{fmt(opacity)}"/>')


def _sparkle(p, cx, cy, s, colour='amber', opacity=0.9):
    c = p._c(colour)
    k = s * 0.22
    d = (f"M{fmt(cx)},{fmt(cy - s)}Q{fmt(cx + k)},{fmt(cy - k)} {fmt(cx + s)},{fmt(cy)}"
         f"Q{fmt(cx + k)},{fmt(cy + k)} {fmt(cx)},{fmt(cy + s)}Q{fmt(cx - k)},{fmt(cy + k)} {fmt(cx - s)},{fmt(cy)}"
         f"Q{fmt(cx - k)},{fmt(cy - k)} {fmt(cx)},{fmt(cy - s)}Z")
    halo = p.radial_gradient([(0, c, 0.5 * p.val('glow_boost')), (1, c, 0)])
    return (f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(s * 1.6)}" fill="{halo}"/>'
            f'<path d="{d}" fill="{c}" fill-opacity="{fmt(opacity)}"/>'
            f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(s * 0.14)}" fill="#FFFFFF" fill-opacity="0.95"/>')


def _header(p, x, y, glyph, colour, bar_w=110):
    """Card header: a small glyph in a tinted chip, and two text-like bars."""
    out = (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="40" height="40" rx="12" fill="{p._c(colour)}" '
           f'fill-opacity="{0.16 if not p.dark else 0.22}"/>')
    if glyph == 'spark':   # a tiny rising line with a peak dot
        c = p._c(colour)
        out += (f'<path d="M{fmt(x + 9)},{fmt(y + 27)}l7,-6l6,4l9,-11" fill="none" stroke="{c}" stroke-width="2.6" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')
        out += p.dot(x + 31, y + 14, 3.4, 1, colour)
    else:
        out += p.glyph(glyph, x + 20, y + 20, 24, colour)
    out += _bar(p, x + 54, y + 8, bar_w, 9, 0.45)
    out += _bar(p, x + 54, y + 25, bar_w * 0.6, 7, 0.18)
    return out


def _line_chart(p, rng):
    x, y, w, h = LINE_CARD
    out = p.glass(x, y, w, h, r=30, tint='#FFE6D4' if not p.dark else None)
    out += _header(p, x + 28, y + 26, 'spark', 'tango', 130)
    # range pills, top right
    for k in range(3):
        px = x + w - 28 - (3 - k) * 58
        active = k == 1
        out += (f'<rect x="{fmt(px)}" y="{fmt(y + 32)}" width="50" height="24" rx="12" '
                f'fill="{p.col("tango") if active else p.col("ink")}" fill-opacity="{0.9 if active else 0.07}"/>')
        out += _bar(p, px + 14, y + 41, 22, 6, 0.9 if active else 0.22, '#FFFFFF' if active else None)
    # plot area
    x0, x1 = x + 36, x + w - 36
    top, base = y + 112, y + h - 44
    for k in range(4):
        gy = lerp(top, base, k / 3)
        out += (f'<path d="M{fmt(x0)},{fmt(gy)}H{fmt(x1)}" stroke="{p.col("ink")}" stroke-opacity="0.08" '
                f'stroke-width="1" stroke-dasharray="{"" if k == 3 else "3 6"}"/>')
    # data: a gentle climb to a peak, then a soft settle
    values = [0.28, 0.34, 0.3, 0.42, 0.4, 0.52, 0.5, 0.63, 0.7, 0.92, 0.74, 0.7, 0.78]
    peak_i = values.index(max(values))
    pts = [(lerp(x0, x1, i / (len(values) - 1)), lerp(base, top, v)) for i, v in enumerate(values)]
    d = smooth_d(pts, tension=0.55)
    area = d + f"L{fmt(pts[-1][0])},{fmt(base)}L{fmt(pts[0][0])},{fmt(base)}Z"
    fill = p.linear_gradient([(0, 'tango', 0.62 if not p.dark else 0.55), (0.6, 'amber', 0.2), (1, 'amber', 0)],
                             0, top, 0, base)
    out += f'<path d="{area}" fill="{fill}"/>'
    stroke = p.linear_gradient([(0, 'amber', 1), (0.7, 'tango', 1), (1, 'coral', 1)], x0, 0, x1, 0)
    out += (f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="10" stroke-opacity="'
            f'{fmt(0.4 * p.val("glow_boost"))}" stroke-linecap="round" filter="{p.glow_filter(9)}"/>')
    out += (f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="3.4" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')
    out += f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-width="1.1" stroke-opacity="0.85"/>'
    for i, (px, py) in enumerate(pts):
        if i % 2 == 1 and i != peak_i:
            out += p.dot(px, py, 3.4, 0.95, 'tango')
            out += p.dot(px, py, 1.4, 1, '#FFFFFF')
    return out, pts[peak_i], (top, base)


def _donut(p):
    x, y, w, h = DONUT_CARD
    out = p.glass(x, y, w, h, r=28)
    cx, cy, r = x + w / 2, y + 112, 58
    out += p.ring(cx, cy, r, p.col('ink'), width=18, opacity=0.06)
    # one soft halo for the whole ring (a full circle keeps the blur region generous)
    out += (f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="none" stroke="{p.col("tango")}" '
            f'stroke-width="30" stroke-opacity="{fmt(0.22 * p.val("glow_boost"))}" filter="{p.glow_filter(10)}"/>')
    a = -90
    for share, colour in ((0.58, 'tango'), (0.24, 'amber'), (0.07, 'coral')):
        a1 = a + share * 360
        seg = arc_d(cx, cy, r, a + 4, a1 - 4)
        out += (f'<path d="{seg}" fill="none" stroke="{p._c(colour)}" stroke-width="16" stroke-linecap="round" '
                f'stroke-opacity="0.95"/>')
        out += (f'<path d="{seg}" fill="none" stroke="#FFFFFF" stroke-width="1.2" stroke-linecap="round" '
                f'stroke-opacity="0.7"/>')
        a = a1
    out += p.ring(cx, cy, r - 18, p.col('ink'), width=1, opacity=0.08)
    out += _bar(p, cx - 26, cy - 8, 52, 10, 0.5)
    out += _bar(p, cx - 17, cy + 8, 34, 7, 0.2)
    # legend
    for k, colour in enumerate(('tango', 'amber', 'coral')):
        ly = y + 202 + k * 0
        lx = x + 30 + k * 60
        out += p.dot(lx, ly, 5, 0.95, colour)
        out += _bar(p, lx + 10, ly - 3.5, 30, 7, 0.2)
    return out


def _bars(p):
    x, y, w, h = BAR_CARD
    out = p.glass(x, y, w, h, r=28)
    out += _header(p, x + 26, y + 24, 'chart', 'amber', 96)
    base = y + h - 36
    heights = [0.42, 0.58, 0.5, 0.74, 0.62, 0.86, 0.68]
    bw, gap = 22, 13
    x0 = x + 34
    for i, v in enumerate(heights):
        bh = v * 130
        bx = x0 + i * (bw + gap)
        grad = (p.linear_gradient([(0, 'tango', 1), (1, 'amber', 0.75)], 0, base - bh, 0, base) if not p.dark else
                p.linear_gradient([(0, 'amber', 1), (0.45, 'tango', 0.9), (1, 'tango', 0.35)], 0, base - bh, 0, base))
        out += (f'<rect x="{fmt(bx)}" y="{fmt(base - bh)}" width="{bw}" height="{fmt(bh)}" rx="7" fill="{grad}" '
                f'fill-opacity="{0.95 if i == 5 else 0.72}"/>')
        out += (f'<rect x="{fmt(bx + 4)}" y="{fmt(base - bh + 4)}" width="4" height="{fmt(bh * 0.5)}" rx="2" '
                f'fill="#FFFFFF" fill-opacity="0.35"/>')
    out += (f'<path d="M{fmt(x + 26)},{fmt(base + 1)}H{fmt(x + w - 26)}" stroke="{p.col("ink")}" '
            f'stroke-opacity="0.12" stroke-width="1.2"/>')
    return out


def _logs(p):
    x, y, w, h = LOG_CARD
    out = ''
    out += p.glass(x, y, w, h, r=30)
    out += _header(p, x + 28, y + 26, 'file', 'tango', 120)
    # status filter chips
    for k, colour in enumerate(('tango', 'amber', 'coral')):
        cx = x + w - 150 + k * 44
        out += (f'<rect x="{fmt(cx)}" y="{fmt(y + 34)}" width="36" height="22" rx="11" fill="{p._c(colour)}" '
                f'fill-opacity="{0.16 if not p.dark else 0.24}"/>')
        out += p.dot(cx + 18, y + 45, 4, 0.95, colour)
    rows = ['ok', 'ok', 'warn', 'error', 'ok', 'ok']
    for i, status in enumerate(rows):
        ry = y + 100 + i * 34
        if status == 'error':
            hl = p.linear_gradient([(0, 'coral', 0.34), (1, 'coral', 0.04)], x + 16, 0, x + w - 16, 0)
            out += (f'<rect x="{fmt(x + 16)}" y="{fmt(ry - 15)}" width="{w - 32}" height="30" rx="15" fill="{hl}" '
                    f'stroke="{p.col("coral")}" stroke-opacity="0.5" stroke-width="1.1"/>')
            out += p.glyph('cross', x + 40, ry, 20, 'coral')
        else:
            colour = 'tango' if status == 'ok' else 'amber'
            out += p.circle(x + 40, ry, 9, opacity=0.18, fill=colour)
            out += p.dot(x + 40, ry, 4.5, 0.95, colour)
        name_w = 170 - (i * 41) % 70
        out += _bar(p, x + 64, ry - 4, name_w, 8, 0.3 if status == 'error' else 0.2)
        out += _bar(p, x + 64 + name_w + 14, ry - 4, 60 - (i % 3) * 12, 8, 0.1)
        out += _bar(p, x + w - 92, ry - 4, 60, 8, 0.45 if status == 'error' else 0.14,
                    'coral' if status == 'error' else None)
        if i < len(rows) - 1:
            out += (f'<path d="M{fmt(x + 64)},{fmt(ry + 17)}H{fmt(x + w - 28)}" stroke="{p.col("ink")}" '
                    f'stroke-opacity="0.06" stroke-width="1"/>')
    return out


def draw(p):
    rng = p.rng
    p.set_aurora([
        (1360, 330, 620, 420, 'tango', 0.6),
        (1880, 120, 480, 340, 'amber', 0.44 if not p.dark else 0.3),
        (1760, 760, 520, 420, 'coral', 0.32),
        (1200, 1000, 620, 320, 'peach', 0.42),
        (1060, -60, 620, 280, 'peach', 0.55),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    for _ in range(70):
        x = rng.uniform(1000, W - 24)
        y = rng.uniform(30, H - 30)
        p.add(p.dot(x, y, rng.uniform(0.7, 2.0), rng.uniform(0.15, 0.5), rng.choice(['tango', 'amber', 'coral'])))

    # Top-band sweep.
    sweep = [(880, 96), (1180, 58), (1480, 86), (1760, 44), (1990, 70)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=1.8, opacity=0.62, glow=12, glow_opacity=0.4))
    p.add(p.glow_path(smooth_d([(x, y + 24) for x, y in sweep]), 'tango', width=1.1, opacity=0.45, glow=8,
                      glow_opacity=0.28))

    chart, peak, (top, base) = _line_chart(p, rng)
    p.add(chart)
    p.add(_donut(p))
    p.add(_bars(p))
    p.add(_logs(p))

    # The peak: drop line, halo rings, orb and a tiny value bubble.
    px, py = peak
    p.add(f'<path d="M{fmt(px)},{fmt(py + 16)}V{fmt(base)}" stroke="{p.col("tango")}" stroke-opacity="0.55" '
          f'stroke-width="1.4" stroke-dasharray="3 5"/>')
    bloom = p.radial_gradient([(0, 'tango', 0.42 * p.val('glow_boost')), (0.5, 'amber', 0.14), (1, 'amber', 0)])
    p.add(f'<circle cx="{fmt(px)}" cy="{fmt(py)}" r="86" fill="{bloom}"/>')
    p.add(p.ring(px, py, 26, 'tango', width=1.4, opacity=0.55))
    p.add(p.ring(px, py, 42, 'amber', width=1.0, opacity=0.3, dash='2 6'))
    p.add(p.orb(px, py, 15, 'tango'))
    bw, bh = 76, 34
    bx, by = px - bw - 34, py - 48
    if p.dark:
        p.add(f'<rect x="{fmt(bx)}" y="{fmt(by)}" width="{bw}" height="{bh}" rx="17" fill="#241A1C" fill-opacity="0.8"/>')
    p.add(p.glass(bx, by, bw, bh, r=17, tint='#FFE6D4' if not p.dark else None))
    p.add(p.text(bx + bw / 2, by + 23, '98.6%', size=15, opacity=0.9, anchor='middle', spacing=0.4, color=p.col('ink'),
                 weight=700))

    for x, y, s, c in ((1610, 90, 10, 'amber'), (1880, 470, 8, 'coral'), (1010, 440, 7, 'tango'),
                       (1880, 900, 8, 'amber')):
        p.add(_sparkle(p, x, y, s, c))
