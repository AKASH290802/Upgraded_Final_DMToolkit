"""Keep AppTest runs out of the project's real File Library.

Every entry script calls isolate_file_library() before streamlit_app.main().
It points file_store_manager's DB and stores at a temp folder whenever they
still point at the real project paths (test_other_screens.tearDownModule may
restore them between test modules, so this is re-checked on every run).
"""
import atexit
import json
import os
import shutil
import tempfile

_TEMP_DIRS = []

# Fake connections the tests use. The tests never read or write the real
# Services/linkedservices.json (real passwords, and a test that saves or deletes a
# connection would change the user's file).
TEST_CREDENTIALS = {
    'AkashDev': {'username': 'tester@example.com', 'password': 'not-a-password', 'security_token': 'x',
                 'domain': 'login'},
    'FCS': {'username': 'tester2@example.com', 'password': 'not-a-password', 'security_token': 'x',
            'domain': 'test'},
    'DEv': {'username': 'tester3@example.com', 'password': 'not-a-password', 'security_token': 'x',
            'domain': 'login'},
    'sql_SQL Server': {'server': 'sql-test.example.local', 'database': 'TestDb', 'driver': 'Auto-detect (recommended)',
                       'port': '', 'encrypt': 'yes', 'trust_server_cert': False, 'connection_timeout': 30,
                       'command_timeout': 300, 'username': 'tester', 'password': 'not-a-password',
                       'Trusted_Connection': 'no'},
    'openai_config': {'provider': 'azure', 'azure_openai_endpoint': '', 'gpt4o_api_key': '', 'embed_api_key': ''},
}


def use_test_credentials() -> str:
    """Point the app at a throw-away linkedservices.json with TEST_CREDENTIALS (once per process).

    connection_manager.credentials_path() reads DM_TOOLKIT_CREDENTIALS; a test that sets it
    to its own file (test_delete_connections) restores this one afterwards.
    """
    from ui_components import connection_manager as cm
    current = os.environ.get(cm.CREDENTIALS_ENV)
    if current and os.path.exists(current):
        return current
    folder = tempfile.mkdtemp(prefix="dm_toolkit_apptest_credentials_")
    _TEMP_DIRS.append(folder)
    path = os.path.join(folder, 'linkedservices.json')
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(TEST_CREDENTIALS, handle, indent=2)
    os.environ[cm.CREDENTIALS_ENV] = path
    return path


def use_test_projects() -> str:
    """Point the app at a throw-away projects.json with no projects (never Services/projects.json).

    A test that needs projects writes them to os.environ[DM_TOOLKIT_PROJECTS] (or points the
    variable at its own file and restores it afterwards, as test_projects does).
    """
    from ui_components import projects
    current = os.environ.get(projects.PROJECTS_ENV)
    if current and os.path.exists(current):
        return current
    folder = tempfile.mkdtemp(prefix="dm_toolkit_apptest_projects_")
    _TEMP_DIRS.append(folder)
    path = os.path.join(folder, 'projects.json')
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump({'projects': []}, handle)
    os.environ[projects.PROJECTS_ENV] = path
    return path


def isolate_file_library() -> None:
    use_test_credentials()
    use_test_projects()
    from ui_components import file_store_manager as fsm
    from ui_components import validation_operations
    # Validation result files (Schema / Enhanced / ...) go to a temp folder too.
    if not getattr(validation_operations.get_validation_folder_path, '_apptest', False):
        validation_root = tempfile.mkdtemp(prefix="dm_toolkit_apptest_validation_")
        _TEMP_DIRS.append(validation_root)

        def _temp_validation_folder(validation_type, org_name=None, object_name=None):
            folder = os.path.join(validation_root, validation_type, org_name or '_', object_name or '_')
            os.makedirs(folder, exist_ok=True)
            return folder

        _temp_validation_folder._apptest = True
        validation_operations.get_validation_folder_path = _temp_validation_folder

    tmp = getattr(fsm, '_apptest_tmp', None)
    if tmp and os.path.isdir(tmp) and fsm.DB_PATH.startswith(tmp):
        return
    fsm._apptest_saved_paths = (fsm.DB_PATH, fsm.SOURCE_STORE, fsm.OUTPUT_STORE)
    fsm._apptest_tmp = tempfile.mkdtemp(prefix="dm_toolkit_apptest_")
    _TEMP_DIRS.append(fsm._apptest_tmp)
    fsm.DB_PATH = os.path.join(fsm._apptest_tmp, 'files.db')
    fsm.SOURCE_STORE = os.path.join(fsm._apptest_tmp, 'file_store', 'source')
    fsm.OUTPUT_STORE = os.path.join(fsm._apptest_tmp, 'file_store', 'output')


@atexit.register
def _cleanup() -> None:
    for path in _TEMP_DIRS:
        shutil.rmtree(path, ignore_errors=True)
