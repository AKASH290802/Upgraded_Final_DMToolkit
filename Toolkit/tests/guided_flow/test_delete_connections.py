"""
Configuration > delete one saved connection at a time (Salesforce org or source DB).

Every test runs on a throw-away linkedservices.json (DM_TOOLKIT_CREDENTIALS), never on
Services/linkedservices.json.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_delete_connections.py -v
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import new_app, no_exceptions  # noqa: E402
from ui_components import connection_manager  # noqa: E402

CONFIG_PAGE = "⚙️ Configuration"
CREDENTIALS = {
    "AkashDev": {"username": "a@example.com", "password": "pw-a", "security_token": "tok-a", "domain": "login"},
    "FCS": {"username": "f@example.com", "password": "pw-f", "security_token": "tok-f", "domain": "test"},
    "ValmontQA": {"username": "v@example.com", "password": "pw-v", "security_token": "", "domain": "test"},
    "sql_SQL Server": {"server": "db1.example.com", "database": "stage", "username": "u", "password": "pw-s",
                       "driver": "Auto-detect (recommended)", "port": "", "Trusted_Connection": "no"},
    "oracle_HR": {"host": "ora.example.com", "port": "1521", "service_name": "HR", "username": "hr",
                  "password": "pw-o"},
    "openai_config": {"api_key": "sk-test", "endpoint": "https://example.invalid"},
}


def delete_buttons(at):
    return sorted(b.key for b in at.button if b.key and b.key.startswith('delete_conn_'))


class DeleteConnectionTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='dm_creds_')
        self.path = os.path.join(self.tmp, 'linkedservices.json')
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(CREDENTIALS, f, indent=2)
        self._old_env = os.environ.get(connection_manager.CREDENTIALS_ENV)
        os.environ[connection_manager.CREDENTIALS_ENV] = self.path

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop(connection_manager.CREDENTIALS_ENV, None)
        else:
            os.environ[connection_manager.CREDENTIALS_ENV] = self._old_env
        shutil.rmtree(self.tmp, ignore_errors=True)

    def saved(self):
        with open(self.path, encoding='utf-8') as f:
            return json.load(f)

    def config_app(self, org=None, sql=None):
        at = new_app()
        if org:
            at.sidebar.selectbox(key='global_org_selector').set_value(org).run()
        if sql:
            at.sidebar.selectbox(key='global_source_selector').set_value(sql).run()
        at.sidebar.radio(key='nav_page').set_value(CONFIG_PAGE).run()
        no_exceptions(self, at)
        return at

    def confirm(self, at):
        at.button(key='confirm_delete_connection').click().run()
        no_exceptions(self, at)

    # ── what is offered ────────────────────────────────────────────────────

    def test_every_connection_has_its_own_delete_button(self):
        at = self.config_app()
        self.assertEqual(delete_buttons(at), sorted(
            f"delete_conn_{k}" for k in ("AkashDev", "FCS", "ValmontQA", "sql_SQL Server", "oracle_HR")))

    def test_non_connection_settings_cannot_be_deleted(self):
        at = self.config_app()
        self.assertNotIn("delete_conn_openai_config", delete_buttons(at))

    def test_user_names_are_shown_as_plain_text(self):
        # Inline markdown would turn "a@example.com" into a mailto: link and "a_b" into italics;
        # an HTML block (<div>...</div>) is left alone. The browser check: no mailto: links.
        at = self.config_app()
        cells = [str(m.value) for m in at.markdown if '@example.com' in str(m.value)]
        self.assertEqual(len(cells), 3)   # the three org user names
        for cell in cells:
            self.assertTrue(cell.startswith('<div class="dm-conn-cell">') and cell.endswith('</div>'), cell)

    def test_old_hidden_remove_button_is_gone(self):
        at = self.config_app()
        self.assertEqual([b.key for b in at.button if b.key and b.key.startswith('remove_')], [])

    # ── confirm / cancel ───────────────────────────────────────────────────

    def test_delete_asks_for_confirmation_first(self):
        at = self.config_app()
        at.button(key='delete_conn_FCS').click().run()
        no_exceptions(self, at)
        self.assertIn('FCS', self.saved())  # nothing deleted yet
        self.assertIn('confirm_delete_connection', [b.key for b in at.button])
        self.assertIn('FCS', " ".join(str(m.value) for m in at.markdown))

    def test_cancel_keeps_the_connection(self):
        at = self.config_app()
        at.button(key='delete_conn_FCS').click().run()
        at.button(key='cancel_delete_connection').click().run()
        no_exceptions(self, at)
        self.assertEqual(self.saved(), CREDENTIALS)
        self.assertNotIn('confirm_delete_connection', [b.key for b in at.button])

    def test_dismissing_the_dialog_clears_the_request(self):
        from ui_components import config_management
        at = self.config_app()
        at.button(key='delete_conn_FCS').click().run()
        self.assertEqual(at.session_state[config_management.PENDING_DELETE_KEY], 'FCS')
        # The dialog's on_dismiss callback (X / Escape); AppTest cannot press Escape, so call it directly.
        fake_state = {config_management.PENDING_DELETE_KEY: 'FCS'}
        with unittest.mock.patch.object(config_management.st, 'session_state', fake_state):
            config_management._clear_pending_delete()
        self.assertEqual(fake_state, {})
        # ...and with the request gone, the dialog no longer opens.
        del at.session_state[config_management.PENDING_DELETE_KEY]
        at.run()
        self.assertNotIn('confirm_delete_connection', [b.key for b in at.button])
        self.assertEqual(self.saved(), CREDENTIALS)

    # ── deleting ───────────────────────────────────────────────────────────

    def test_confirm_deletes_only_that_org(self):
        at = self.config_app()
        at.button(key='delete_conn_FCS').click().run()
        self.confirm(at)
        expected = {k: v for k, v in CREDENTIALS.items() if k != 'FCS'}
        self.assertEqual(self.saved(), expected)
        self.assertNotIn('delete_conn_FCS', delete_buttons(at))
        self.assertNotIn('FCS', at.session_state['available_orgs'])
        self.assertNotIn('FCS', at.sidebar.selectbox(key='global_org_selector').options)

    def test_confirm_deletes_a_source_connection(self):
        at = self.config_app()
        at.button(key='delete_conn_oracle_HR').click().run()
        self.confirm(at)
        self.assertNotIn('oracle_HR', self.saved())
        self.assertEqual(len(self.saved()), len(CREDENTIALS) - 1)

    def test_deleting_the_sidebar_org_resets_the_sidebar(self):
        at = self.config_app(org='FCS')
        self.assertEqual(at.session_state['current_org'], 'FCS')
        at.button(key='delete_conn_FCS').click().run()
        self.confirm(at)
        self.assertIsNone(at.session_state['current_org'])
        self.assertEqual(at.sidebar.selectbox(key='global_org_selector').value,
                         connection_manager.ORG_PLACEHOLDER)
        self.assertNotIn('FCS', at.session_state['_sf_conn_pool'])

    def test_deleting_the_sidebar_sql_connection_resets_it(self):
        at = self.config_app(sql='sql_SQL Server')
        at.button(key='delete_conn_sql_SQL Server').click().run()
        self.confirm(at)
        self.assertIsNone(at.session_state['current_sql_connection'])
        self.assertNotIn('sql_SQL Server', self.saved())

    # ── undo ───────────────────────────────────────────────────────────────

    def test_undo_restores_the_connection_in_its_place(self):
        at = self.config_app()
        at.button(key='delete_conn_FCS').click().run()
        self.confirm(at)
        at.button(key='undo_delete_connection').click().run()
        no_exceptions(self, at)
        self.assertEqual(list(self.saved().items()), list(CREDENTIALS.items()))  # same content, same order
        self.assertIn('delete_conn_FCS', delete_buttons(at))
        self.assertNotIn('undo_delete_connection', [b.key for b in at.button])

    def test_undo_does_not_overwrite_a_connection_added_since(self):
        at = self.config_app()
        at.button(key='delete_conn_FCS').click().run()
        self.confirm(at)
        replacement = dict(CREDENTIALS['FCS'], username='new@example.com')
        creds = self.saved()
        creds['FCS'] = replacement
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(creds, f)
        at.button(key='undo_delete_connection').click().run()
        no_exceptions(self, at)
        self.assertEqual(self.saved()['FCS'], replacement)


if __name__ == '__main__':
    unittest.main()
