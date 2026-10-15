"""
Dark mode: every custom colour follows the theme in the BROWSER, at the moment the user
switches it (⋮ > Settings > Light / Dark / System), with no rerun.

Root cause this guards against: the app's background, content panel, cards and step
cards used to be chosen on the server from st.context.theme, which Streamlit only
updates on the next rerun. Choosing Dark in the menu flipped Streamlit's own text to
light colours over the still-light custom background -> light text on a light page.

Now a tiny script (theme.THEME_WATCH_JS) sets <html data-dm-theme="light|dark"> from
the theme Streamlit is actually showing, and all custom colours are CSS variables with
a light and a dark value. These tests check the parts that do not need a browser; the
browser check is tools/theme_check.py.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_dark_mode.py -v
"""
import glob
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import new_app, no_exceptions  # noqa: E402
from ui_components import navigation, page_backgrounds, step_flow, theme  # noqa: E402

DARK_BLOCK = ':root[data-dm-theme="dark"]'


# ── colour maths (WCAG 2.1) ─────────────────────────────────────────────────

def rgba(value):
    if isinstance(value, tuple):
        return value
    value = value.strip()
    if value.startswith('#'):
        h = value[1:]
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
    nums = [float(n) for n in re.findall(r'[\d.]+', value)]
    return nums[0], nums[1], nums[2], (nums[3] if len(nums) > 3 else 1.0)


def over(top, base):
    """Composite colour `top` (may be translucent) over opaque `base`."""
    r, g, b, a = rgba(top)
    br, bg, bb, _ = rgba(base)
    return r * a + br * (1 - a), g * a + bg * (1 - a), b * a + bb * (1 - a), 1.0


