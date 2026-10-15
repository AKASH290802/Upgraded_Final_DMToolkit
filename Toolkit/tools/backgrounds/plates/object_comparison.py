"""Object Comparison.

The same object read from two orgs: two mirrored glass object cards with field
rows. Rows that match are joined across the gap by thin glowing links; the rows
that differ light up in coral, and the main difference carries the focal orb.
A small compare orb balances the two cards from above.
"""
import math

from common import W, H, cubic_d, lerp, smooth_d, arc_d, fmt

SLUG = 'object_comparison'
NUMBER = 13
WORD = 'COMPARE'
SEED = 29

CARD_W, CARD_H = 318, 620
A = (1070, 250)          # left card (source org)
B = (1532, 250)          # right card (target org)
ROW0, ROW_STEP, ROWS = 456, 46, 8
DIFF = {1: 'main', 4: 'minor', 6: 'missing'}   # row index -> kind of difference


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


def _row_y(i):
    return ROW0 + i * ROW_STEP


def _card(p, x, y, mirrored, emblem):
    """A glass object card: header with emblem, three tab pills, then field rows."""
    out = p.glass(x, y, CARD_W, CARD_H, r=30, tint='#FFEADC' if (mirrored and not p.dark) else None)
    # header
    ex = x + CARD_W - 64 if mirrored else x + 64
    out += p.orb(ex, y + 66, 26, emblem, halo=False)
    out += p.glyph('table', ex, y + 66, 26, '#FFFFFF')
    bx = x + 28 if mirrored else x + 110
    out += _bar(p, bx + (0 if not mirrored else 60), y + 50, 120, 11, 0.5)
    out += _bar(p, bx + (0 if not mirrored else 100), y + 72, 80, 8, 0.2)
    # tabs: fields / picklists / record types (first active)
    tx = x + 28
    for k, w in enumerate((82, 82, 82)):
        tabx = tx + k * 90
        active = k == 0
        fill = p.col('tango') if active else p.col('ink')
        out += (f'<rect x="{fmt(tabx)}" y="{fmt(y + 118)}" width="{w}" height="26" rx="13" fill="{fill}" '
                f'fill-opacity="{0.9 if active else 0.07}"/>')
        out += _bar(p, tabx + 20, y + 128, 42, 6, 0.9 if active else 0.22, '#FFFFFF' if active else None)
    out += p.line(x + 24, y + 166, x + CARD_W - 24, y + 166, opacity=0.1, width=1, color=p.col('ink'))
    return out


def _row(p, x, i, mirrored, kind=None):
    """One field row. Mirrored cards put the value pill on the inner (gap) side."""
    y = _row_y(i)
    out = ''
    if kind in ('main', 'minor'):
        hl = p.linear_gradient([(0, 'coral', 0.0 if not mirrored else 0.32), (1, 'coral', 0.32 if not mirrored else 0.0)],
                               x + 14, y, x + CARD_W - 14, y)
        out += (f'<rect x="{fmt(x + 14)}" y="{fmt(y - 17)}" width="{CARD_W - 28}" height="34" rx="17" '
                f'fill="{hl}"/>')
        out += (f'<rect x="{fmt(x + 14)}" y="{fmt(y - 17)}" width="{CARD_W - 28}" height="34" rx="17" '
                f'fill="none" stroke="{p.col("coral")}" stroke-opacity="{0.55 if kind == "main" else 0.35}" '
                f'stroke-width="1.2"/>')
    if kind == 'missing' and not mirrored:
        # the field does not exist in this org: an empty dashed slot
        out += (f'<rect x="{fmt(x + 14)}" y="{fmt(y - 15)}" width="{CARD_W - 28}" height="30" rx="15" '
                f'fill="none" stroke="{p.col("coral")}" stroke-opacity="0.6" stroke-width="1.3" '
                f'stroke-dasharray="5 6"/>')
        return out
    dot_col = 'coral' if kind else ('tango' if i % 3 != 1 else 'amber')
    name_w = 128 - (i * 37) % 54
    pill_w = 54 if i % 2 else 66
    pill_col = 'coral' if kind else 'tango'
    if not mirrored:
        out += p.dot(x + 38, y, 5, 0.95, dot_col)
        out += _bar(p, x + 56, y - 4, name_w, 8, 0.24)
        out += _bar(p, x + CARD_W - 34 - pill_w, y - 6, pill_w, 12, 0.55 if kind else 0.3, pill_col)
    else:
        out += p.dot(x + CARD_W - 38, y, 5, 0.95, dot_col)
        out += _bar(p, x + CARD_W - 56 - name_w, y - 4, name_w, 8, 0.24)
        w = pill_w + (18 if kind == 'main' else 0)
        out += _bar(p, x + 34, y - 6, w, 12, 0.55 if kind else 0.3, pill_col)
    return out


