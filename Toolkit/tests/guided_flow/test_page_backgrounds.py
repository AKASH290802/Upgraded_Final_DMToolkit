"""
Background art per screen (ui_components/page_backgrounds.py).

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_page_backgrounds.py -v
"""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import new_app, no_exceptions  # noqa: E402
from ui_components import navigation, page_backgrounds  # noqa: E402

PNG_BYTES = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + b'0' * 32
JPEG_BYTES = bytes([0xFF, 0xD8, 0xFF]) + b'0' * 32


def sidebar_styles(at):
    return [m.value for m in at.sidebar.markdown if '<style>' in str(m.value) and '.stApp::before' in str(m.value)]


class PlateCoverageTests(unittest.TestCase):

    def test_every_sidebar_page_has_a_plate_in_both_themes(self):
        self.assertEqual(set(page_backgrounds.PAGE_SLUGS), set(navigation.PAGE_LIST))
        missing = [name for slug in page_backgrounds.PAGE_SLUGS.values() for name in (slug, slug + '_dark')
                   if not os.path.exists(os.path.join(page_backgrounds.ASSET_DIR, name + '.webp'))]
        self.assertEqual(missing, [], "render them with: .venv\\Scripts\\python.exe tools\\backgrounds\\render.py")

    def test_plates_stay_small(self):
        for slug in page_backgrounds.PAGE_SLUGS.values():
            for name in (slug, slug + '_dark'):
                path = os.path.join(page_backgrounds.ASSET_DIR, name + '.webp')
                if os.path.exists(path):
                    self.assertLess(os.path.getsize(path), 120 * 1024, name)


class RenderingTests(unittest.TestCase):

    def test_each_page_shows_its_own_plate_and_the_toggle_hides_it(self):
        at = new_app()
        seen = set()
        for page in navigation.PAGE_LIST:
            at.sidebar.radio(key='nav_page').set_value(page).run()
            no_exceptions(self, at)
            styles = sidebar_styles(at)
            self.assertEqual(len(styles), 1, page)
            self.assertIn('data:image/', styles[0])
            seen.add(styles[0])
        self.assertEqual(len(seen), len(navigation.PAGE_LIST), "every screen has a different image")
        at.sidebar.toggle(key=page_backgrounds.TOGGLE_KEY).set_value(False).run()
        no_exceptions(self, at)
        self.assertEqual(sidebar_styles(at), [])


class CustomImageAndThemeTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.patch = mock.patch.object(page_backgrounds, 'CUSTOM_DIR', self.tmp)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_custom_image_replaces_the_plate(self):
        custom = os.path.join(self.tmp, 'source_target.png')
        with open(custom, 'wb') as handle:
            handle.write(PNG_BYTES)
        self.assertEqual(page_backgrounds.background_path('source_target'), custom)
        css = page_backgrounds.page_background_css(navigation.STEP1_PAGE)
        self.assertIn('data:image/png;base64', css)

    # The browser picks the light or dark plate (<html data-dm-theme>); both are in the CSS.
    # More on this in test_dark_mode.py.

    def test_dark_theme_uses_the_dark_variant_and_the_hero_shows_it(self):
        path = page_backgrounds.background_path('source_target', dark=True)
        self.assertTrue(path.endswith('source_target_dark.webp'), path)
        css = page_backgrounds.page_background_css(navigation.STEP1_PAGE)
        self.assertNotIn('invert(', css)
        self.assertIn('.dm-hero', css, "the hero banner shows the screen's scene")

    def test_light_only_plate_is_inverted_in_dark_theme(self):
        light_only = os.path.join(page_backgrounds.ASSET_DIR, 'source_target.webp')
        with mock.patch.object(page_backgrounds, 'background_path', return_value=light_only):
            css = page_backgrounds.page_background_css(navigation.STEP1_PAGE)
        dark = css[css.index(':root[data-dm-theme="dark"]'):]
        self.assertIn('invert(', dark)

    def test_custom_jpeg_is_not_inverted(self):
        custom = os.path.join(self.tmp, 'source_target.jpg')
        with open(custom, 'wb') as handle:
            handle.write(JPEG_BYTES)
        css = page_backgrounds.page_background_css(navigation.STEP1_PAGE)
        self.assertNotIn('invert(', css)
        self.assertIn('data:image/jpeg;base64', css)

    def test_unknown_page_has_no_background(self):
        with mock.patch.object(page_backgrounds, 'background_path', return_value=None):
            self.assertEqual(page_backgrounds.page_background_css(navigation.STEP1_PAGE), '')


if __name__ == '__main__':
    unittest.main()
