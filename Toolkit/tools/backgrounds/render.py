"""
Render the Signal Cartography plates.

    .venv\\Scripts\\python.exe tools\\backgrounds\\render.py            # all plates
    .venv\\Scripts\\python.exe tools\\backgrounds\\render.py data_loading mapping
    .venv\\Scripts\\python.exe tools\\backgrounds\\render.py --preview-dir <dir>   # also keep full PNGs

For each plates/<slug>.py it writes
    assets/backgrounds/src/<slug>.svg   vector source
    assets/backgrounds/<slug>.webp      what the app shows (1920 x 1080)
and finally assets/backgrounds/contact_sheet.png (all plates, for review).

Rasterising uses headless Chrome or Edge (already installed on the machine).
"""

import argparse
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PLATES_DIR = os.path.join(HERE, 'plates')
OUT_DIR = os.path.join(ROOT, 'assets', 'backgrounds')
SRC_DIR = os.path.join(OUT_DIR, 'src')
sys.path.insert(0, HERE)

import common  # noqa: E402

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
WEBP_QUALITY = 84


def find_browser() -> str:
    for path in BROWSERS:
        if os.path.exists(path):
            return path
    found = shutil.which('chrome') or shutil.which('msedge')
    if not found:
        raise SystemExit("Chrome or Edge is needed to rasterise the plates.")
    return found


def load_plate(slug: str):
    spec = importlib.util.spec_from_file_location(f"plate_{slug}", os.path.join(PLATES_DIR, f"{slug}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODES = ('light', 'dark')


def build_svg(module, mode: str = 'light') -> str:
    plate = common.Plate(module.NUMBER, module.WORD, seed=getattr(module, 'SEED', 7), mode=mode)
    module.draw(plate)
    return plate.svg()


def out_name(slug: str, mode: str) -> str:
    return slug if mode == 'light' else f"{slug}_dark"


def rasterise(browser: str, svg_path: str, png_path: str) -> None:
    profile = tempfile.mkdtemp(prefix='plate_chrome_')
    try:
        subprocess.run([
            browser, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
            '--force-device-scale-factor=1', f'--window-size={common.W},{common.H}',
            f'--user-data-dir={profile}', f'--screenshot={png_path}',
            'file:///' + svg_path.replace('\\', '/'),
        ], check=True, capture_output=True, timeout=120)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not os.path.exists(png_path):
        raise RuntimeError(f"browser produced no screenshot for {svg_path}")


def contact_sheet(slugs, images, file_name='contact_sheet.png') -> None:
    cols = 4
    thumb_w, thumb_h, pad, label_h = 460, 259, 28, 30
    rows = (len(slugs) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (thumb_w + pad) + pad, rows * (thumb_h + pad + label_h) + pad), '#EDE8DF')
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(os.path.join(common.FONT_DIR, 'DMMono-Regular.ttf'), 13)
    except OSError:
        font = ImageFont.load_default()
    for i, (slug, image) in enumerate(zip(slugs, images)):
        x = pad + (i % cols) * (thumb_w + pad)
        y = pad + (i // cols) * (thumb_h + pad + label_h)
        sheet.paste(image.resize((thumb_w, thumb_h), Image.LANCZOS), (x, y))
        draw.rectangle([x - 1, y - 1, x + thumb_w, y + thumb_h], outline='#CFC8BC')
        draw.text((x, y + thumb_h + 8), slug.upper(), fill='#5A554D', font=font)
    sheet.save(os.path.join(OUT_DIR, file_name), optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('slugs', nargs='*')
    parser.add_argument('--preview-dir', help='also save full-size PNG renders here')
    parser.add_argument('--no-sheet', action='store_true')
    args = parser.parse_args()

    slugs = args.slugs or sorted(f[:-3] for f in os.listdir(PLATES_DIR)
                                 if f.endswith('.py') and not f.startswith('_'))
    os.makedirs(SRC_DIR, exist_ok=True)
    browser = find_browser()
    tmp = tempfile.mkdtemp(prefix='plates_')
    rendered = {mode: [] for mode in MODES}
    try:
        for slug in slugs:
            module = load_plate(slug)
            sizes = []
            for mode in MODES:
                name = out_name(slug, mode)
                svg = build_svg(module, mode)
                svg_path = os.path.join(SRC_DIR, f"{name}.svg")
                with open(svg_path, 'w', encoding='utf-8') as handle:
                    handle.write(svg)
                png_path = os.path.join(tmp, f"{name}.png")
                rasterise(browser, svg_path, png_path)
                image = Image.open(png_path).convert('RGB')
                if image.size != (common.W, common.H):
                    image = image.resize((common.W, common.H), Image.LANCZOS)
                webp_path = os.path.join(OUT_DIR, f"{name}.webp")
                image.save(webp_path, 'WEBP', quality=WEBP_QUALITY, method=6)
                if args.preview_dir:
                    os.makedirs(args.preview_dir, exist_ok=True)
                    image.save(os.path.join(args.preview_dir, f"{name}.png"))
                rendered[mode].append((slug, image))
                sizes.append(f"{mode} svg {len(svg) // 1024:4d} KB webp {os.path.getsize(webp_path) // 1024:4d} KB")
            print(f"{slug:22s} " + "   ".join(sizes))
        if not args.no_sheet and not args.slugs:
            for mode in MODES:
                contact_sheet([s for s, _ in rendered[mode]], [i for _, i in rendered[mode]],
                              'contact_sheet.png' if mode == 'light' else 'contact_sheet_dark.png')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
