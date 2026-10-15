"""
Step 3 (Data Operations): gate, Step 2 hand-off, Salesforce and SQL Server loads.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_step3_data_operations.py -v
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from streamlit.testing.v1 import AppTest  # noqa: E402

from helpers import ORG, OTHER_ORG, SQL_KEY, no_exceptions  # noqa: E402
import fake_salesforce  # noqa: E402
from ui_components.navigation import STEP1_PAGE, STEP3_PAGE  # noqa: E402
from ui_components.data_operations import FLOW_SOURCE_OPTION, FLOW_MAPPING_OPTION  # noqa: E402

APP = os.path.join(HERE, 'app_step3.py')
STEP2_RESULT = {
    'method': 'Enhanced Validation',
    'object': 'Account',
    'field_mappings': {'AccountName': 'Name', 'Phone': 'Phone', 'Industry': 'Industry'},
    'lookups_resolved': True,
}


def new_app(timeout: int = 180, **session) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=timeout)
    for key, value in session.items():
        at.session_state[key] = value
    at.run()
    return at


def goto(at, page):
    at.sidebar.radio(key='nav_page').set_value(page).run()


def app_with_step2_done(case, step2_result=None, **session) -> AppTest:
    """Step 1 through the UI (SQL source -> Account), Step 2 published directly."""
    at = new_app(**session)
    at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
    at.sidebar.selectbox(key='global_source_selector').set_value(SQL_KEY).run()
    goto(at, STEP1_PAGE)
    at.radio(key='step1_source').set_value("🗄️ SQL Server").run()
    at.selectbox(key='step1_sql_table').set_value('dbo.Accounts').run()
    at.button(key='step1_sql_run').click().run()
    at.selectbox(key='step1_target_object').set_value('Account').run()
    at.button(key='step1_confirm').click().run()
    no_exceptions(case, at)
    case.assertEqual(at.session_state['flow_dataset']['rows'], 3)
    at.session_state['_test_publish_validation'] = dict(step2_result or STEP2_RESULT)
    at.run()
    case.assertEqual(at.session_state['flow_validation']['summary']['valid'], 2)
    goto(at, STEP3_PAGE)
    no_exceptions(case, at)
    return at


def configure_insert(at):
    """Insert needs a uniqueness strategy: Name -> External_Key__c (single field)."""
    at.selectbox(key='insert_source_field_single').set_value('Name').run()
    at.selectbox(key='insert_target_field_single').set_value('External_Key__c').run()


def button_keys(at):
    return {b.key for b in at.button}


class Step3GateTests(unittest.TestCase):

    def test_without_step2_load_tab_is_locked_and_tools_still_work(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        goto(at, STEP3_PAGE)
        no_exceptions(self, at)
        self.assertTrue(any(k and k.startswith('flow_gate_3_') for k in button_keys(at)),
                        "the Load tab must show the Step 3 lock card")
        self.assertTrue(at.button(key='flow_next_3').disabled)
        self.assertNotIn('sf_load_object', [s.key for s in at.selectbox])
        for tab in (1, 2, 3):
            at.button(key=f'tab_btn_{tab}').click().run()
            no_exceptions(self, at)
            self.assertTrue(at.button(key='flow_next_3').disabled)

    def test_no_org_selected_page_and_sql_tools_render(self):
        at = new_app()
        goto(at, STEP3_PAGE)
        no_exceptions(self, at)
        self.assertTrue(any('No Salesforce org is selected' in w.value for w in at.warning))
        self.assertTrue(at.button(key='flow_next_3').disabled)
        for tab in (1, 2, 3, 0):
            at.button(key=f'tab_btn_{tab}').click().run()
            no_exceptions(self, at)
        # SQL Migration defaults: SQL -> SF direction lists orgs from the connection manager
        at.button(key='tab_btn_1').click().run()
        no_exceptions(self, at)

    def test_manual_load_is_available_while_locked(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        goto(at, STEP3_PAGE)
        at.toggle(key='data_ops_manual_load').set_value(True).run()
        no_exceptions(self, at)
        self.assertIn('sf_load_object', [s.key for s in at.selectbox])
        self.assertEqual(at.selectbox(key='sf_load_object').value, "Select an object...")


class Step3ConnectionTests(unittest.TestCase):

    def test_sql_migration_pickers_default_to_sidebar_connections(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(OTHER_ORG).run()
        at.sidebar.selectbox(key='global_source_selector').set_value(SQL_KEY).run()
        goto(at, STEP3_PAGE)
        at.button(key='tab_btn_1').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.selectbox(key='mig_src_org').value, OTHER_ORG)
        self.assertNotIn(SQL_KEY, at.selectbox(key='mig_src_org').options)
        self.assertEqual(at.selectbox(key='mig_tgt_db').value, SQL_KEY)
        self.assertEqual(at.session_state['connected_org'], OTHER_ORG)

    def test_extraction_sql_picker_does_not_change_sidebar_silently(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        goto(at, STEP3_PAGE)
        at.button(key='tab_btn_2').click().run()
        at.selectbox(key='extraction_source').set_value('SQL Server').run()
        no_exceptions(self, at)
        self.assertIsNone(at.session_state['current_sql_connection'])
        # The picker's button sets the SIDEBAR connection for every screen.
        at.button(key='extract_sql_pick_sql_btn').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['current_sql_connection'], SQL_KEY)
        self.assertEqual(at.sidebar.selectbox(key='global_source_selector').value, SQL_KEY)

    def test_sql_migration_pickers_follow_sidebar_changes_and_keep_user_choice(self):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        goto(at, STEP3_PAGE)
        at.button(key='tab_btn_1').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.selectbox(key='mig_src_org').value, ORG)
        # A later sidebar change is followed (the pipeline must not back up another org).
        at.sidebar.selectbox(key='global_org_selector').set_value(OTHER_ORG).run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['current_org'], OTHER_ORG)
        self.assertEqual(at.selectbox(key='mig_src_org').value, OTHER_ORG)
        # A deliberate choice in the picker is kept across a page round trip ...
        at.selectbox(key='mig_src_org').set_value(ORG).run()
        goto(at, STEP1_PAGE)
        goto(at, STEP3_PAGE)
        no_exceptions(self, at)
        self.assertEqual(at.selectbox(key='mig_src_org').value, ORG)
        # ... and never changes the sidebar org.
        self.assertEqual(at.session_state['current_org'], OTHER_ORG)


class Step3HandoffTests(unittest.TestCase):

    def test_salesforce_load_uses_step2_result_and_unlocks_next(self):
        at = app_with_step2_done(self)
        self.assertTrue(at.button(key='flow_next_3').disabled)
        self.assertEqual(at.selectbox(key='load_destination').value, 'Salesforce')
        self.assertEqual(at.selectbox(key='sf_load_object').value, 'Account')
        self.assertEqual(at.radio(key='sf_load_source').value, FLOW_SOURCE_OPTION)
        self.assertEqual(at.radio(key='mapping_strategy').value, FLOW_MAPPING_OPTION)
        self.assertTrue(any('already resolved' in s.value for s in at.success),
                        "lookup resolution must be skipped for Step 2 rows")

        configure_insert(at)
        no_exceptions(self, at)
        fake_salesforce.reset()
        at.button(key='sf_load_start').click().run()
        no_exceptions(self, at)
        writes = [w for w in fake_salesforce.WRITES if w[0] == 'Account']
        self.assertTrue(writes, f"no Account writes recorded: {fake_salesforce.WRITES}")
        records = [r for w in writes for r in w[2]]
        self.assertEqual(len(records), 2)
        self.assertEqual({r['Name'] for r in records}, {'Initech', 'Umbrella'})
        for rec in records:
            self.assertTrue({'Name', 'Phone', 'Industry'} <= set(rec))
            self.assertNotIn('AccountName', rec)
            self.assertNotIn('Acct_No', rec)

        result = at.session_state['flow_load_result']
        self.assertEqual(result['destination'], 'Salesforce')
        self.assertEqual(result['target'], 'Account')
        self.assertEqual(result['success'], 2)
        self.assertEqual(result['validation_id'], at.session_state['flow_validation']['id'])
        self.assertFalse(at.button(key='flow_next_3').disabled)

        # The result survives a rerun (e.g. a download button click) and a page switch.
        at.run()
        self.assertFalse(at.button(key='flow_next_3').disabled)
        goto(at, STEP1_PAGE)
        goto(at, STEP3_PAGE)
        no_exceptions(self, at)
        self.assertFalse(at.button(key='flow_next_3').disabled)

    def test_reviewing_step2_mappings_keeps_unmapped_columns_skipped(self):
        # Step 2 deliberately left Phone unmapped: reviewing must not auto-map it.
        partial = dict(STEP2_RESULT, field_mappings={'AccountName': 'Name', 'Industry': 'Industry'})
        at = app_with_step2_done(self, step2_result=partial)
        self.assertEqual(at.radio(key='mapping_strategy').value, FLOW_MAPPING_OPTION)
        at.checkbox(key='sf_load_flow_mapping_edit').check().run()
        no_exceptions(self, at)
        configure_insert(at)
        fake_salesforce.reset()
        at.button(key='sf_load_start').click().run()
        no_exceptions(self, at)
        records = [r for w in fake_salesforce.WRITES if w[0] == 'Account' for r in w[2]]
        self.assertEqual(len(records), 2)
        for rec in records:
            self.assertIn('Name', rec)
            self.assertIn('Industry', rec)
            self.assertNotIn('Phone', rec)

    def test_user_choices_survive_page_round_trip(self):
        at = app_with_step2_done(self)
        at.selectbox(key='sf_load_object').set_value('Contact').run()
        no_exceptions(self, at)
        goto(at, STEP1_PAGE)
        goto(at, STEP3_PAGE)
        no_exceptions(self, at)
        self.assertEqual(at.selectbox(key='sf_load_object').value, 'Contact')
        # "Select an object..." can be chosen and is not re-seeded with Step 2's object.
        at.selectbox(key='sf_load_object').set_value('Select an object...').run()
        at.run()
        self.assertEqual(at.selectbox(key='sf_load_object').value, 'Select an object...')
        # Back to the Step 2 object: a source switch is kept across a page round trip too.
        at.selectbox(key='sf_load_object').set_value('Account').run()
        at.radio(key='sf_load_source').set_value('Upload File').run()
        goto(at, STEP1_PAGE)
        goto(at, STEP3_PAGE)
        no_exceptions(self, at)
        self.assertEqual(at.radio(key='sf_load_source').value, 'Upload File')

    def test_user_can_switch_to_another_source_and_strategy(self):
        at = app_with_step2_done(self)
        at.radio(key='mapping_strategy').set_value("🤖 Auto Detect").run()
        no_exceptions(self, at)
        self.assertEqual(at.radio(key='mapping_strategy').value, "🤖 Auto Detect")
        at.radio(key='sf_load_source').set_value("Upload File").run()
        no_exceptions(self, at)
        self.assertEqual(at.radio(key='sf_load_source').value, "Upload File")
        # The choice is not overwritten on later reruns.
        at.run()
        self.assertEqual(at.radio(key='sf_load_source').value, "Upload File")

    def test_additional_column_is_loaded(self):
        at = app_with_step2_done(self)
        at.button(key='ac_add_additional_columns_Account').click().run()
        no_exceptions(self, at)
        at.selectbox(key='ac_tgt_additional_columns_Account_0').set_value('AccountNumber').run()
        at.text_input(key='ac_sv_additional_columns_Account_0').input('FIXED-1').run()
        configure_insert(at)
        no_exceptions(self, at)
        fake_salesforce.reset()
        at.button(key='sf_load_start').click().run()
        no_exceptions(self, at)
        records = [r for w in fake_salesforce.WRITES if w[0] == 'Account' for r in w[2]]
        self.assertEqual(len(records), 2)
        self.assertEqual({r.get('AccountNumber') for r in records}, {'FIXED-1'})

    def test_sql_server_load_uses_step2_result(self):
        at = app_with_step2_done(self)
        at.selectbox(key='load_destination').set_value('SQL Server').run()
        no_exceptions(self, at)
        self.assertEqual(at.radio(key='sql_load_source').value, FLOW_SOURCE_OPTION)
        self.assertEqual(at.text_input(key='sql_load_table_name').value, 'Account')
        self.assertTrue(at.checkbox(key='sql_load_flow_rename').value)
        at.selectbox(key='sql_load_mode').set_value('Replace Existing').run()
        at.button(key='sql_load_start').click().run()
        no_exceptions(self, at)
        writes = at.session_state['_test_sql_writes']
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]['table'], 'Account')
        self.assertEqual(writes[0]['rows'], 2)
        self.assertEqual(set(writes[0]['columns']), {'Name', 'Phone', 'Industry'})
        result = at.session_state['flow_load_result']
        self.assertEqual(result['destination'], 'SQL Server')
        self.assertEqual(result['target'], 'dbo.Account')
        self.assertEqual(result['success'], 2)
        self.assertFalse(at.button(key='flow_next_3').disabled)
        self.assertNotEqual(at.session_state['current_sql_connection'], None)

    def test_sql_table_name_kept_after_source_detour(self):
        at = app_with_step2_done(self)
        at.selectbox(key='load_destination').set_value('SQL Server').run()
        self.assertEqual(at.text_input(key='sql_load_table_name').value, 'Account')
        at.text_input(key='sql_load_table_name').input('my_tbl').run()
        at.radio(key='sql_load_source').set_value('Upload File').run()  # table widget not drawn
        no_exceptions(self, at)
        at.radio(key='sql_load_source').set_value(FLOW_SOURCE_OPTION).run()
        no_exceptions(self, at)
        self.assertEqual(at.text_input(key='sql_load_table_name').value, 'my_tbl')

    def test_sql_server_source_can_read_from_another_connection(self):
        at = app_with_step2_done(self, _test_second_sql=True)
        at.selectbox(key='load_destination').set_value('SQL Server').run()
        at.radio(key='sql_load_source').set_value('SQL Server').run()
        no_exceptions(self, at)
        picker = at.selectbox(key='sql_load_source_connection')
        self.assertEqual(picker.value, SQL_KEY, "the source defaults to the sidebar connection")
        picker.set_value('sql_Second').run()
        at.text_area(key='sql_load_source_query').input('SELECT * FROM dbo.Accounts').run()
        at.session_state['_test_sql_reads'] = []
        at.button(key='sql_load_run_source_query').click().run()
        no_exceptions(self, at)
        reads = [r for r in at.session_state['_test_sql_reads'] if r['query'] == 'SELECT * FROM dbo.Accounts']
        self.assertEqual([r['server'] for r in reads], ['second-host'])
        # A read-only choice: the sidebar (and so the target) connection is unchanged.
        self.assertEqual(at.session_state['current_sql_connection'], SQL_KEY)
        self.assertIn('sql_load_start', button_keys(at))

    def test_sql_server_query_source_persists_so_load_button_is_reachable(self):
        at = app_with_step2_done(self)
        at.selectbox(key='load_destination').set_value('SQL Server').run()
        at.radio(key='sql_load_source').set_value('SQL Server').run()
        at.text_area(key='sql_load_source_query').input('SELECT * FROM dbo.Accounts').run()
        at.button(key='sql_load_run_source_query').click().run()
        no_exceptions(self, at)
        at.run()  # an unrelated rerun used to lose the query result
        self.assertIn('sql_load_start', button_keys(at))
        at.text_input(key='sql_load_table_name').input('manual_accounts').run()
        at.button(key='sql_load_start').click().run()
        no_exceptions(self, at)
        writes = at.session_state['_test_sql_writes']
        self.assertEqual(writes[-1]['table'], 'manual_accounts')
        self.assertEqual(writes[-1]['rows'], 3)
        # A manual load does not complete the guided step.
        self.assertNotIn('flow_load_result', at.session_state)
        self.assertTrue(at.button(key='flow_next_3').disabled)


class Step3DefaultsFromStep2Tests(unittest.TestCase):

    def test_insert_external_id_target_is_prefilled(self):
        """The fake Account has one External ID field: Insert's target defaults to it."""
        at = app_with_step2_done(self)
        self.assertEqual(at.selectbox(key='insert_target_field_single').value, 'External_Key__c')

    def test_upsert_match_field_comes_from_step2(self):
        result = dict(STEP2_RESULT, match={'strategy': 'unique_field', 'fields': ['Name'], 'separator': '_'})
        at = app_with_step2_done(self, step2_result=result)
        at.selectbox(key='sf_load_operation').set_value('Upsert').run()
        no_exceptions(self, at)
        self.assertEqual(at.selectbox(key='upsert_match_field_select').value, 'Name')

    def test_operation_choice_survives_a_page_switch(self):
        at = app_with_step2_done(self)
        at.selectbox(key='sf_load_operation').set_value('Update').run()
        goto(at, STEP1_PAGE)
        goto(at, STEP3_PAGE)
        no_exceptions(self, at)
        self.assertEqual(at.selectbox(key='sf_load_operation').value, 'Update')

    def test_column_analysis_is_computed_once(self):
        from ui_components import data_operations
        at = app_with_step2_done(self)
        profile = at.session_state['_step3_column_profile']
        calls = []
        original = data_operations.analyze_data_quality
        data_operations.analyze_data_quality = lambda df: calls.append(1) or original(df)
        try:
            at.run()
            at.run()
        finally:
            data_operations.analyze_data_quality = original
        self.assertEqual(calls, [], "the column analysis must be reused on plain reruns")
        self.assertEqual(at.session_state['_step3_column_profile']['signature'], profile['signature'])


if __name__ == '__main__':
    unittest.main()
