"""
Sidebar: the Salesforce org + ONE "Source connection" picker (any saved source: SQL Server,
Oracle, Snowflake, PostgreSQL) instead of a separate SQL Server and Oracle picker; the
sidebar follows the Light / Dark theme; the real Tavant logo (from tavant.com).

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_source_picker.py -v
"""
import json
import os
import re
import shutil
import sys
import tempfile
import tomllib
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import new_app, no_exceptions  # noqa: E402
from ui_components import connection_manager as cm, theme  # noqa: E402

CREDENTIALS = {
    "AkashDev": {"username": "a@example.com", "password": "x", "security_token": "t", "domain": "login"},
    "sql_Staging": {"server": "db1.example.com", "database": "stage", "username": "u", "password": "x",
                    "driver": "Auto-detect (recommended)", "port": "", "Trusted_Connection": "no"},
    "oracle_HR": {"host": "ora.example.com", "port": "1521", "service_name": "HR", "username": "hr", "password": "x"},
    "snowflake_DW": {"account": "acme-1", "warehouse": "WH", "database": "DW", "username": "sf", "password": "x"},
}
SOURCE_KEY = 'global_source_selector'


class SourcePickerTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='dm_src_')
        path = os.path.join(self.tmp, 'linkedservices.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(CREDENTIALS, f)
        self._old = os.environ.get(cm.CREDENTIALS_ENV)
        os.environ[cm.CREDENTIALS_ENV] = path

    def tearDown(self):
        if self._old is None:
            os.environ.pop(cm.CREDENTIALS_ENV, None)
        else:
            os.environ[cm.CREDENTIALS_ENV] = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_one_picker_lists_every_source_type(self):
        at = new_app()
        no_exceptions(self, at)
        keys = {s.key for s in at.sidebar.selectbox}
        self.assertIn(SOURCE_KEY, keys)
        self.assertNotIn('global_sql_selector', keys)
        self.assertNotIn('global_oracle_selector', keys)
        picker = at.sidebar.selectbox(key=SOURCE_KEY)
        self.assertEqual(list(picker.options)[1:],
                         ['🗄️ SQL Server · Staging', '🔶 Oracle · HR', '❄️ Snowflake · DW'])

    def test_choosing_a_sql_server_source(self):
        at = new_app()
        at.sidebar.selectbox(key=SOURCE_KEY).set_value('sql_Staging').run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['current_sql_connection'], 'sql_Staging')
        self.assertIsNone(at.session_state['current_oracle_connection'])
        self.assertEqual(at.session_state['current_source_connection'], 'sql_Staging')

    def test_choosing_an_oracle_source_replaces_the_sql_one(self):
        at = new_app()
        at.sidebar.selectbox(key=SOURCE_KEY).set_value('sql_Staging').run()
        at.sidebar.selectbox(key=SOURCE_KEY).set_value('oracle_HR').run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['current_oracle_connection'], 'oracle_HR')
        self.assertIsNone(at.session_state['current_sql_connection'])

    def test_a_screen_can_set_the_source_for_every_screen(self):
        # sql_connection_picker's "Use for all screens" asks the sidebar to switch
        at = new_app()
        at.session_state['_pending_connection_changes'] = {'sql': 'sql_Staging'}
        at.run()
        no_exceptions(self, at)
        self.assertEqual(at.sidebar.selectbox(key=SOURCE_KEY).value, 'sql_Staging')
        self.assertEqual(at.session_state['current_sql_connection'], 'sql_Staging')

    def test_no_source_selected(self):
        at = new_app()
        self.assertEqual(at.sidebar.selectbox(key=SOURCE_KEY).value, cm.SOURCE_PLACEHOLDER)
        self.assertFalse(at.session_state['current_source_connection'])


class SidebarThemeTests(unittest.TestCase):

    def test_config_has_a_light_and_a_dark_sidebar(self):
        with open(os.path.join(ROOT, '.streamlit', 'config.toml'), 'rb') as f:
            cfg = tomllib.load(f)['theme']
        light, dark = cfg['light']['sidebar'], cfg['dark']['sidebar']
        self.assertNotEqual(light['backgroundColor'], dark['backgroundColor'])
        self.assertNotIn('backgroundColor', cfg.get('sidebar', {}),
                         "a [theme.sidebar] background would force one colour on both themes")
        self.assertEqual(theme.SIDEBAR_BG['light'], light['backgroundColor'])
        self.assertEqual(theme.SIDEBAR_BG['dark'], dark['backgroundColor'])

    def test_sidebar_styles_follow_the_theme(self):
        css = theme._sidebar_css()
        self.assertIn('var(--dm-side-text)', css)
        for hard_coded in ('#F4F1EE', '#B9B3AE', '#F7A26B'):
            self.assertNotIn(hard_coded, css, "sidebar colours must be theme variables")
        for name in ('side-text', 'side-muted', 'side-heading', 'side-card-bg', 'side-active-text'):
            self.assertIn(name, theme.LIGHT)
            self.assertIn(name, theme.DARK)


class BrandTests(unittest.TestCase):

    def test_tavant_logo_and_icon_assets_exist(self):
        for name in ('tavant_logo.png', 'tavant_icon.png'):
            self.assertTrue(os.path.exists(os.path.join(ROOT, 'assets', 'brand', name)), name)

    def test_sidebar_uses_st_logo(self):
        import inspect
        src = inspect.getsource(theme.render_sidebar_brand)
        self.assertIn('st.logo(', src)
        self.assertIn('icon_image=', src)

    def test_banner_shows_the_logo_image(self):
        html = theme.hero_html()
        self.assertIn('<img', html)
        self.assertIn('data:image/png;base64,', html)

    def test_page_icon_is_the_tavant_icon(self):
        with open(os.path.join(ROOT, 'streamlit_app.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertRegex(src, r'page_icon=\s*theme\.BRAND_ICON')


if __name__ == '__main__':
    unittest.main()
