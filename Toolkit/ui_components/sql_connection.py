"""
SQL Server connection strings for every screen, and a plain-words diagnosis
when the server cannot be reached.

One builder, because the six hand-rolled copies drifted apart:
  * `Connection Timeout=` is an ADO.NET keyword, not an ODBC one. The ODBC driver
    answers it with "Invalid connection string attribute" and ignores it, so the
    configured timeout never applied (a 5 s timeout measured 41 s). The login
    timeout goes to pyodbc as `timeout=` instead -- see login_timeout().
  * A bare host name lets the driver fall back from TCP to Named Pipes, and the
    error then reports the Named Pipes attempt ("Named Pipes Provider ... (64)"),
    which hides that TCP port 1433 was the thing that failed. `tcp:host,port`
    pins the protocol.
"""
import socket
from typing import Dict, Optional, Tuple

DEFAULT_PORT = 1433
DEFAULT_LOGIN_TIMEOUT = 30

# Drivers that predate Azure SQL's certificate chain / TLS 1.2 defaults.
_LEGACY_DRIVERS = ('odbc driver 13', 'odbc driver 11', 'native client')


def resolve_driver(driver_setting: str) -> str:
    """
    Resolve driver string. If 'Auto-detect', pick the best installed SQL Server driver.
    Priority: ODBC 18 > 17 > 13 > Native Client > SQL Server
    """
    if driver_setting and driver_setting != 'Auto-detect (recommended)':
        return driver_setting
    try:
        import pyodbc
        installed = [d for d in pyodbc.drivers() if 'sql server' in d.lower() or 'sql native' in d.lower()]
        priority = [
            'ODBC Driver 18 for SQL Server',
            'ODBC Driver 17 for SQL Server',
            'ODBC Driver 13 for SQL Server',
            'SQL Server Native Client 11.0',
            'SQL Server',
        ]
        for preferred in priority:
            for d in installed:
                if preferred.lower() in d.lower():
                    return '{' + d + '}' if not d.startswith('{') else d
        if installed:
            d = installed[0]
            return '{' + d + '}' if not d.startswith('{') else d
    except Exception:
        pass
    return '{ODBC Driver 17 for SQL Server}'


def _is_legacy_driver(driver: str) -> bool:
    name = driver.strip('{} ').lower()
    return name == 'sql server' or any(tag in name for tag in _LEGACY_DRIVERS)


def _server_value(db_cfg: Dict) -> str:
    """SERVER= value: `tcp:host,port`, unless the user chose a protocol or a named instance."""
    server = str(db_cfg.get('server') or '').strip()
    if server.lower().startswith(('tcp:', 'np:', 'lpc:')) or '\\' in server:
        return server
    if ',' in server:  # port already given as "host,port"
        return f"tcp:{server}"
    port = str(db_cfg.get('port') or DEFAULT_PORT).strip()
    return f"tcp:{server},{port}"


def build_connection_string(db_cfg: Dict) -> str:
    """ODBC connection string for a saved SQL Server connection (linkedservices.json entry)."""
    driver = resolve_driver(db_cfg.get('driver', 'Auto-detect (recommended)'))
    cs = f"DRIVER={driver};SERVER={_server_value(db_cfg)};DATABASE={db_cfg['database']}"

    if db_cfg.get('Trusted_Connection') == 'yes':
        cs += ";Trusted_Connection=yes"
    else:
        cs += f";UID={db_cfg['username']};PWD={db_cfg['password']}"

    encrypt_val = db_cfg.get('encrypt', 'no')
    if encrypt_val and str(encrypt_val).lower() not in ('no', 'false', ''):
        cs += f";Encrypt={encrypt_val}"

    # TrustServerCertificate: explicit setting, or Azure SQL through a legacy driver.
    is_azure = '.database.windows.net' in str(db_cfg.get('server', ''))
    if db_cfg.get('trust_server_cert', False) or (is_azure and _is_legacy_driver(driver)):
        cs += ";TrustServerCertificate=yes"

    if db_cfg.get('application_name'):
        cs += f";APP={db_cfg['application_name']}"
    if db_cfg.get('mars_connection'):
        cs += ";MARS_Connection=yes"
    return cs


def login_timeout(db_cfg: Dict) -> int:
    """Seconds to wait for the login: pass as pyodbc.connect(..., timeout=) or connect_args={'timeout': ...}."""
    try:
        return int(db_cfg.get('connection_timeout') or DEFAULT_LOGIN_TIMEOUT)
    except (TypeError, ValueError):
        return DEFAULT_LOGIN_TIMEOUT


# ─────────────────────────────────────────────────────────────────────────────
# "Server not reachable" -- say which layer failed
# ─────────────────────────────────────────────────────────────────────────────

_NETWORK_MARKERS = ('08001', 'hyt00', 'network-related', 'server was not found', 'tcp provider',
                    'named pipes provider', 'timeout expired', 'timed out')


def is_network_error(message: str) -> bool:
    """True for "could not reach the server" failures (not login, firewall-rule or SSL errors)."""
    text = str(message or '').lower()
    return any(marker in text for marker in _NETWORK_MARKERS)


def server_host_port(db_cfg: Dict) -> Optional[Tuple[str, int]]:
    """(host, TCP port) the driver will dial, or None when it is not a plain TCP address."""
    server = str(db_cfg.get('server') or '').strip()
    if server.lower().startswith(('np:', 'lpc:')):
        return None
    if server.lower().startswith('tcp:'):
        server = server[4:]
    if '\\' in server:  # named instance: SQL Browser (UDP 1434) supplies the port
        return None
    host, _, port = server.partition(',')
    port = port.strip() or str(db_cfg.get('port') or '').strip() or str(DEFAULT_PORT)
    try:
        return host.strip(), int(port)
    except ValueError:
        return None


def _tcp_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def network_diagnosis(db_cfg: Dict, timeout: float = 3.0, control_port: int = 443) -> Optional[str]:
    """
    Why the SQL Server port cannot be reached, in one sentence -- or None when it can
    (then the failure is not the network). Probes the SQL port, and the HTTPS port of
    the same host as a control: if HTTPS answers and the SQL port does not, the host
    is there and something between here and it blocks the SQL port.
    """
    target = server_host_port(db_cfg)
    if target is None:
        return None
    host, port = target
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return (f"The server name {host} does not resolve (DNS lookup failed). Check the server address, "
                f"or connect the VPN if it is a private name.")
    if _tcp_open(host, port, timeout):
        return None
    if control_port and control_port != port and _tcp_open(host, control_port, timeout):
        return (f"{host} answers on port {control_port} but port {port} is blocked from this machine: the "
                f"network (Wi-Fi, office firewall or proxy) is not letting SQL Server traffic out. Connect the "
                f"VPN, or use a network that allows outbound TCP {port}, then test again.")
    return (f"{host} is not reachable on TCP port {port} from this machine. Check the server address, that "
            f"SQL Server is running and listening on port {port}, and that this network / VPN can reach it.")
