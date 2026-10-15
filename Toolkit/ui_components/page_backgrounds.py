"""
Background art for every screen (the "Tango Aurora" scenes, Tavant colours).

Each sidebar page has its own plate in assets/backgrounds/<slug>.webp (drawn by
tools/backgrounds/render.py). To use your own image for a screen — for example
one made with an AI image generator — put it in assets/backgrounds/custom/ with
the same slug and any of these extensions: .webp .png .jpg .jpeg. Custom images
win over the built-in plates.

The page content sits on a translucent panel so text stays readable. In the dark
theme the '<slug>_dark' plate is used; a light-only image is shown inverted.
"""

import base64
import functools
import os
from typing import Optional

import streamlit as st

from ui_components import navigation

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(PROJECT_ROOT, 'assets', 'backgrounds')
CUSTOM_DIR = os.path.join(ASSET_DIR, 'custom')

PAGE_SLUGS = {
    navigation.DASHBOARD: 'dashboard',
    "⚙️ Configuration": 'configuration',
    navigation.STEP1_PAGE: 'source_target',
    navigation.STEP2_PAGE: 'mapping_validation',
    navigation.STEP3_PAGE: 'data_operations',
    navigation.STEP4_PAGE: 'unit_testing',
    "📊 Data Hub": 'data_hub',
    "📁 File Library": 'file_library',
    "🎯 Migration Readiness": 'migration_readiness',
    "🧩 Multi Data File": 'multi_data_file',
    "🗺️ Mapping": 'mapping',
    "🔄 Org Migration": 'org_migration',
    "🔍 Object Comparison": 'object_comparison',
    "📋 Logs & Reports": 'logs_reports',
}

_MIME = {'.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
TOGGLE_KEY = 'show_page_backgrounds'


def background_path(slug: str, dark: bool = False) -> Optional[str]:
    """The image shown for slug: a custom image if present, else the built-in plate.

    In the dark theme a plate's '<slug>_dark' variant is preferred when it exists.
    """
    names = ([slug + '_dark'] if dark else []) + [slug]
    for name in names:
        for ext in ('.webp', '.png', '.jpg', '.jpeg'):
            custom = os.path.join(CUSTOM_DIR, name + ext)
            if os.path.exists(custom):
                return custom
    for name in names:
        plate = os.path.join(ASSET_DIR, name + '.webp')
        if os.path.exists(plate):
            return plate
    return None


@functools.lru_cache(maxsize=32)
def _data_uri(path: str, mtime: float) -> str:
    with open(path, 'rb') as handle:
        data = base64.b64encode(handle.read()).decode('ascii')
    return f"data:{_MIME.get(os.path.splitext(path)[1].lower(), 'image/webp')};base64,{data}"


def page_background_css(page: str) -> str:
    """CSS that paints page's plate behind the app (empty string if there is none).

    Both the light and the dark plate are sent; the browser shows the one for the theme
    on screen (<html data-dm-theme>, set by theme.THEME_WATCH_JS), so switching the
    theme in ⋮ > Settings swaps the art at once, without a rerun.
    """
    slug = PAGE_SLUGS.get(navigation.resolve_page(page))
    light_path = background_path(slug) if slug else None
    if not light_path:
        return ''
    dark_path = background_path(slug, dark=True) or light_path
    light_uri = _data_uri(light_path, os.path.getmtime(light_path))
    dark_uri = _data_uri(dark_path, os.path.getmtime(dark_path))
    has_dark_variant = os.path.splitext(os.path.basename(dark_path))[0].endswith('_dark')
    custom = dark_path.startswith(CUSTOM_DIR)
    # A light plate without a dark variant is shown inverted in the dark theme so it does not glare.
    dark_filter = 'none' if (custom or has_dark_variant) else 'invert(0.93) hue-rotate(180deg) brightness(0.92)'
    art_vars = (f':root {{ --dm-art: url("{light_uri}"); --dm-art-filter: none; }}\n'
                f':root[data-dm-theme="dark"] {{ --dm-art: url("{dark_uri}"); --dm-art-filter: {dark_filter}; }}\n'
                f'@media (prefers-color-scheme: dark) {{ :root:not([data-dm-theme]) '
                f'{{ --dm-art: url("{dark_uri}"); --dm-art-filter: {dark_filter}; }} }}\n')
    # The dark variant of the scene is also shown crisply in the hero banner (fading in from the right).
    hero_path = background_path(slug, dark=True)
    hero_css = ''
    if hero_path and os.path.splitext(os.path.basename(hero_path))[0].endswith('_dark'):
        hero_uri = _data_uri(hero_path, os.path.getmtime(hero_path))
        hero_css = f"""
.stApp .dm-hero {{
    background:
      linear-gradient(90deg, #15151C 0%, rgba(21,21,28,0.94) 34%, rgba(21,21,28,0.45) 62%, rgba(21,21,28,0.05) 100%),
      url("{hero_uri}") right 42% / cover no-repeat, #15151C;
    min-height: 0;
}}
"""
    # --dm-paper / --dm-panel / ... are the theme colours from theme.theme_vars_css().
    return art_vars + hero_css + """
.stApp { background-color: var(--dm-paper); }
.stApp::before {
    content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background: var(--dm-art) right center / cover no-repeat;
    filter: var(--dm-art-filter);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stAppViewContainer"], [data-testid="stMain"] { background: transparent; }
[data-testid="stMain"], section.main { position: relative; z-index: 1; }
[data-testid="stMainBlockContainer"], .main .block-container {
    background: var(--dm-panel);
    border: 1px solid var(--dm-panel-border);
    border-radius: 18px;
    box-shadow: 0 12px 40px var(--dm-panel-shadow);
    backdrop-filter: blur(4px) saturate(1.1);
    -webkit-backdrop-filter: blur(4px) saturate(1.1);
    margin-top: .5rem;
    margin-bottom: 2rem;
}
"""


def render_page_background(page: str) -> None:
    """Draw the background toggle (in the current container) and apply the page's art."""
    if TOGGLE_KEY not in st.session_state:
        st.session_state[TOGGLE_KEY] = True
    st.toggle("🎨 Background art", key=TOGGLE_KEY,
              help="Show a background illustration for each screen. Put your own images in "
                   "assets/backgrounds/custom/<screen>.png|jpg|webp to replace them.")
    if st.session_state[TOGGLE_KEY]:
        css = page_background_css(page)
        if css:
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