def draw(p):
    rng = p.rng
    ax, ay = A
    bx, by = B
    gap_l, gap_r = ax + CARD_W, bx
    gcx = (gap_l + gap_r) / 2

    p.set_aurora([
        (1500, 520, 640, 520, 'tango', 0.55),
        (1880, 160, 480, 360, 'amber', 0.44 if not p.dark else 0.3),
        (gcx, _row_y(1), 340, 240, 'coral', 0.24 if not p.dark else 0.3),
        (1250, 1020, 640, 340, 'coral', 0.24),
        (1080, -60, 620, 280, 'peach', 0.55),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Star field.
    for _ in range(70):
        x = rng.uniform(1000, W - 24)
        y = rng.uniform(30, H - 30)
        p.add(p.dot(x, y, rng.uniform(0.7, 2.0), rng.uniform(0.15, 0.5), rng.choice(['tango', 'amber', 'coral'])))

    # Top-band sweep and the balance beam over both cards.
    sweep = [(900, 110), (1200, 64), (1500, 96), (1780, 52), (1990, 80)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=1.8, opacity=0.6, glow=12, glow_opacity=0.4))
    pivot = (gcx, 168)
    left_end = (ax + CARD_W / 2, ay - 2)
    right_end = (bx + CARD_W / 2, by - 2)
    for end, col in ((left_end, 'amber'), (right_end, 'tango')):
        c1 = (pivot[0] + (end[0] - pivot[0]) * 0.55, pivot[1] - 18)
        c2 = (end[0], pivot[1] + 10)
        p.add(p.glow_path(cubic_d(pivot, c1, c2, end), col, width=2.0, opacity=0.8, glow=9, glow_opacity=0.45))
        p.add(p.node(end[0], end[1], 5, col))
    p.add(p.ring(pivot[0], pivot[1], 38, 'tango', width=1.2, opacity=0.35, dash='2 7'))
    p.add(p.orb(pivot[0], pivot[1], 18, 'tango'))
    # compare glyph: two opposed arrows
    px, py = pivot
    p.add(f'<path d="M{fmt(px - 8)},{fmt(py - 4)}h14l-3.5,-3.5M{fmt(px + 8)},{fmt(py + 4)}h-14l3.5,3.5" fill="none" '
          f'stroke="#FFFFFF" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')

    # Links across the gap (drawn before cards so they tuck under the rims).
    for i in range(ROWS):
        y = _row_y(i)
        kind = DIFF.get(i)
        l, r = (gap_l - 30, y), (gap_r + 30, y)
        if kind is None:
            d = cubic_d(l, (gcx - 20, y), (gcx + 20, y), r)
            p.add(p.glow_path(d, 'tango' if (i % 2 or not p.dark) else 'amber', width=1.4, opacity=0.82, glow=6, glow_opacity=0.35))
        elif kind == 'main':
            p.add(p.ribbon(l, (gcx - 30, y - 4), (gcx + 30, y + 4), r, width=7, colours=('coral', 'coral'), opacity=0.7))
        else:
            d = cubic_d(l, (gcx - 20, y), (gcx + 20, y), r)
            p.add(p.glow_path(d, 'coral', width=1.6, opacity=0.8, glow=7, glow_opacity=0.45, dash='4 6'))

    # Cards.
    p.add(_card(p, ax, ay, False, 'amber'))
    p.add(_card(p, bx, by, True, 'tango'))
    for i in range(ROWS):
        p.add(_row(p, ax, i, False, DIFF.get(i)))
        p.add(_row(p, bx, i, True, DIFF.get(i)))

    # Link end nodes and the difference markers in the gap.
    for i in range(ROWS):
        y = _row_y(i)
        kind = DIFF.get(i)
        if kind is None:
            p.add(p.dot(gap_l, y, 3.2, 0.9, 'amber'))
            p.add(p.dot(gap_r, y, 3.2, 0.9, 'tango'))
        elif kind == 'main':
            p.add(p.ring(gcx, y, 36, 'coral', width=1.4, opacity=0.6))
            p.add(p.ring(gcx, y, 54, 'coral', width=1.0, opacity=0.3, dash='2 6'))
            p.add(p.orb(gcx, y, 20, 'coral'))
        else:
            p.add(p.orb(gcx, y, 8, 'coral', highlight=False))

    # Footer of each card: a match summary bar (mostly tango, a coral slice).
    for x in (ax, bx):
        fy = ay + CARD_H - 38
        p.add(_bar(p, x + 28, fy, CARD_W - 56, 8, 0.1))
        p.add(_bar(p, x + 28, fy, (CARD_W - 56) * 0.66, 8, 0.8, 'tango'))
        p.add(_bar(p, x + 28 + (CARD_W - 56) * 0.66 + 4, fy, (CARD_W - 56) * 0.14, 8, 0.85, 'coral'))

    for x, y, s, c in ((1440, 60, 10, 'amber'), (1890, 520, 8, 'coral'), (1020, 200, 7, 'tango'),
                       (1900, 930, 8, 'amber')):
        p.add(_sparkle(p, x, y, s, c))
