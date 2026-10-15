"""Step 1 · Source / Target Information.

Four glass source tiles (file, SQL Server, Salesforce, Oracle) send luminous
ribbons into one target object card, which glows in Tavant Tango.
"""
import math

from common import W, H, cubic, lerp, smooth_d, arc_d

SLUG = 'source_target'
NUMBER = 1
WORD = 'SOURCE / TARGET'
SEED = 11

TILE_W, TILE_H = 150, 104
TILES = [  # (x, y, glyph, ribbon colours)
    (1100, 150, 'file', ('amber', 'tango')),
    (1060, 330, 'database', ('tango', 'coral')),
    (1100, 510, 'cloud', ('coral', 'tango')),
    (1060, 690, 'table', ('amber', 'coral')),
]
TARGET = (1520, 330, 300, 330)   # x, y, w, h


def draw(p):
    rng = p.rng
    tx, ty, tw, th = TARGET
    target_in = (tx, ty + th / 2)

    p.set_aurora([
        (1640, 470, 620, 520, 'tango', 0.62),
        (1900, 120, 520, 380, 'amber', 0.48),
        (1250, 980, 640, 380, 'coral', 0.30),
        (1120, -40, 620, 300, 'peach', 0.55),
        (380, 1150, 900, 420, 'peach', 0.22),
    ])

    # Wide decorative sweep across the top band.
    sweep = [(860, 120), (1180, 60), (1500, 92), (1780, 40), (1990, 70)]
    p.add(p.glow_path(smooth_d(sweep), 'amber', width=2.0, opacity=0.7, glow=12, glow_opacity=0.45))
    sweep2 = [(x, y + 26) for x, y in sweep]
    p.add(p.glow_path(smooth_d(sweep2), 'tango', width=1.2, opacity=0.5, glow=8, glow_opacity=0.3))

    # Orbit rings behind the target.
    cx, cy = tx + tw / 2, ty + th / 2
    for i, r in enumerate((250, 320, 400)):
        p.add(p.ring(cx, cy, r, 'tango', width=1.2, opacity=0.28 - i * 0.06, dash='2 10'))
    p.add(p.glow_path(arc_d(cx, cy, 320, 200, 300), 'tango', width=2.2, opacity=0.85, glow=10))
    p.add(p.glow_path(arc_d(cx, cy, 400, 20, 80), 'amber', width=2.0, opacity=0.75, glow=10))

    # Ribbons from each source into the target, with particles.
    for i, (x, y, glyph, colours) in enumerate(TILES):
        start = (x + TILE_W, y + TILE_H / 2)
        end = (target_in[0] + 2, target_in[1] + (i - 1.5) * 34)
        c1 = (start[0] + 150, start[1])
        c2 = (end[0] - 170, end[1])
        p.add(p.ribbon(start, c1, c2, end, width=12 - abs(i - 1.5) * 1.5, colours=colours, opacity=0.62))
        p.add(p.particles_along(start, c1, c2, end, count=9, colour=colours[1], r=(1.8, 3.6)))

    # Source tiles.
    for x, y, glyph, colours in TILES:
        p.add(p.glass(x, y, TILE_W, TILE_H, r=22))
        p.add(p.glyph(glyph, x + 46, y + TILE_H / 2, 40, colours[0] if glyph != 'cloud' else 'tango'))
        # two small text-like bars
        for k, w in enumerate((62, 42)):
            p.add(f'<rect x="{x + 78}" y="{y + 38 + k * 16}" width="{w}" height="7" rx="3.5" '
                  f'fill="{p.col("ink")}" fill-opacity="{0.22 if k == 0 else 0.12}"/>')
        p.add(p.dot(x + TILE_W - 18, y + 18, 4, 0.9, 'tango'))

    # Target object card.
    p.add(p.glass(tx, ty, tw, th, r=30, tint='#FFE2CF' if not p.dark else None))
    p.add(p.orb(tx + 76, ty + 78, 34, 'tango'))
    p.add(f'<rect x="{tx + 128}" y="{ty + 58}" width="130" height="12" rx="6" fill="{p.col("ink")}" fill-opacity="0.55"/>')
    p.add(f'<rect x="{tx + 128}" y="{ty + 82}" width="88" height="9" rx="4.5" fill="{p.col("ink")}" fill-opacity="0.22"/>')
    for row in range(5):
        yy = ty + 140 + row * 34
        p.add(p.dot(tx + 40, yy + 4, 5, 0.9, 'tango' if row % 2 == 0 else 'amber'))
        p.add(f'<rect x="{tx + 58}" y="{yy}" width="{150 - (row % 3) * 26}" height="8" rx="4" '
              f'fill="{p.col("ink")}" fill-opacity="0.2"/>')
        p.add(f'<rect x="{tx + 222}" y="{yy}" width="46" height="8" rx="4" fill="{p.col("tango")}" fill-opacity="0.45"/>')
    p.add(p.glyph('check', tx + tw - 36, ty + th - 36, 34, 'tango'))

    # Sparkles around the scene.
    for _ in range(70):
        x = rng.uniform(980, W - 30)
        y = rng.uniform(40, H - 40)
        p.add(p.dot(x, y, rng.uniform(0.8, 2.4), rng.uniform(0.15, 0.55), rng.choice(['tango', 'amber', 'coral'])))
