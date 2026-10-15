"""
Projects: one customer's org connections grouped (Valmont = ValmontDev + ValmontQA +
ValmontUAT, plus alias folder names such as Valmont_Industries), and a File Library that
shows the selected org's PROJECT by default ("This project" / "This org" / "All").

Also the File Library index repair: rows still pointing at the old install folders are
re-pointed (or dropped when the file is already indexed at its new path), and the org of
every 'unknown' row is read from its folder path.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_projects.py -v
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import new_app, no_exceptions  # noqa: E402
from ui_components import connection_manager as cm, projects  # noqa: E402
from ui_components import file_store_manager as fsm  # noqa: E402

FILE_LIBRARY = "📁 File Library"
CONFIG_PAGE = "⚙️ Configuration"
CREDENTIALS = {
    "ValmontDev": {"username": "d@example.com", "password": "x", "security_token": "t", "domain": "test"},
    "ValmontQA": {"username": "q@example.com", "password": "x", "security_token": "t", "domain": "test"},
    "ValmontUAT": {"username": "u@example.com", "password": "x", "security_token": "t", "domain": "test"},
    "AkashDev": {"username": "a@example.com", "password": "x", "security_token": "t", "domain": "login"},
    "DTNA_QA": {"username": "n@example.com", "password": "x", "security_token": "t", "domain": "test"},
    "DTNA_UAT": {"username": "m@example.com", "password": "x", "security_token": "t", "domain": "test"},
}
VALMONT = {'name': 'Valmont', 'orgs': ['ValmontDev', 'ValmontQA', 'ValmontUAT'], 'aliases': ['Valmont_Industries']}


class _TempFiles(unittest.TestCase):
    """A throw-away credentials file, projects file and File Library index."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='dm_proj_')
        self.creds = os.path.join(self.tmp, 'linkedservices.json')
        with open(self.creds, 'w', encoding='utf-8') as f:
            json.dump(CREDENTIALS, f)
        self.projects_file = os.path.join(self.tmp, 'projects.json')
        self._env = {k: os.environ.get(k) for k in (cm.CREDENTIALS_ENV, projects.PROJECTS_ENV)}
        os.environ[cm.CREDENTIALS_ENV] = self.creds
        os.environ[projects.PROJECTS_ENV] = self.projects_file
        import isolation
        isolation.isolate_file_library()
        self._db = fsm.DB_PATH
        fsm.DB_PATH = os.path.join(fsm._apptest_tmp, f'projects_{self._testMethodName}.db')
        # The File Library indexes the app folder on its first visit; give it an empty one.
        self._root = fsm.PROJECT_ROOT
        fsm.PROJECT_ROOT = os.path.join(self.tmp, 'empty_install')
        os.makedirs(fsm.PROJECT_ROOT, exist_ok=True)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        fsm.DB_PATH = self._db
        fsm.PROJECT_ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add_file(self, table, org, name, exists=True, obj='Account'):
        path = os.path.join(self.tmp, 'files', org or 'none', name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if exists:
            with open(path, 'w') as f:
                f.write('a,b\n1,2\n')
        fsm.initialize_db()
        with fsm._get_connection() as conn:
            if table == 'source':
                conn.execute("INSERT INTO source_files (original_name, stored_path, org_name, object_name, uploaded_at) "
                             "VALUES (?, ?, ?, ?, '2026-10-01T10:00:00')", (name, path, org, obj))
            else:
                conn.execute("INSERT INTO output_files (original_name, stored_path, org_name, object_name, "
                             "operation_type, generated_at) VALUES (?, ?, ?, ?, 'Validation', '2026-10-01T10:00:00')",
                             (name, path, org, obj))
            conn.commit()
        return path


class ProjectStoreTests(_TempFiles):

    def test_save_load_and_lookup(self):
        projects.save_projects([VALMONT])
        self.assertEqual(projects.load_projects(), [VALMONT])
        self.assertEqual(projects.project_for_org('ValmontQA')['name'], 'Valmont')
        self.assertIsNone(projects.project_for_org('AkashDev'))
        # ...and the project's own folder name, where project-wide uploads are filed
        self.assertEqual(projects.project_labels(VALMONT),
                         ['ValmontDev', 'ValmontQA', 'ValmontUAT', 'Valmont_Industries', 'Valmont'])
        self.assertEqual(projects.project_for_org('Valmont')['name'], 'Valmont')

    def test_missing_file_means_no_projects(self):
        self.assertEqual(projects.load_projects(), [])

    def test_suggestions_group_environments_and_skip_assigned_orgs(self):
        names = ['ValmontDev', 'ValmontQA', 'ValmontUAT', 'AkashDev', 'DTNA_QA', 'DTNA_UAT', 'TavantTechnologies']
        self.assertEqual(projects.suggest_projects(names),
                         {'Valmont': ['ValmontDev', 'ValmontQA', 'ValmontUAT'], 'DTNA': ['DTNA_QA', 'DTNA_UAT']})
        projects.save_projects([VALMONT])
        self.assertEqual(projects.suggest_projects(names), {'DTNA': ['DTNA_QA', 'DTNA_UAT']})

    def test_org_is_read_from_the_folder_path(self):
        cases = {
            'Validation/Enhanced_Validation/Valmont_Industries/Account/20260101/a.csv': 'Valmont_Industries',
            'Validation/GenAI_Validation/ValmontQA/Account/20260101/a.csv': 'ValmontQA',
            'Validation/HeraQA/Account/GenAIValidation/a.csv': 'HeraQA',
            'mapping_logs/AkashDev/Account/mapping.json': 'AkashDev',
            'DataLoader_Logs/dataload/Dataload_HeraQA/Account/Batches/a.csv': 'HeraQA',
            'DataFiles/ValmontQA/Account/a.csv': 'ValmontQA',
            'file_store/source/ValmontDev/Account/a.csv': 'ValmontDev',
            'Unit Testing Generates/ValmontQA/Account/t.json': 'ValmontQA',
            'file_store/output/migration_readiness/error_1.csv': None,
            'genai_validation_results/Account_invalid.csv': None,
            'Validation/GenAI_Validation/Unknown_Org/Account/a.csv': None,
        }
        for rel, org in cases.items():
            self.assertEqual(projects.org_from_path(os.path.join('C:\\any\\old\\install', *rel.split('/'))), org, rel)


class IndexRepairTests(_TempFiles):

    def test_moved_rows_are_repointed_duplicates_dropped_and_orgs_filled(self):
        root = os.path.join(self.tmp, 'install')
        new_file = os.path.join(root, 'Validation', 'GenAI_Validation', 'ValmontQA', 'Account', 'r.csv')
        moved = os.path.join(root, 'mapping_logs', 'AkashDev', 'Account', 'mapping.json')
        for path in (new_file, moved):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'w').write('x')
        fsm.initialize_db()
        with fsm._get_connection() as conn:
            rows = [(new_file, 'unknown'),                                                        # tag only
                    (r'C:\old\install\Validation\GenAI_Validation\ValmontQA\Account\r.csv', 'unknown'),  # duplicate
                    (r'C:\old\install\mapping_logs\AkashDev\Account\mapping.json', 'unknown'),     # re-point
                    (r'C:\old\install\Validation\gone.csv', 'unknown')]                            # stays missing
            conn.executemany("INSERT INTO output_files (original_name, stored_path, org_name, generated_at) "
                             "VALUES ('f', ?, ?, '2026-10-01')", rows)
            conn.commit()
        report = fsm.repair_index(root=root)
        self.assertEqual((report['relocated'], report['duplicates_removed'], report['orgs_tagged']), (1, 1, 2))
        self.assertTrue(os.path.exists(report['backup']))
        with sqlite3.connect(fsm.DB_PATH) as conn:
            got = dict(conn.execute("SELECT stored_path, org_name FROM output_files").fetchall())
        self.assertEqual(got[new_file], 'ValmontQA')
        self.assertEqual(got[moved], 'AkashDev')
        self.assertEqual(len(got), 3)
        self.assertEqual(report['missing'], 1)

    def test_repair_is_idempotent(self):
        root = os.path.join(self.tmp, 'install')
        fsm.initialize_db()
        first = fsm.repair_index(root=root)
        second = fsm.repair_index(root=root)
        self.assertEqual(second['relocated'] + second['duplicates_removed'] + second['orgs_tagged'], 0)
        self.assertIsNone(second['backup'], "nothing to change, no backup made")
        self.assertIsNotNone(first)