def luminance(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b, _ = c if isinstance(c, tuple) else rgba(c)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


class TokenTests(unittest.TestCase):

    def test_light_and_dark_define_the_same_tokens(self):
        self.assertEqual(set(theme.LIGHT), set(theme.DARK))

    def test_dark_block_sets_every_token(self):
        css = theme.theme_vars_css()
        dark = css[css.index(DARK_BLOCK):]
        for name in theme.DARK:
            self.assertIn(f'--dm-{name}:', dark, name)

    def test_text_is_readable_on_the_content_panel(self):
        for mode, t in (('light', theme.LIGHT), ('dark', theme.DARK)):
            panel = over(t['panel'], t['paper'])
            for token in ('heading', 'muted', 'accent-text'):
                self.assertGreaterEqual(contrast(t[token], panel), 4.5, f"{mode} {token} on panel")
            card = over(t['card-bg'], panel)
            self.assertGreaterEqual(contrast(t['heading'], card), 4.5, f"{mode} heading on card")
            self.assertGreaterEqual(contrast(t['muted'], card), 4.5, f"{mode} muted on card")
            # Dashboard KPI numbers and secondary-button hover text use the accent on a card
            self.assertGreaterEqual(contrast(t['accent-text'], card), 4.5, f"{mode} accent on card")

    def test_disabled_buttons_stay_legible(self):
        for mode, t in (('light', theme.LIGHT), ('dark', theme.DARK)):
            self.assertGreaterEqual(contrast(t['disabled-fg'], t['disabled-bg']), 3.0, mode)

    def test_step_cards_are_readable_in_both_themes(self):
        for mode, t in (('light', theme.LIGHT), ('dark', theme.DARK)):
            for kind in theme.STEP_KINDS:
                bg = t[f'step-{kind}-bg']
                for token in ('step-title', 'step-desc', f'step-{kind}-accent'):
                    self.assertGreaterEqual(contrast(t[token], bg), 4.5, f"{mode} {kind} {token}")

    def test_dark_message_boxes_are_readable(self):
        panel = over(theme.DARK['panel'], theme.DARK['paper'])
        for kind, (bg, border, text) in theme.DARK_ALERTS.items():
            self.assertGreaterEqual(contrast(text, over(bg, panel)), 7.0, kind)
            self.assertGreaterEqual(contrast(border, panel), 3.0, f"{kind} accent bar")

    def test_sidebar_text_is_readable(self):
        for mode, t in (('light', theme.LIGHT), ('dark', theme.DARK)):
            bg = theme.SIDEBAR_BG[mode]
            for token in ('side-text', 'side-muted', 'side-heading', 'side-active-text'):
                self.assertGreaterEqual(contrast(t[token], over(t['side-card-bg'], bg) if token == 'side-muted'
                                                 else bg), 4.5, f"{mode} {token}")
            for state in ('ok', 'bad', 'none'):   # status pill on the connection card
                pill = over(t[f'side-{state}-bg'], over(t['side-card-bg'], bg))
                self.assertGreaterEqual(contrast(t[f'side-{state}'], pill), 4.5, f"{mode} status {state}")


class BrowserSideThemeTests(unittest.TestCase):

    def test_no_screen_asks_the_server_which_theme_is_shown(self):
        offenders = []
        for path in glob.glob(os.path.join(ROOT, 'ui_components', '**', '*.py'), recursive=True):
            with open(path, encoding='utf-8') as f:
                if re.search(r'st\.context\.theme|is_dark_theme\(', f.read()):
                    offenders.append(os.path.relpath(path, ROOT))
        self.assertEqual(offenders, [])

    def test_watcher_marks_the_page_with_the_shown_theme(self):
        js = theme.THEME_WATCH_JS
        self.assertIn('dmTheme', js)                     # sets <html data-dm-theme=...>
        self.assertIn('MutationObserver', js)            # follows a menu switch without a rerun
        self.assertIn('prefers-color-scheme', js)        # and an OS switch under "System"

    def test_watcher_is_mounted_on_every_screen(self):
        at = new_app()
        for page in (navigation.DASHBOARD, navigation.STEP2_PAGE, "⚙️ Configuration"):
            at.sidebar.radio(key='nav_page').set_value(page).run()
            no_exceptions(self, at)
            self.assertTrue(at.session_state['_dm_theme_watch_mounted'], page)

    def test_os_dark_preference_applies_before_the_watcher_runs(self):
        css = theme.theme_vars_css()
        self.assertIn('@media (prefers-color-scheme: dark)', css)
        self.assertIn(':root:not([data-dm-theme])', css)


class StepCardTests(unittest.TestCase):

    def test_step_cards_use_theme_classes_not_inline_colours(self):
        import inspect
        src = inspect.getsource(step_flow.render_stepper)
        self.assertNotIn('background:#', src.replace(' ', ''))
        self.assertIn('dm-step', src)


class BackgroundArtTests(unittest.TestCase):

    def _blocks(self, css):
        i = css.index(DARK_BLOCK)
        return css[:i], css[i:]

    def test_both_variants_ship_and_the_browser_picks_one(self):
        css = page_backgrounds.page_background_css(navigation.STEP1_PAGE)
        light, dark = self._blocks(css)
        light_uri = re.search(r'--dm-art:\s*url\("(data:[^"]+)"\)', light).group(1)
        dark_uri = re.search(r'--dm-art:\s*url\("(data:[^"]+)"\)', dark).group(1)
        self.assertNotEqual(light_uri, dark_uri)
        self.assertIn('var(--dm-art)', css)
        self.assertNotIn('invert(', dark)

    def test_light_only_plate_is_inverted_only_in_dark(self):
        from unittest import mock
        light_only = os.path.join(page_backgrounds.ASSET_DIR, 'source_target.webp')
        with mock.patch.object(page_backgrounds, 'background_path', return_value=light_only):
            light, dark = self._blocks(page_backgrounds.page_background_css(navigation.STEP1_PAGE))
        self.assertNotIn('invert(', light)
        self.assertIn('invert(', dark)

    def test_panel_and_paper_follow_the_theme(self):
        css = page_backgrounds.page_background_css(navigation.STEP1_PAGE)
        self.assertIn('var(--dm-paper)', css)
        self.assertIn('var(--dm-panel)', css)
        self.assertNotRegex(css, r'\.stApp \{ background-color: #')


class HardCodedPastelTests(unittest.TestCase):
    """Light pastel cell colours (#d4edda, #f8d7da, ...) glare -- or vanish -- in dark mode."""

    PASTEL = re.compile(r"background(-color)?\s*:\s*#(d4edda|f8d7da|fff3cd|ffebee|fff8e1|e3f2fd|f0f2f6|fafbfc|"
                        r"f8f9ff|f8f9fa)", re.I)

    def test_no_light_pastels_in_the_result_tables(self):
        for name in ('unit_testing_operations.py', 'etl_ui_enhancements.py'):
            with open(os.path.join(ROOT, 'ui_components', name), encoding='utf-8') as f:
                hits = [m.group(0) for m in self.PASTEL.finditer(f.read())]
            self.assertEqual(hits, [], name)


if __name__ == '__main__':
    unittest.main()
