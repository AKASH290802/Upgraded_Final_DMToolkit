"""
Sidebar navigation, shared connections and Step 1.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -v
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import ORG, OTHER_ORG, SQL_KEY, new_app, no_exceptions  # noqa: E402
import fake_salesforce  # noqa: E402
from ui_components.navigation import STEP1_PAGE, STEP2_PAGE  # noqa: E402


class NavigationTests(unittest.TestCase):

    def test_two_consecutive_sidebar_clicks_both_navigate(self):
        at = new_app()
        at.sidebar.radio(key='nav_page').set_value("⚙️ Configuration").run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['active_page'], "⚙️ Configuration")
        at.sidebar.radio(key='nav_page').set_value("📊 Data Hub").run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['active_page'], "📊 Data Hub")

    def test_legacy_active_page_assignment_still_navigates(self):
        at = new_app()
        at.session_state['active_page'] = "1️⃣ Mapping/Validation"   # old page name
        at.run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['nav_page'], STEP2_PAGE)


class ConnectionTests(unittest.TestCase):

    def test_org_selection_connects_once_and_is_reused_by_pages(self):
        at = new_app()
        fake_salesforce.reset()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['current_org'], ORG)
        self.assertEqual(at.session_state['connected_org'], ORG)
        logins_after_select = len(fake_salesforce.LOGINS)
        self.assertEqual(logins_after_select, 1)
        for page in (STEP1_PAGE, STEP2_PAGE, "📊 Data Hub", "🗺️ Mapping"):
            at.sidebar.radio(key='nav_page').set_value(page).run()
            no_exceptions(self, at)
        self.assertEqual(len(fake_salesforce.LOGINS), logins_after_select,
                         "pages must reuse the sidebar connection instead of logging in again")

    def test_other_org_connection_does_not_replace_sidebar_connection(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        from ui_components import connection_manager  # noqa: F401  (imported in the app process)
        sidebar_conn = at.session_state['sf_connection']
        # A screen asking for a second org (SQL Migration, Object Comparison, ...)
        pool = at.session_state['_sf_conn_pool']
        self.assertIn(ORG, pool)
        at.session_state['_pending_test_other_org'] = OTHER_ORG
        at.run()
        self.assertIs(at.session_state['sf_connection'], sidebar_conn)
        self.assertEqual(at.session_state['connected_org'], ORG)

    def test_org_change_resets_guided_flow(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        at.session_state['flow_dataset'] = {'id': 'x', 'org': ORG, 'object': 'Account', 'rows': 1}
        at.run()
        at.sidebar.selectbox(key='global_org_selector').set_value(OTHER_ORG).run()
        no_exceptions(self, at)
        self.assertNotIn('flow_dataset', at.session_state)
        self.assertEqual(at.session_state['connected_org'], OTHER_ORG)

    def test_non_salesforce_credentials_are_not_listed_as_orgs(self):
        at = new_app()
        options = at.sidebar.selectbox(key='global_org_selector').options
        self.assertNotIn(SQL_KEY, options)
        self.assertNotIn('openai_config', options)


class Step1Tests(unittest.TestCase):

    def test_step1_sql_source_uses_sidebar_connection_and_unlocks_next(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        at.sidebar.selectbox(key='global_source_selector').set_value(SQL_KEY).run()
        at.sidebar.radio(key='nav_page').set_value(STEP1_PAGE).run()
        no_exceptions(self, at)
        self.assertTrue(at.button(key='flow_next_1').disabled)

        at.radio(key='step1_source').set_value("🗄️ SQL Server").run()

        at.selectbox(key='step1_sql_table').set_value('dbo.Accounts').run()
        no_exceptions(self, at)
        at.button(key='step1_sql_run').click().run()
        no_exceptions(self, at)
        self.assertIsNotNone(at.session_state['step1_staged'])
        self.assertEqual(at.session_state['step1_staged']['details']['sql_connection'], SQL_KEY)

        at.selectbox(key='step1_target_object').set_value('Account').run()
        at.button(key='step1_confirm').click().run()
        no_exceptions(self, at)
        dataset = at.session_state['flow_dataset']
        self.assertEqual(dataset['object'], 'Account')
        self.assertEqual(dataset['rows'], 3)
        self.assertFalse(at.button(key='flow_next_1').disabled)

        at.button(key='flow_next_1').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['nav_page'], STEP2_PAGE)

    def _sql_source(self, **session):
        at = new_app()
        for key, value in session.items():
            at.session_state[key] = value
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        at.sidebar.selectbox(key='global_source_selector').set_value(SQL_KEY).run()
        at.sidebar.radio(key='nav_page').set_value(STEP1_PAGE).run()
        at.radio(key='step1_source').set_value("🗄️ SQL Server").run()
        no_exceptions(self, at)
        return at

    def test_sql_table_picker_builds_the_query_for_all_or_first_rows(self):
        at = self._sql_source()
        self.assertEqual(at.text_area(key='step1_sql_query').value, "", "no fake 'YourTable' query")
        self.assertTrue(at.button(key='step1_sql_run').disabled)
        at.selectbox(key='step1_sql_table').set_value('dbo.Accounts').run()
        self.assertEqual(at.radio(key='step1_sql_rows').value, "All rows")
        self.assertEqual(at.text_area(key='step1_sql_query').value, "SELECT * FROM [dbo].[Accounts]")
        at.radio(key='step1_sql_rows').set_value("First rows only").run()
        at.number_input(key='step1_sql_top').set_value(50).run()
        self.assertEqual(at.text_area(key='step1_sql_query').value, "SELECT TOP 50 * FROM [dbo].[Accounts]")
        # An edited query stays until the table or the row choice changes.
        at.text_area(key='step1_sql_query').input("SELECT Name FROM [dbo].[Accounts]").run()
        at.run()
        self.assertEqual(at.text_area(key='step1_sql_query').value, "SELECT Name FROM [dbo].[Accounts]")

    def test_views_are_listed_and_marked(self):
        at = self._sql_source(_test_sql_tables='views')
        picker = at.selectbox(key='step1_sql_table')
        self.assertIn('dbo.vActiveAccounts', picker.options[-1] + ' '.join(picker.options))
        self.assertTrue(any('(view)' in o for o in picker.options), picker.options)

    def test_unreachable_server_shows_why_and_can_retry(self):
        at = self._sql_source(_test_sql_tables='fail')
        warnings = ' | '.join(w.value for w in at.warning)
        self.assertIn('Could not list the tables', warnings)
        self.assertIn('did not answer (port 1433)', warnings)
        self.assertEqual(at.button(key='step1_sql_tables_refresh').label, "🔄 Retry")
        # The failure is remembered (no 30 s wait on every click) until Retry.
        queries = len([q for q in fake_salesforce.QUERIES if 'INFORMATION_SCHEMA' in str(q)])
        at.run()
        self.assertEqual(len([q for q in fake_salesforce.QUERIES if 'INFORMATION_SCHEMA' in str(q)]), queries)
        at.session_state['_test_sql_tables'] = None
        at.button(key='step1_sql_tables_refresh').click().run()
        no_exceptions(self, at)
        self.assertIn('dbo.Accounts', at.selectbox(key='step1_sql_table').options)

    def test_file_library_source_shows_the_projects_files(self):
        import isolation
        from ui_components import file_store_manager as fsm, projects
        isolation.isolate_file_library()
        projects.save_projects([{'name': 'Akash', 'orgs': [ORG], 'aliases': ['AkashOld']}])
        try:
            fsm.register_source_file(b"Name\nAcme\n", "project_accounts.csv", org_name='AkashOld')
            fsm.register_source_file(b"Name\nGlobex\n", "other_customer.csv", org_name=OTHER_ORG)
            at = new_app()
            at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
            at.sidebar.radio(key='nav_page').set_value(STEP1_PAGE).run()
            at.radio(key='step1_source').set_value("📁 File Library").run()
            no_exceptions(self, at)
            self.assertEqual(at.radio(key='step1_library_scope').value, projects.SCOPE_PROJECT)
            options = ' | '.join(at.selectbox(key='step1_library_pick').options)
            self.assertIn('project_accounts.csv', options, "a file filed under the project's alias folder")
            self.assertNotIn('other_customer.csv', options, "another customer's file")
            at.radio(key='step1_library_scope').set_value(projects.SCOPE_ALL).run()
            self.assertIn('other_customer.csv', ' | '.join(at.selectbox(key='step1_library_pick').options))
        finally:
            projects.save_projects([])

    def test_own_query_survives_a_failed_list_and_retry(self):
        at = self._sql_source(_test_sql_tables='fail')
        at.text_area(key='step1_sql_query').input("SELECT Name FROM [dbo].[Accounts] WHERE Name > 'M'").run()
        at.session_state['_test_sql_tables'] = None
        at.button(key='step1_sql_tables_refresh').click().run()
        no_exceptions(self, at)
        self.assertIn('dbo.Accounts', at.selectbox(key='step1_sql_table').options)
        self.assertEqual(at.text_area(key='step1_sql_query').value,
                         "SELECT Name FROM [dbo].[Accounts] WHERE Name > 'M'")

    def test_step1_salesforce_source_uses_sidebar_org(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        at.sidebar.radio(key='nav_page').set_value(STEP1_PAGE).run()
        at.radio(key='step1_source').set_value("☁️ Salesforce (SOQL)").run()
        at.selectbox(key='step1_soql_object').set_value('Account').run()
        at.button(key='step1_soql_run').click().run()
        no_exceptions(self, at)
        staged = at.session_state['step1_staged']
        self.assertEqual(len(staged['df']), 2)
        self.assertNotIn('attributes', staged['df'].columns)
        # The queried object is suggested as the target.
        self.assertEqual(at.selectbox(key='step1_target_object').value, 'Account')


if __name__ == '__main__':
    unittest.main()