class FileLibraryScopeTests(_TempFiles):

    def setUp(self):
        super().setUp()
        projects.save_projects([VALMONT])
        self.add_file('source', 'ValmontQA', 'qa.csv')
        self.add_file('source', 'ValmontDev', 'dev.csv')
        self.add_file('source', 'AkashDev', 'akash.csv')
        self.add_file('source', 'ValmontQA', 'gone.csv', exists=False)
        self.add_file('output', 'Valmont_Industries', 'enhanced.csv')
        self.add_file('output', 'unknown', 'orphan.csv')

    def library(self, org=None):
        at = new_app()
        if org:
            at.sidebar.selectbox(key='global_org_selector').set_value(org).run()
        at.sidebar.radio(key='nav_page').set_value(FILE_LIBRARY).run()
        no_exceptions(self, at)
        return at

    def listed(self, at):
        return sorted({e.label.split('  [')[0].split(' ')[-1] for e in at.expander if '  [' in e.label})

    def test_project_scope_is_the_default_for_a_project_org(self):
        at = self.library('ValmontQA')
        self.assertEqual(at.radio(key='fl_scope').value, projects.SCOPE_PROJECT)
        self.assertEqual(self.listed(at), ['dev.csv', 'enhanced.csv', 'qa.csv'])
        self.assertIn('Project **Valmont**', " ".join(str(m.value) for m in list(at.markdown) + list(at.caption)))

    def test_this_org_only(self):
        at = self.library('ValmontQA')
        at.radio(key='fl_scope').set_value(projects.SCOPE_ORG).run()
        no_exceptions(self, at)
        self.assertEqual(self.listed(at), ['qa.csv'])

    def test_all_shows_everything_existing(self):
        at = self.library('ValmontQA')
        at.radio(key='fl_scope').set_value(projects.SCOPE_ALL).run()
        self.assertEqual(self.listed(at), ['akash.csv', 'dev.csv', 'enhanced.csv', 'orphan.csv', 'qa.csv'])

    def test_missing_files_are_hidden_and_counted(self):
        at = self.library('ValmontQA')
        self.assertNotIn('gone.csv', self.listed(at))
        self.assertTrue(any('not found on disk' in str(c.value) for c in at.caption))

    def test_org_without_a_project_defaults_to_this_org(self):
        at = self.library('AkashDev')
        self.assertEqual(at.radio(key='fl_scope').value, projects.SCOPE_ORG)
        self.assertEqual(self.listed(at), ['akash.csv'])
        self.assertTrue(any('Projects' in str(c.value) for c in at.caption))

    def test_no_org_selected_shows_all(self):
        at = self.library()
        self.assertEqual(at.radio(key='fl_scope').value, projects.SCOPE_ALL)

    def test_sidebar_names_the_project(self):
        at = self.library('ValmontQA')
        self.assertIn('Project: <b>Valmont</b>', " ".join(str(m.value) for m in at.sidebar.markdown))


