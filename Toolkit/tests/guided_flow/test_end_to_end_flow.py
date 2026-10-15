"""
End-to-end: the whole guided flow through the real UI, moving only with Next buttons.

    sidebar org + SQL  ->  Step 1 (SQL source)  ->  Next
    Step 2 (Schema Validation on the Step 1 dataset)  ->  Next
    Step 3 (Load Validated Data into Salesforce)  ->  Next  ->  Unit Testing

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_end_to_end_flow.py -v
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from streamlit.testing.v1 import AppTest  # noqa: E402

from helpers import ORG, SQL_KEY, no_exceptions  # noqa: E402
import fake_salesforce  # noqa: E402
from ui_components.navigation import STEP1_PAGE, STEP2_PAGE, STEP3_PAGE, STEP4_PAGE  # noqa: E402
from ui_components.data_operations import FLOW_MAPPING_OPTION, FLOW_SOURCE_OPTION  # noqa: E402

APP = os.path.join(HERE, 'app_step3.py')   # real app + fake SF/SQL, File Library isolated


class EndToEndFlowTests(unittest.TestCase):

    def test_guided_flow_step1_to_step3_with_next_buttons_only(self):
        at = AppTest.from_file(APP, default_timeout=180)
        at.run()
        fake_salesforce.reset()

        # Sidebar: the ONE place connections are chosen.
        at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
        at.sidebar.selectbox(key='global_source_selector').set_value(SQL_KEY).run()
        logins = len(fake_salesforce.LOGINS)
        self.assertEqual(logins, 1)

        # Dashboard quick action starts the flow.
        at.button(key='dash_start_flow').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['nav_page'], STEP1_PAGE)

        # ---- Step 1: Data Loading --------------------------------------------------
        self.assertTrue(at.button(key='flow_next_1').disabled)
        at.radio(key='step1_source').set_value("🗄️ SQL Server").run()
        at.selectbox(key='step1_sql_table').set_value('dbo.Accounts').run()
        at.button(key='step1_sql_run').click().run()
        at.selectbox(key='step1_target_object').set_value('Account').run()
        at.button(key='step1_confirm').click().run()
        no_exceptions(self, at)
        self.assertFalse(at.button(key='flow_next_1').disabled)
        at.button(key='flow_next_1').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['nav_page'], STEP2_PAGE)

        # ---- Step 2: Mapping & Validation ------------------------------------------
        self.assertTrue(at.button(key='flow_next_2').disabled)
        self.assertEqual(at.selectbox(key='schema_validation_object').value, 'Account')
        at.button(key='schema_run_validation').click().run()
        no_exceptions(self, at)
        validation = at.session_state['flow_validation']
        self.assertEqual(validation['dataset_id'], at.session_state['flow_dataset']['id'])
        self.assertEqual(validation['summary']['valid'], 2)      # empty AccountName -> required Name missing
        self.assertEqual(validation['summary']['invalid'], 1)
        self.assertEqual(validation['field_mappings'].get('AccountName'), 'Name')
        self.assertFalse(at.button(key='flow_next_2').disabled)
        at.button(key='flow_next_2').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['nav_page'], STEP3_PAGE)

        # ---- Step 3: Data Operations -----------------------------------------------
        self.assertTrue(at.button(key='flow_next_3').disabled)
        self.assertEqual(at.selectbox(key='sf_load_object').value, 'Account')
        self.assertEqual(at.radio(key='sf_load_source').value, FLOW_SOURCE_OPTION)
        self.assertEqual(at.radio(key='mapping_strategy').value, FLOW_MAPPING_OPTION)
        at.selectbox(key='insert_source_field_single').set_value('Name').run()
        at.selectbox(key='insert_target_field_single').set_value('External_Key__c').run()
        fake_salesforce.WRITES.clear()
        at.button(key='sf_load_start').click().run()
        no_exceptions(self, at)
        records = [r for obj, _op, batch in fake_salesforce.WRITES if obj == 'Account' for r in batch]
        self.assertEqual({r['Name'] for r in records}, {'Initech', 'Umbrella'},
                         "only the rows Step 2 validated are loaded")
        self.assertTrue(all('AccountName' not in r for r in records), "columns are renamed to SF API names")
        self.assertEqual(at.session_state['flow_load_result']['success'], 2)
        self.assertFalse(at.button(key='flow_next_3').disabled)
        at.button(key='flow_next_3').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['nav_page'], STEP4_PAGE)

        # Every screen reused the sidebar connection: no extra logins.
        self.assertEqual(len(fake_salesforce.LOGINS), logins)

        # Going back re-shows the finished steps; changing the Step 1 dataset re-locks 2 and 3.
        at.sidebar.radio(key='nav_page').set_value(STEP1_PAGE).run()
        at.button(key='step1_sql_run').click().run()
        at.button(key='step1_confirm').click().run()
        no_exceptions(self, at)
        self.assertNotIn('flow_validation', at.session_state)
        self.assertNotIn('flow_load_result', at.session_state)
        at.button(key='flow_next_1').click().run()
        self.assertTrue(at.button(key='flow_next_2').disabled)


if __name__ == '__main__':
    unittest.main()
