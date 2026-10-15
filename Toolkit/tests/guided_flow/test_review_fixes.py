"""
Regression tests for the final review of the guided flow:
connections (auth vs network failures, My Domain values), Step 1 parsing,
org / SQL changes, re-confirming a dataset, and the Enhanced Validation checks.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_review_fixes.py -v
"""
import io
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pandas as pd  # noqa: E402

from helpers import ORG, OTHER_ORG, ROOT, SQL_KEY, no_exceptions  # noqa: E402
import fake_salesforce  # noqa: E402
from test_step3_data_operations import app_with_step2_done, goto, new_app  # noqa: E402
from ui_components import connection_manager, step1_data_loading, transform_operations  # noqa: E402
from ui_components.navigation import STEP1_PAGE, STEP2_PAGE, STEP3_PAGE  # noqa: E402
from ui_components.validation_operations import _suggest_validation_field_mappings  # noqa: E402

# The tests' (fake) credentials file - never the real Services/linkedservices.json.
with open(connection_manager.credentials_path(), encoding='utf-8') as _f:
    ORG_USERNAME = json.load(_f)[ORG]['username']


def select_org(at, org=ORG):
    at.sidebar.selectbox(key='global_org_selector').set_value(org).run()


def texts(elements):
    return " | ".join(str(e.value) for e in elements)


class ConnectionFailureTests(unittest.TestCase):

    def tearDown(self):
        fake_salesforce.FAIL_MODE.clear()
        connection_manager.SF_NETWORK_RETRY_SECONDS = 20

    def test_wrong_credentials_are_not_retried_until_retry_is_clicked(self):
        fake_salesforce.reset()
        fake_salesforce.FAIL_MODE[ORG_USERNAME] = 'auth'
        at = new_app()
        select_org(at)
        no_exceptions(self, at)
        self.assertIsNone(at.session_state['sf_connection'])
        self.assertIn('Invalid username', texts(at.sidebar.error))
        self.assertIn('retry_sf_connection_status', {b.key for b in at.sidebar.button},
                      "Retry must be visible next to the error, not only inside the collapsed expander")
        fake_salesforce.FAIL_MODE.clear()          # credentials 'fixed' but not retried yet
        at.run()
        self.assertIsNone(at.session_state['sf_connection'], "a credentials failure is sticky")
        at.sidebar.button(key='retry_sf_connection_status').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['connected_org'], ORG)

    def test_network_error_is_retried_automatically(self):
        fake_salesforce.reset()
        fake_salesforce.FAIL_MODE[ORG_USERNAME] = 'network'
        connection_manager.SF_NETWORK_RETRY_SECONDS = 0
        at = new_app()
        select_org(at)
        self.assertIsNone(at.session_state['sf_connection'])
        fake_salesforce.FAIL_MODE.clear()          # network is back
        at.run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['connected_org'], ORG)

    def test_step1_footer_names_the_login_problem(self):
        fake_salesforce.reset()
        fake_salesforce.FAIL_MODE[ORG_USERNAME] = 'auth'
        at = new_app()
        select_org(at)
        goto(at, STEP1_PAGE)
        no_exceptions(self, at)
        self.assertIn('login failed', texts(at.caption))

    def test_domain_values_are_normalised(self):
        cases = {None: 'login', '': 'login', 'login': 'login', 'test': 'test',
                 'test.salesforce.com': 'test', 'mycompany.my.salesforce.com': 'mycompany.my',
                 'https://mycompany.my.salesforce.com/': 'mycompany.my'}
        for raw, expected in cases.items():
            self.assertEqual(connection_manager.normalize_domain(raw), expected, raw)