class _Upload:
    """What st.file_uploader hands over (name + getbuffer())."""

    def __init__(self, name, data):
        self.name, self._data = name, data

    def getbuffer(self):
        return memoryview(self._data)


class UploadToProjectTests(_TempFiles):

    def setUp(self):
        super().setUp()
        projects.save_projects([VALMONT])

    def library(self, org):
        at = new_app()
        at.sidebar.selectbox(key='global_org_selector').set_value(org).run()
        at.sidebar.radio(key='nav_page').set_value(FILE_LIBRARY).run()
        no_exceptions(self, at)
        return at

    def test_upload_box_defaults_to_the_whole_project(self):
        at = self.library('ValmontQA')
        target = at.selectbox(key='fl_up_target')
        self.assertEqual(target.value, projects.WHOLE_PROJECT)
        self.assertEqual(list(target.options),
                         ['📁 Whole project (Valmont)', 'ValmontDev', 'ValmontQA', 'ValmontUAT'])
        self.assertTrue(at.button(key='fl_up_go').disabled, "nothing to upload yet")

    def test_org_without_a_project_uploads_to_that_org(self):
        at = self.library('AkashDev')
        self.assertNotIn('fl_up_target', {s.key for s in at.selectbox})
        self.assertTrue(any('Upload to AkashDev' in str(m.value) for m in at.markdown))

    def test_whole_project_upload_goes_to_the_project_folder_and_shows_in_the_project(self):
        from ui_components import file_library_ui
        saved = file_library_ui.upload_files([_Upload('accounts.csv', b'Name\nAcme\n')], 'Valmont', 'Account')
        self.assertEqual(len(saved), 1)
        row = fsm.list_source_files(org_names=['Valmont'])[0]
        self.assertEqual((row['original_name'], row['org_name'], row['object_name']), ('accounts.csv', 'Valmont', 'Account'))
        self.assertEqual(os.path.basename(os.path.dirname(row['stored_path'])), 'Account')
        self.assertEqual(os.path.basename(os.path.dirname(os.path.dirname(row['stored_path']))), 'Valmont')
        at = self.library('ValmontDev')   # any Valmont org shows project-wide files
        self.assertIn('accounts.csv', [e.label.split('  [')[0] for e in at.expander])

    def test_upload_for_one_org_of_the_project(self):
        from ui_components import file_library_ui
        file_library_ui.upload_files([_Upload('qa.csv', b'a\n1\n')], 'ValmontQA', '')
        rows = fsm.list_source_files(org_names=['ValmontQA'])
        self.assertEqual([r['original_name'] for r in rows], ['qa.csv'])
        self.assertIn(os.sep + 'ValmontQA' + os.sep, rows[0]['stored_path'])

    def test_uploading_the_same_file_twice_keeps_one_copy(self):
        from ui_components import file_library_ui
        for _ in range(2):
            file_library_ui.upload_files([_Upload('same.csv', b'a\n1\n')], 'Valmont', 'Account')
        self.assertEqual(len(fsm.list_source_files(org_names=['Valmont'])), 1)


