"""
SQL Server connection strings and the "server unreachable" diagnosis.

Every screen builds its SQL Server connection string through
ui_components.sql_connection, so:
  * no `Connection Timeout=` keyword (ADO.NET, not ODBC: the driver rejects it with
    "Invalid connection string attribute" and the timeout never applies -- a 5 s
    timeout measured 41 s);
  * `tcp:host,port`, so an unreachable server fails over TCP instead of falling
    back to Named Pipes and reporting a misleading "Named Pipes Provider" error;
  * the login timeout goes to pyodbc as `timeout=`.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_sql_connection.py -v
"""
import glob
import os
import re
import socket
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for path in (ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

from ui_components import sql_connection  # noqa: E402

AZURE = {
    'server': 'myserver.database.windows.net', 'database': 'stage', 'driver': '{ODBC Driver 17 for SQL Server}',
    'port': '', 'encrypt': 'yes', 'trust_server_cert': False, 'connection_timeout': 30,
    'application_name': 'DM_Toolkit', 'mars_connection': False, 'username': 'u', 'password': 'p',
    'Trusted_Connection': 'no',
}


def cfg(**overrides):
    c = dict(AZURE)
    c.update(overrides)
    return c


def parts(cs):
    """'A=1;B=2' -> {'A': '1', 'B': '2'} (keys as written)."""
    return dict(p.split('=', 1) for p in cs.split(';') if p)


class ConnectionStringTests(unittest.TestCase):
    def test_no_ado_net_timeout_keyword(self):
        cs = sql_connection.build_connection_string(cfg(connection_timeout=5))
        self.assertNotIn('Connection Timeout', cs)
        self.assertNotIn('Connect Timeout', cs)

    def test_tcp_prefix_with_default_port(self):
        self.assertEqual(parts(sql_connection.build_connection_string(cfg(port='')))['SERVER'],
                         'tcp:myserver.database.windows.net,1433')

    def test_custom_port(self):
        self.assertEqual(parts(sql_connection.build_connection_string(cfg(port='14330')))['SERVER'],
                         'tcp:myserver.database.windows.net,14330')

    def test_port_already_in_server_is_kept(self):
        self.assertEqual(parts(sql_connection.build_connection_string(cfg(server='db1,1500', port='1433')))['SERVER'],
                         'tcp:db1,1500')

    def test_named_instance_is_left_to_sql_browser(self):
        self.assertEqual(parts(sql_connection.build_connection_string(cfg(server='db1\\SQLEXPRESS')))['SERVER'],
                         'db1\\SQLEXPRESS')

    def test_explicit_protocol_prefix_is_kept(self):
        for server in ('tcp:db1,1500', 'np:\\\\db1\\pipe\\sql\\query', 'lpc:db1'):
            self.assertEqual(parts(sql_connection.build_connection_string(cfg(server=server)))['SERVER'], server)

    def test_server_whitespace_is_stripped(self):
        self.assertEqual(parts(sql_connection.build_connection_string(cfg(server='  db1 ')))['SERVER'], 'tcp:db1,1433')

    def test_sql_authentication(self):
        p = parts(sql_connection.build_connection_string(cfg()))
        self.assertEqual((p['UID'], p['PWD']), ('u', 'p'))
        self.assertNotIn('Trusted_Connection', p)

    def test_windows_authentication(self):
        p = parts(sql_connection.build_connection_string(cfg(Trusted_Connection='yes')))
        self.assertEqual(p['Trusted_Connection'], 'yes')
        self.assertNotIn('UID', p)
        self.assertNotIn('PWD', p)

    def test_encrypt(self):
        self.assertEqual(parts(sql_connection.build_connection_string(cfg(encrypt='yes')))['Encrypt'], 'yes')
        self.assertNotIn('Encrypt', parts(sql_connection.build_connection_string(cfg(encrypt='no'))))

    def test_trust_server_certificate(self):
        self.assertEqual(parts(sql_connection.build_connection_string(cfg(trust_server_cert=True)))
                         ['TrustServerCertificate'], 'yes')
        self.assertNotIn('TrustServerCertificate', parts(sql_connection.build_connection_string(cfg())))

    def test_azure_with_an_old_driver_trusts_the_certificate(self):
        p = parts(sql_connection.build_connection_string(cfg(driver='{SQL Server}')))
        self.assertEqual(p['TrustServerCertificate'], 'yes')

    def test_application_name_and_mars(self):
        p = parts(sql_connection.build_connection_string(cfg(mars_connection=True)))
        self.assertEqual(p['APP'], 'DM_Toolkit')
        self.assertEqual(p['MARS_Connection'], 'yes')
        self.assertNotIn('MARS_Connection', parts(sql_connection.build_connection_string(cfg())))

    def test_driver_and_database(self):
        p = parts(sql_connection.build_connection_string(cfg()))
        self.assertEqual(p['DRIVER'], '{ODBC Driver 17 for SQL Server}')
        self.assertEqual(p['DATABASE'], 'stage')

    def test_login_timeout(self):
        self.assertEqual(sql_connection.login_timeout(cfg(connection_timeout=15)), 15)
        self.assertEqual(sql_connection.login_timeout(cfg(connection_timeout='20')), 20)
        self.assertEqual(sql_connection.login_timeout(cfg(connection_timeout=None)), 30)
        self.assertEqual(sql_connection.login_timeout({}), 30)


class EveryScreenUsesTheSharedBuilderTests(unittest.TestCase):
    """The six hand-rolled builders drifted apart; only one had the fixes above."""

    def _sources(self):
        for path in glob.glob(os.path.join(ROOT, 'ui_components', '*.py')):
            if os.path.basename(path) == 'sql_connection.py':
                continue
            with open(path, encoding='utf-8') as f:
                yield os.path.basename(path), f.read()

    def test_no_screen_builds_its_own_connection_string(self):
        offenders = [name for name, src in self._sources() if re.search(r'f"DRIVER=\{', src)]
        self.assertEqual(offenders, [])

    def test_no_screen_sends_connection_timeout(self):
        offenders = [name for name, src in self._sources() if 'Connection Timeout=' in src]
        self.assertEqual(offenders, [])

    def test_every_pyodbc_connect_passes_a_login_timeout(self):
        offenders = []
        for name, src in self._sources():
            for call in re.findall(r'pyodbc\.connect\(([^)]*)\)', src):
                if 'timeout=' not in call:
                    offenders.append(f"{name}: pyodbc.connect({call})")
        self.assertEqual(offenders, [])


def _closed_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class NetworkDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(5)
        self.open_port = self.listener.getsockname()[1]

    def tearDown(self):
        self.listener.close()

    def test_reachable_port_has_no_network_diagnosis(self):
        self.assertIsNone(sql_connection.network_diagnosis({'server': '127.0.0.1', 'port': str(self.open_port)},
                                                           timeout=2))

    def test_port_blocked_but_host_answers_on_https(self):
        closed = _closed_port()
        msg = sql_connection.network_diagnosis({'server': '127.0.0.1', 'port': str(closed)},
                                               timeout=2, control_port=self.open_port)
        self.assertIn(f'port {closed}', msg)
        self.assertIn('blocked', msg)
        self.assertIn('VPN', msg)

    def test_host_does_not_answer_at_all(self):
        closed = _closed_port()
        msg = sql_connection.network_diagnosis({'server': '127.0.0.1', 'port': str(closed)},
                                               timeout=2, control_port=_closed_port())
        self.assertIn('not reachable', msg)
        self.assertNotIn('blocked', msg)

    def test_name_that_does_not_resolve(self):
        msg = sql_connection.network_diagnosis({'server': 'no-such-host.invalid', 'port': '1433'}, timeout=2)
        self.assertIn('no-such-host.invalid', msg)
        self.assertIn('DNS', msg)

    def test_port_comes_from_the_server_field_or_defaults_to_1433(self):
        self.assertEqual(sql_connection.server_host_port({'server': 'tcp:db1,1500', 'port': '1433'}), ('db1', 1500))
        self.assertEqual(sql_connection.server_host_port({'server': 'db1', 'port': ''}), ('db1', 1433))
        self.assertEqual(sql_connection.server_host_port({'server': 'db1', 'port': '14330'}), ('db1', 14330))

    def test_named_instance_is_not_probed(self):
        # The instance's port comes from SQL Browser (UDP 1434); probing 1433 would mislead.
        self.assertIsNone(sql_connection.server_host_port({'server': 'db1\\SQLEXPRESS', 'port': '1433'}))
        self.assertIsNone(sql_connection.network_diagnosis({'server': 'db1\\SQLEXPRESS', 'port': '1433'}, timeout=2))


if __name__ == '__main__':
    unittest.main()