class ConnectionChangeTests(unittest.TestCase):

    def test_changing_sql_connection_keeps_the_flow(self):
        """Step 3 may load into a different SQL Server than the one Step 1 read from."""
        at = app_with_step2_done(self, _test_second_sql=True)
        at.sidebar.selectbox(key='global_source_selector').set_value('sql_Second').run()
        no_exceptions(self, at)
        self.assertIn('flow_dataset', at.session_state)
        self.assertIn('flow_validation', at.session_state)
        self.assertNotIn('flow_gate_3_1_load', {b.key for b in at.button})

    def test_org_change_keeps_sql_data_staged_and_explains_the_reset(self):
        at = new_app()
        select_org(at)
        at.sidebar.selectbox(key='global_source_selector').set_value(SQL_KEY).run()
        goto(at, STEP1_PAGE)
        at.radio(key='step1_source').set_value("🗄️ SQL Server").run()
        at.selectbox(key='step1_sql_table').set_value('dbo.Accounts').run()
        at.button(key='step1_sql_run').click().run()
        at.selectbox(key='step1_target_object').set_value('Account').run()
        at.button(key='step1_confirm').click().run()
        select_org(at, OTHER_ORG)
        no_exceptions(self, at)
        self.assertNotIn('flow_dataset', at.session_state)
        self.assertEqual(len(at.session_state['step1_staged']['df']), 3, "file/SQL data is not org-specific")
        self.assertIn('org changed', texts(at.info))

    def test_org_change_drops_salesforce_staged_data_and_rule_bundles(self):
        at = new_app()
        select_org(at)
        goto(at, STEP1_PAGE)
        at.radio(key='step1_source').set_value("☁️ Salesforce (SOQL)").run()
        at.selectbox(key='step1_soql_object').set_value('Account').run()
        at.button(key='step1_soql_run').click().run()
        for key in ('ai_bundle_result', 'ai_bundle_generated', 'current_genai_object', 'validator_file_path'):
            at.session_state[key] = 'from ' + ORG
        at.run()
        select_org(at, OTHER_ORG)
        no_exceptions(self, at)
        for key in ('step1_staged', 'ai_bundle_result', 'ai_bundle_generated', 'current_genai_object',
                    'validator_file_path'):
            self.assertNotIn(key, at.session_state, key)


class ReconfirmTests(unittest.TestCase):

    def test_confirming_the_same_dataset_again_keeps_steps_2_and_3(self):
        at = app_with_step2_done(self)
        validation_id = at.session_state['flow_validation']['id']
        goto(at, STEP1_PAGE)
        at.button(key='step1_confirm').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['flow_validation']['id'], validation_id)
        self.assertEqual(at.session_state['data_hub'].get_dataset_count(), 1, "no duplicate copy in the Hub")
        # The staged record shares the Hub's DataFrame instead of holding a second copy.
        dataset_id = at.session_state['flow_dataset']['id']
        self.assertIs(at.session_state['step1_staged']['df'],
                      at.session_state['data_hub'].cached_datasets[dataset_id]['df'])
        goto(at, STEP2_PAGE)
        self.assertFalse(at.button(key='flow_next_2').disabled)

    def test_confirming_another_object_resets_step2(self):
        at = app_with_step2_done(self)
        goto(at, STEP1_PAGE)
        at.selectbox(key='step1_target_object').set_value('Contact').run()
        self.assertIn('resets Steps 2-4', texts(at.caption))
        at.button(key='step1_confirm').click().run()
        self.assertNotIn('flow_validation', at.session_state)
        goto(at, STEP3_PAGE)
        self.assertIn('flow_gate_3_2_load', {b.key for b in at.button})