class ProjectsTabTests(_TempFiles):

    def config(self):
        at = new_app()
        at.sidebar.radio(key='nav_page').set_value(CONFIG_PAGE).run()
        no_exceptions(self, at)
        return at

    def test_suggestion_creates_a_project_on_click(self):
        at = self.config()
        at.button(key='proj_suggest_Valmont').click().run()
        no_exceptions(self, at)
        self.assertEqual(projects.load_projects(),
                         [{'name': 'Valmont', 'orgs': ['ValmontDev', 'ValmontQA', 'ValmontUAT'], 'aliases': []}])

    def test_add_and_delete_a_project(self):
        at = self.config()
        at.text_input(key='proj_new_name').set_value('DTNA')
        at.multiselect(key='proj_new_orgs').set_value(['DTNA_QA', 'DTNA_UAT'])
        at.button(key='proj_add').click().run()
        no_exceptions(self, at)
        self.assertEqual([p['name'] for p in projects.load_projects()], ['DTNA'])
        at.button(key='proj_delete_DTNA').click().run()
        no_exceptions(self, at)
        self.assertEqual(projects.load_projects(), [])

    def test_an_org_can_be_in_only_one_project(self):
        projects.save_projects([VALMONT])
        at = self.config()
        at.text_input(key='proj_new_name').set_value('Other')
        self.assertNotIn('ValmontQA', at.multiselect(key='proj_new_orgs').options)


if __name__ == '__main__':
    unittest.main()
