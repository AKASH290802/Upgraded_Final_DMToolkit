"""
Sidebar: one connection card at the top, then the module menu grouped under section headings.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_sidebar.py -v
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import ORG, new_app, no_exceptions  # noqa: E402
import fake_salesforce  # noqa: E402
from ui_components import navigation, theme  # noqa: E402


def sidebar_html(at):
    return " ".join(str(m.value) for m in at.sidebar.markdown)


class MenuTests(unittest.TestCase):

    def test_menu_order_is_unchanged(self):
        self.assertEqual(navigation.PAGE_LIST, [
            "🏠 Dashboard", "⚙️ Configuration",
            "1️⃣ Source/Target Information", "2️⃣ Mapping & Validation", "3️⃣ Data Operations", "4️⃣ Unit Testing",
            "📊 Data Hub", "📁 File Library", "🎯 Migration Readiness", "🧩 Multi Data File", "🗺️ Mapping",
            "🔄 Org Migration", "🔍 Object Comparison", "📋 Logs & Reports"])

    def test_every_section_heading_sits_on_its_first_page(self):
        css = theme.nav_section_css()
        headings = dict(re.findall(r'label:nth-of-type\((\d+)\)::before \{ content: "([^"]+)"', css))
        expected, position = {}, 1
        for title, pages in navigation.NAV_SECTIONS:
            expected[str(position)] = title.upper()
            position += len(pages)
        self.assertEqual(headings, expected)
        self.assertEqual(headings, {'1': 'HOME', '3': 'GUIDED MIGRATION', '7': 'TOOLS', '14': 'REPORTS'})

    def test_menu_is_one_radio_without_a_visible_label(self):
        at = new_app()
        no_exceptions(self, at)
        radio = at.sidebar.radio(key='nav_page')
        self.assertEqual(list(radio.options), navigation.PAGE_LIST)
        self.assertEqual(radio.proto.label_visibility.value, radio.proto.label_visibility.COLLAPSED)


class ConnectionCardTests(unittest.TestCase):

    def test_no_org_selected(self):
        at = new_app()
        html = sidebar_html(at)
        self.assertIn('dm-conn-status none', html)
        self.assertIn('No org selected', html)
        self.assertIn('Object: none selected', html)

    def test_connected_org(self):
        fake_salesforce.reset()
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        no_exceptions(self, at)
        html = sidebar_html(at)
        self.assertIn('dm-conn-status ok', html)
        self.assertIn('Connected', html)
        self.assertEqual(texts(at.sidebar.error), '')

    def test_current_object_is_shown(self):
        at = new_app()
        at.session_state['current_object'] = 'Account'
        at.run()
        self.assertIn('Object: <b>Account</b>', sidebar_html(at))

    def test_old_status_boxes_are_gone(self):
        at = new_app()
        self.assertNotIn('Current Status', sidebar_html(at))
        self.assertEqual([w.value for w in at.sidebar.warning], [])
        self.assertEqual([e.label for e in at.sidebar.expander], [])

    def test_pickers_and_refresh_are_in_the_card(self):
        at = new_app()
        keys = {w.key for w in at.sidebar.selectbox}
        self.assertIn('global_org_selector', keys)
        self.assertIn('refresh_connections', {b.key for b in at.sidebar.button})


def texts(elements):
    return " | ".join(str(e.value) for e in elements)


if __name__ == '__main__':
    unittest.main()