class Step1ParsingTests(unittest.TestCase):

    def test_soql_relationships_and_subqueries_are_flattened_safely(self):
        records = [
            {'attributes': {'type': 'Account'}, 'Id': '001A', 'Name': 'Globex', 'NumberOfEmployees': 50,
             'Owner': {'attributes': {'type': 'User'}, 'Name': 'Ann'},
             'Parent': {'attributes': {'type': 'Account'}, 'Name': 'Acme'},
             'Contacts': {'totalSize': 1, 'done': True, 'records': [{'Id': '003A'}]}},
            {'attributes': {'type': 'Account'}, 'Id': '001B', 'Name': 'Initech', 'NumberOfEmployees': None,
             'Owner': {'attributes': {'type': 'User'}, 'Name': 'Bob'}, 'Parent': None, 'Contacts': None},
        ]
        df, dropped = step1_data_loading._flatten_records(records)
        self.assertEqual(list(df.columns), ['Id', 'Name', 'NumberOfEmployees', 'Owner.Name', 'Parent.Name'])
        self.assertEqual(dropped, ['Contacts'])
        self.assertEqual(df['NumberOfEmployees'].tolist(), ['50', None])
        self.assertEqual(df['Parent.Name'].tolist(), ['Acme', None])

    def test_relationship_columns_are_not_auto_mapped_onto_name(self):
        fields = [{'name': 'Name', 'label': 'Account Name'}, {'name': 'OwnerId', 'label': 'Owner ID'}]
        suggestions = _suggest_validation_field_mappings(['Name', 'Owner.Name', 'Parent.Name'], fields)
        self.assertEqual(suggestions, {'Name': 'Name'})

    def test_json_integers_stay_integers(self):
        class Upload:
            name = 'rows.json'

            def getvalue(self):
                return json.dumps([{'Name': 'Acme', 'NumberOfEmployees': 10},
                                   {'Name': 'Globex', 'Industry': 'Energy'}]).encode()

        df = step1_data_loading._parse_upload(Upload(), None)
        self.assertEqual(df['NumberOfEmployees'].tolist(), ['10', None])


class EnhancedChecksTests(unittest.TestCase):
    """transform_operations.categorize_transform_results with mapped source columns."""

    @classmethod
    def setUpClass(cls):
        cls.sf = fake_salesforce.FakeSalesforce(username='unit-test')
        fake_salesforce.DESCRIBES['Account']['fields'][4]['restrictedPicklist'] = True   # Industry

    def run_check(self, df, mappings, original=None):
        return transform_operations.categorize_transform_results(
            original if original is not None else df, df, {}, 'Account', self.sf, field_mappings=mappings)

    def test_skipped_column_is_not_checked(self):
        df = pd.DataFrame({'CompanyName': ['A', 'B'], 'Industry': ['NotAPicklistValue', 'Energy']})
        _ok, bad, summary = self.run_check(df, {'CompanyName': 'Name', 'Industry': '-- Skip Field --'})
        self.assertEqual(summary['failure_count'], 0)

    def test_skipped_required_column_is_reported_as_unmapped(self):
        df = pd.DataFrame({'Name': ['A', 'B']})
        _ok, _bad, summary = self.run_check(df, {'Name': '-- Skip Field --'})
        self.assertIn('Name', summary['unmapped_required_fields'])

    def test_unique_check_ignores_case_and_list_cells_do_not_crash(self):
        df = pd.DataFrame({'CompanyName': ['A', 'B', 'C'], 'Key': ['abc', 'ABC', 'xyz'],
                           'Notes': [[], ['x'], None]})
        _ok, bad, summary = self.run_check(df, {'CompanyName': 'Name', 'Key': 'External_Key__c'})
        self.assertEqual(summary['unique_failures'], 2)

    def test_unrestricted_picklist_accepts_other_values(self):
        field = fake_salesforce.DESCRIBES['Account']['fields'][4]
        field['restrictedPicklist'] = False
        try:
            df = pd.DataFrame({'CompanyName': ['A'], 'Industry': ['Aerospace']})
            _ok, _bad, summary = self.run_check(df, {'CompanyName': 'Name', 'Industry': 'Industry'})
            self.assertEqual(summary['failure_count'], 0)
        finally:
            field['restrictedPicklist'] = True

    def test_rows_are_aligned_by_label_after_lookup_resolution_drops_rows(self):
        original = pd.DataFrame({'CompanyName': ['A', 'B', 'C'], 'Parent': ['p1', 'p2', 'p3']})
        transformed = pd.DataFrame({'CompanyName': ['A', 'C'], 'Parent': ['001000000000001AAA', 'p3']},
                                   index=[0, 2])
        ok, bad, _summary = transform_operations.categorize_transform_results(
            original, transformed, {'Parent': {}}, 'Account', self.sf, field_mappings={'CompanyName': 'Name'})
        self.assertEqual(ok['CompanyName'].tolist(), ['A'])     # p1 -> Id resolved
        self.assertEqual(bad['CompanyName'].tolist(), ['C'])    # p3 unchanged -> unresolved


if __name__ == '__main__':
    unittest.main()
