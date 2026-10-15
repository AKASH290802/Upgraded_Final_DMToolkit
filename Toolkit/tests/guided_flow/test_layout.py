"""
Space and look: no dead space above the banner, a slim banner, tight dividers / headings,
and a compact Dashboard (status bar + 4 KPI tiles + session / quick actions side by side).

Measured before (1500x1000): 113 px blank above the banner, banner 157 px, each divider
49 px, each Dashboard card 189 px, Dashboard 1,587 px tall. The browser numbers are checked
with tools/backgrounds/theme_check.py --layout; these tests guard the structure.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_layout.py -v
"""
import os
import re
import sys
import unittest
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import ORG, new_app, no_exceptions  # noqa: E402
from ui_components import connection_manager, file_store_manager as fsm, theme  # noqa: E402
from ui_components.navigation import STEP2_PAGE  # noqa: E402


def kpi_tiles(at):
    """{label: (value, sub)} of the Dashboard KPI tiles."""
    tiles = {}
    for m in at.markdown:
        text = str(m.value)
        for label, value, sub in re.findall(
                r'<div class="dm-kpi-label">([^<]+)</div>\s*<div class="dm-kpi-value">([^<]+)</div>\s*'
                r'<div class="dm-kpi-sub">([^<]*)</div>', text):
            tiles[label] = (value, sub)
    return tiles


def page_html(at):
    return " ".join(str(m.value) for m in at.markdown)


class SpacingTests(unittest.TestCase):

    def test_page_starts_near_the_top(self):
        css = theme._css()
        rule = re.search(r'\[data-testid="stMainBlockContainer"\][^{]*\{([^}]*)\}', css).group(1)
        self.assertRegex(rule, r'padding-top:\s*(1(\.\d+)?|2)rem', "Streamlit's default is 6rem (96 px)")

    def test_banner_is_slim(self):
        css = theme._css()
        logo = re.search(r'\.dm-hero \.dm-logo \{\{?([^}]*)\}', css).group(1)
        self.assertIn('width: 52px', logo)
        hero = re.search(r'\.dm-hero \{\{?([^}]*)\}', css).group(1)
        self.assertIn('padding: 14px 22px', hero)

    def test_dividers_and_headings_are_tight(self):
        css = theme._css()
        self.assertRegex(css, r'\[data-testid="stMain"\] hr \{[^}]*margin: \.5rem 0')
        self.assertRegex(css, r'\[data-testid="stMain"\] h1 \{[^}]*padding: \.25rem 0 \.35rem')

    def test_type_scale_is_compact(self):
        # Streamlit's 2.75 / 2.25 / 1.75 / 1.5 rem wrapped page titles and made sections shout
        css = theme._css()
        for tag, biggest in (('h1', 1.8), ('h2', 1.45), ('h3', 1.25), ('h4', 1.1)):
            size = float(re.search(rf'\[data-testid="stMain"\] {tag} \{{[^}}]*font-size: ([\d.]+)rem', css).group(1))
            self.assertLessEqual(size, biggest, tag)

    def test_step_cards_are_two_lines(self):
        import inspect
        from ui_components import step_flow
        src = inspect.getsource(step_flow.render_stepper)
        self.assertNotIn('class="desc"', src, "the description is the tooltip, not a third/fourth line")
        self.assertIn('title="{step["desc"]}"', src)
        css = theme._css()
        self.assertRegex(css, r'\.dm-step \.state, \.dm-step \.title \{[^}]*white-space: nowrap')

    def test_step_subtitle_is_a_caption(self):
        import inspect
        from ui_components import step_flow
        self.assertIn('st.caption(subtitle)', inspect.getsource(step_flow.render_step_header))


class DashboardTests(unittest.TestCase):

    def test_no_duplicate_title_and_no_dividers(self):
        at = new_app()
        no_exceptions(self, at)
        self.assertNotIn('Welcome to DM Toolkit', page_html(at))   # the banner already says it
        self.assertEqual(len(at.main.get('divider')), 0)   # the sidebar has its own

    def test_four_kpi_tiles_with_real_numbers(self):
        at = new_app()
        tiles = kpi_tiles(at)
        self.assertEqual(list(tiles), ["Salesforce orgs", "Source connections", "Processed files", "Validation runs"])
        groups = connection_manager.classify_credentials(at.session_state['credentials'])
        self.assertEqual(tiles["Salesforce orgs"][0], str(len(groups['salesforce'])))
        sources = sum(len(groups[k]) for k in ('sqlserver', 'oracle', 'snowflake', 'postgres'))
        self.assertEqual(tiles["Source connections"][0], str(sources))

    def test_validation_runs_tile_counts_the_last_7_days_of_the_sidebar_org(self):
        at = new_app()
        saved = fsm.DB_PATH
        fsm.DB_PATH = os.path.join(fsm._apptest_tmp, 'dashboard_runs.db')
        try:
            now = datetime.now()
            for when, org in ((now - timedelta(days=30), ORG), (now - timedelta(hours=2), ORG),
                              (now - timedelta(days=1), ORG), (now, 'OtherOrg')):
                fsm.save_validation_run(org, 'Account', 'Schema Validation', 10, 9, 1,
                                        created_at=when.isoformat(timespec='seconds'))
            at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
            no_exceptions(self, at)
            value, sub = kpi_tiles(at)["Validation runs"]
            self.assertEqual(value, '2')
            self.assertIn('last 7 days', sub)
        finally:
            fsm.DB_PATH = saved

    def test_status_bar_without_org(self):
        at = new_app()
        html = page_html(at)
        self.assertIn('dm-status none', html)
        self.assertIn('Select a Salesforce org in the sidebar', html)
        self.assertIn('dash_start_flow', {b.key for b in at.button})
        self.assertEqual(len(at.warning), 0, "no big warning boxes on the Dashboard")

    def test_status_bar_when_connected(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        html = page_html(at)
        self.assertIn('dm-status ok', html)
        self.assertIn(f'Connected to <b>{ORG}</b>', html)

    def test_quick_actions_are_disabled_without_org_and_work_with_one(self):
        at = new_app()
        self.assertTrue(at.button(key='dash_validation').disabled)
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        self.assertFalse(at.button(key='dash_validation').disabled)
        at.button(key='dash_validation').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['nav_page'], STEP2_PAGE)

    def test_session_panel_lists_the_connections_and_progress(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        html = page_html(at)
        for label in ('Salesforce org', 'Object', 'Source connection', 'Guided migration'):
            self.assertIn(f'<span class="k">{label}</span>', html)
        self.assertIn('0 of 4 steps done', html)


if __name__ == '__main__':
    unittest.main()
