"""
file_store_manager.py
SQLite-backed file registry for DM Toolkit.
- Source files are physically copied into file_store/source/ for persistence.
- Output files are registered in-place (not copied) since they live in their
  own directories (Validation/, genai_validation_results/, etc.)
"""

import hashlib
import sqlite3
import os
import shutil
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'dm_toolkit_files.db')
SOURCE_STORE = os.path.join(PROJECT_ROOT, 'file_store', 'source')
OUTPUT_STORE = os.path.join(PROJECT_ROOT, 'file_store', 'output')


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    """Create tables and storage directories if they do not exist."""
    os.makedirs(SOURCE_STORE, exist_ok=True)
    os.makedirs(OUTPUT_STORE, exist_ok=True)
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_files (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                original_name TEXT    NOT NULL,
                stored_path   TEXT    NOT NULL UNIQUE,
                org_name      TEXT    DEFAULT 'unknown',
                object_name   TEXT    DEFAULT '',
                file_size     INTEGER DEFAULT 0,
                row_count     INTEGER DEFAULT 0,
                col_count     INTEGER DEFAULT 0,
                file_type     TEXT    DEFAULT '',
                uploaded_at   TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS output_files (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                original_name  TEXT    NOT NULL,
                stored_path    TEXT    NOT NULL UNIQUE,
                org_name       TEXT    DEFAULT 'unknown',
                object_name    TEXT    DEFAULT '',
                operation_type TEXT    DEFAULT '',
                file_size      INTEGER DEFAULT 0,
                row_count      INTEGER DEFAULT 0,
                status         TEXT    DEFAULT '',
                source_file_id INTEGER,
                generated_at   TEXT    NOT NULL,
                FOREIGN KEY (source_file_id) REFERENCES source_files(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_name   TEXT    NOT NULL,
                direction       TEXT    NOT NULL,
                source_label    TEXT    DEFAULT '',
                target_label    TEXT    DEFAULT '',
                object_name     TEXT    DEFAULT '',
                table_name      TEXT    DEFAULT '',
                operation       TEXT    DEFAULT '',
                status          TEXT    DEFAULT 'pending',
                records_success INTEGER DEFAULT 0,
                records_failed  INTEGER DEFAULT 0,
                error_message   TEXT    DEFAULT '',
                config_json     TEXT    DEFAULT '{}',
                started_at      TEXT    NOT NULL,
                finished_at     TEXT    DEFAULT ''
            )
        """)
        # One row per validation run (Step 2), for the Validation Summary history.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS validation_runs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at    TEXT    NOT NULL,
                org_name      TEXT    DEFAULT 'unknown',
                object_name   TEXT    DEFAULT '',
                method        TEXT    DEFAULT '',
                total         INTEGER DEFAULT 0,
                valid         INTEGER DEFAULT 0,
                invalid       INTEGER DEFAULT 0,
                mapped_fields INTEGER DEFAULT 0,
                source        TEXT    DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_validation_runs_org_object "
                     "ON validation_runs(org_name, object_name, created_at)")
        # content_hash (SHA-256 of the file bytes) lets register_source_file skip
        # re-registering the same upload. Added to existing databases in place.
        source_cols = {row[1] for row in conn.execute("PRAGMA table_info(source_files)")}
        if 'content_hash' not in source_cols:
            conn.execute("ALTER TABLE source_files ADD COLUMN content_hash TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source_files_content_hash "
                     "ON source_files(content_hash)")
        conn.commit()


def register_source_file(source, original_name, org_name='unknown', object_name='',
                          row_count=0, col_count=0):
    """
    Save a source file to file_store/source/ and register it in SQLite.

    Parameters
    ----------
    source : Streamlit UploadedFile, bytes/bytearray, or str (file path)
    original_name : str  — display name (e.g. uploaded_file.name)
    org_name, object_name : str — metadata labels
    row_count, col_count  : int — optional DataFrame dimensions

    Returns
    -------
    int  file_id on success, or None on failure

    Idempotent: registering the same bytes again for the same org, object and
    original name returns the existing file_id without copying the file again
    (callers run this on every Streamlit rerun while a file is in an uploader).
    """
    initialize_db()

    # Read the content once to fingerprint it (paths are hashed in chunks).
    data = None
    try:
        if hasattr(source, 'getbuffer'):
            # Streamlit UploadedFile: a view of its bytes (no copy - an upload can be 1 GB)
            data = source.getbuffer()
        elif isinstance(source, (bytes, bytearray)):
            data = bytes(source)
        elif isinstance(source, str) and os.path.exists(source):
            data = None
        else:
            return None
        if data is not None:
            content_hash = hashlib.sha256(data).hexdigest()
        else:
            content_hash = _hash_file(source)
    except Exception:
        return None

    org_value = org_name or 'unknown'
    obj_value = object_name or ''
    existing_id = _find_registered_source(content_hash, org_value, obj_value, original_name)
    if existing_id is not None:
        if row_count or col_count:
            try:
                with _get_connection() as conn:
                    conn.execute(
                        """UPDATE source_files
                           SET row_count = CASE WHEN ? > 0 THEN ? ELSE row_count END,
                               col_count = CASE WHEN ? > 0 THEN ? ELSE col_count END
                           WHERE id = ?""",
                        (row_count, row_count, col_count, col_count, existing_id))
                    conn.commit()
            except Exception:
                pass
        return existing_id

    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    org_slug = (org_name or 'unknown').replace(' ', '_')
    obj_slug = (object_name or 'general').replace(' ', '_')
    org_dir = os.path.join(SOURCE_STORE, org_slug, obj_slug)
    os.makedirs(org_dir, exist_ok=True)

    stored_name = f"{ts}_{original_name}"
    stored_path = os.path.join(org_dir, stored_name)

    try:
        # Write the file bytes to disk
        if data is not None:
            with open(stored_path, 'wb') as f:
                f.write(data)
        else:
            shutil.copy2(source, stored_path)

        file_size = os.path.getsize(stored_path)
        file_type = os.path.splitext(original_name)[1].lower()
        uploaded_at = datetime.now().isoformat()

        with _get_connection() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO source_files
                   (original_name, stored_path, org_name, object_name,
                    file_size, row_count, col_count, file_type, uploaded_at,
                    content_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (original_name, stored_path, org_value,
                 obj_value, file_size, row_count, col_count,
                 file_type, uploaded_at, content_hash)
            )
            conn.commit()
            return cursor.lastrowid

    except Exception:
        return None


def _find_registered_source(content_hash, org_name, object_name, original_name):
    """id of an already registered copy of this content whose file still exists, else None."""
    try:
        with _get_connection() as conn:
            rows = conn.execute(
                """SELECT id, stored_path FROM source_files
                   WHERE content_hash = ? AND org_name = ? AND object_name = ?
                     AND original_name = ?
                   ORDER BY id DESC""",
                (content_hash, org_name, object_name, original_name)
            ).fetchall()
    except Exception:
        return None
    for row in rows:
        if row['stored_path'] and os.path.exists(row['stored_path']):
            return row['id']
    return _match_legacy_source(content_hash, org_name, object_name, original_name)


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _match_legacy_source(content_hash, org_name, object_name, original_name):
    """Rows registered before content_hash existed: hash their stored file once
    (the hash is saved), and return the id of one with the same content."""
    try:
        with _get_connection() as conn:
            rows = conn.execute(
                """SELECT id, stored_path FROM source_files
                   WHERE content_hash IS NULL AND org_name = ? AND object_name = ?
                     AND original_name = ?
                   ORDER BY id DESC""",
                (org_name, object_name, original_name)
            ).fetchall()
            match = None
            for row in rows:
                path = row['stored_path']
                if not path or not os.path.exists(path):
                    continue
                file_hash = _hash_file(path)
                conn.execute("UPDATE source_files SET content_hash = ? WHERE id = ?",
                             (file_hash, row['id']))
                if match is None and file_hash == content_hash:
                    match = row['id']
            conn.commit()
            return match
    except Exception:
        return None


def register_output_file(file_path, original_name=None, org_name='unknown',
                          object_name='', operation_type='', row_count=0,
                          status='', source_file_id=None):
    """
    Register a generated output file (stays in its current location).

    Parameters
    ----------
    file_path      : str — absolute path to the file on disk
    original_name  : str — display name (defaults to basename)
    org_name, object_name, operation_type : str — metadata labels
    row_count      : int — optional record count
    status         : str — e.g. 'pass', 'fail', 'mixed'
    source_file_id : int — FK to source_files if known

    Returns
    -------
    int  file_id on success, or None on failure
    """
    initialize_db()

    if not file_path or not os.path.exists(file_path):
        return None

    try:
        file_size = os.path.getsize(file_path)
        name = original_name or os.path.basename(file_path)
        generated_at = datetime.now().isoformat()

        with _get_connection() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO output_files
                   (original_name, stored_path, org_name, object_name,
                    operation_type, file_size, row_count, status,
                    source_file_id, generated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, file_path, org_name or 'unknown', object_name or '',
                 operation_type or '', file_size, row_count, status or '',
                 source_file_id, generated_at)
            )
            conn.commit()
            return cursor.lastrowid

    except Exception:
        return None


def list_source_files(org_name=None, object_name=None, limit=300, org_names=None):
    """Return list of source file dicts, newest first.

    org_names: only files filed under one of these orgs (a project's orgs and aliases).
    """
    initialize_db()
    query = "SELECT * FROM source_files WHERE 1=1"
    params = []
    if org_name:
        query += " AND org_name = ?"
        params.append(org_name)
    if org_names is not None:
        query += f" AND org_name IN ({','.join('?' * len(org_names)) or 'NULL'})"
        params.extend(org_names)
    if object_name:
        query += " AND object_name = ?"
        params.append(object_name)
    query += " ORDER BY uploaded_at DESC LIMIT ?"
    params.append(limit)

    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def list_output_files(org_name=None, object_name=None, operation_type=None, limit=300, org_names=None):
    """Return list of output file dicts, newest first (org_names: see list_source_files)."""
    initialize_db()
    query = "SELECT * FROM output_files WHERE 1=1"
    params = []
    if org_name:
        query += " AND org_name = ?"
        params.append(org_name)
    if org_names is not None:
        query += f" AND org_name IN ({','.join('?' * len(org_names)) or 'NULL'})"
        params.extend(org_names)
    if object_name:
        query += " AND object_name = ?"
        params.append(object_name)
    if operation_type:
        query += " AND operation_type = ?"
        params.append(operation_type)
    query += " ORDER BY generated_at DESC LIMIT ?"
    params.append(limit)

    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def save_validation_run(org_name, object_name, method, total, valid, invalid,
                        mapped_fields=0, source='', created_at=None):
    """Record one Step 2 validation run. Returns its id (None if it could not be saved)."""
    initialize_db()
    try:
        with _get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO validation_runs (created_at, org_name, object_name, method, total,
                                                valid, invalid, mapped_fields, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (created_at or datetime.now().isoformat(timespec='seconds'), org_name or 'unknown',
                 object_name or '', method or '', int(total or 0), int(valid or 0), int(invalid or 0),
                 int(mapped_fields or 0), source or ''))
            conn.commit()
            return cursor.lastrowid
    except Exception:
        return None


def list_validation_runs(org_name=None, object_name=None, method=None, limit=500):
    """Validation runs, newest first."""
    initialize_db()
    query = "SELECT * FROM validation_runs WHERE 1=1"
    params = []
    for column, value in (('org_name', org_name), ('object_name', object_name), ('method', method)):
        if value:
            query += f" AND {column} = ?"
            params.append(value)
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def delete_source_file(file_id):
    """Delete a source file record and its stored copy on disk."""
    initialize_db()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT stored_path FROM source_files WHERE id = ?", (file_id,)
        ).fetchone()
        if row:
            try:
                if os.path.exists(row['stored_path']):
                    os.remove(row['stored_path'])
            except Exception:
                pass
            conn.execute("DELETE FROM source_files WHERE id = ?", (file_id,))
            conn.commit()
            return True
    return False


def delete_output_file(file_id):
    """Delete an output file record and the file on disk."""
    initialize_db()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT stored_path FROM output_files WHERE id = ?", (file_id,)
        ).fetchone()
        if row:
            try:
                if os.path.exists(row['stored_path']):
                    os.remove(row['stored_path'])
            except Exception:
                pass
            conn.execute("DELETE FROM output_files WHERE id = ?", (file_id,))
            conn.commit()
            return True
    return False


def get_file_stats():
    """Return summary statistics for display in the File Library header."""
    initialize_db()
    with _get_connection() as conn:
        source_count = conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
        output_count = conn.execute("SELECT COUNT(*) FROM output_files").fetchone()[0]
        source_size  = conn.execute("SELECT COALESCE(SUM(file_size), 0) FROM source_files").fetchone()[0]
        output_size  = conn.execute("SELECT COALESCE(SUM(file_size), 0) FROM output_files").fetchone()[0]
        org_rows     = conn.execute("SELECT COUNT(DISTINCT org_name) FROM source_files").fetchone()[0]
    return {
        'source_count':   source_count,
        'output_count':   output_count,
        'source_size_mb': round(source_size  / (1024 * 1024), 2),
        'output_size_mb': round(output_size  / (1024 * 1024), 2),
        'org_count':      org_rows,
    }


def scan_and_register_existing():
    """
    Scan known output/source directories and register files not yet tracked.
    Safe to call on every startup — known paths are skipped. Uses one connection,
    one lookup of the known paths and batched inserts (it used to open a connection
    and run a query per file on disk).
    Returns the count of newly registered files.
    """
    initialize_db()
    output_dirs = {
        'genai_validation_results': 'GenAI Validation',
        'Validation':               'Validation',
        'mapping_logs':             'Mapping',
        'DataLoader_Logs':          'Data Load',
    }
    datafiles_dir = os.path.join(PROJECT_ROOT, 'DataFiles')

    with _get_connection() as conn:
        known_outputs = {row[0] for row in conn.execute("SELECT stored_path FROM output_files")}
        known_sources = {row[0] for row in conn.execute("SELECT stored_path FROM source_files")}

        new_outputs = []
        for rel_dir, op_type in output_dirs.items():
            abs_dir = os.path.join(PROJECT_ROOT, rel_dir)
            if not os.path.exists(abs_dir):
                continue
            for root, dirs, files in os.walk(abs_dir):
                for fname in files:
                    if fname.startswith('~$') or not fname.endswith(('.csv', '.xlsx', '.xls', '.json', '.psv')):
                        continue
                    fpath = os.path.join(root, fname)
                    if fpath in known_outputs:
                        continue
                    known_outputs.add(fpath)
                    # Try to infer object name from filename prefix
                    obj = fname.split('_')[0] if '_' in fname else ''
                    org = _org_from_path(fpath) or 'unknown'
                    new_outputs.append((fname, fpath, org, obj, op_type, os.path.getsize(fpath), 0,
                                        'existing', datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()))

        new_sources = []
        if os.path.exists(datafiles_dir):
            for root, dirs, files in os.walk(datafiles_dir):
                for fname in files:
                    if fname.startswith('~$') or not fname.lower().endswith(
                            ('.csv', '.xlsx', '.xls', '.psv', '.txt', '.json')):
                        continue
                    fpath = os.path.join(root, fname)
                    if fpath in known_sources:
                        continue
                    known_sources.add(fpath)
                    parts = os.path.relpath(fpath, datafiles_dir).replace(os.sep, '/').split('/')
                    org = parts[0] if len(parts) > 0 else 'unknown'
                    obj = parts[1] if len(parts) > 1 else ''
                    new_sources.append((fname, fpath, org, obj, os.path.getsize(fpath), 0, 0,
                                        os.path.splitext(fname)[1].lower(),
                                        datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()))

        if new_outputs:
            conn.executemany(
                """INSERT OR IGNORE INTO output_files
                   (original_name, stored_path, org_name, object_name,
                    operation_type, file_size, row_count, status, generated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", new_outputs)
        if new_sources:
            conn.executemany(
                """INSERT OR IGNORE INTO source_files
                   (original_name, stored_path, org_name, object_name,
                    file_size, row_count, col_count, file_type, uploaded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", new_sources)
        conn.commit()
    return len(new_outputs) + len(new_sources)


def _org_from_path(path):
    try:
        from ui_components.projects import org_from_path
    except ImportError:
        from projects import org_from_path
    return org_from_path(path)


_INDEXED_TOP_FOLDERS = ('file_store', 'Validation', 'DataFiles', 'DataLoader_Logs', 'mapping_logs',
                        'genai_validation_results', 'Unit Testing Generates')


def _path_under(root, stored_path):
    """Where a file indexed under an OLD install folder is now: the same path from its top
    folder (Validation, DataFiles, ...) under root. None when the path has no known top folder."""
    parts = [p for p in stored_path.replace('/', '\\').split('\\') if p]
    tops = {t.lower() for t in _INDEXED_TOP_FOLDERS}
    i = next((n for n, part in enumerate(parts) if part.lower() in tops), None)
    return os.path.join(root, *parts[i:]) if i is not None else None


def repair_index(root=None):
    """Repair the File Library index (files on disk are never touched).

    - a row whose file is gone but exists at the same place under root (the app folder moved,
      e.g. from C:\\DM_toolkit) is re-pointed there, or dropped when that file is already indexed;
    - the org of every 'unknown' row is read from its folder path (projects.org_from_path);
    - a copy of the index is saved next to it first (only when something changes).
    Returns {'relocated', 'duplicates_removed', 'orgs_tagged', 'missing', 'backup'}.
    """
    root = root or PROJECT_ROOT
    initialize_db()
    report = {'relocated': 0, 'duplicates_removed': 0, 'orgs_tagged': 0, 'missing': 0, 'backup': None}
    deletes, moves, tags = [], [], []
    with _get_connection() as conn:
        for table in ('source_files', 'output_files'):
            rows = conn.execute(f"SELECT id, stored_path, org_name FROM {table}").fetchall()
            indexed = {r['stored_path'].lower() for r in rows if os.path.exists(r['stored_path'])}
            for r in rows:
                path = r['stored_path']
                if not os.path.exists(path):
                    candidate = _path_under(root, path)
                    if not candidate or not os.path.exists(candidate):
                        report['missing'] += 1
                        continue
                    if candidate.lower() in indexed:
                        deletes.append((table, r['id']))
                        report['duplicates_removed'] += 1
                        continue
                    moves.append((table, r['id'], candidate))
                    indexed.add(candidate.lower())
                    report['relocated'] += 1
                    path = candidate
                if (r['org_name'] or '').strip().lower() in ('', 'unknown', 'unknown_org', 'none'):
                    org = _org_from_path(path)
                    if org:
                        tags.append((table, r['id'], org))
                        report['orgs_tagged'] += 1
        if not (deletes or moves or tags):
            return report
        backup = f"{DB_PATH}.backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        conn.commit()
        with sqlite3.connect(backup) as copy:
            conn.backup(copy)
        report['backup'] = backup
        for table, row_id in deletes:
            conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        for table, row_id, new_path in moves:
            conn.execute(f"UPDATE {table} SET stored_path = ? WHERE id = ?", (new_path, row_id))
        for table, row_id, org in tags:
            conn.execute(f"UPDATE {table} SET org_name = ? WHERE id = ?", (org, row_id))
        conn.commit()
    return report


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline run persistence
# ─────────────────────────────────────────────────────────────────────────────

def save_pipeline_run(pipeline_name, direction, source_label, target_label,
                      object_name, table_name, operation, status,
                      records_success, records_failed, error_message, config_dict,
                      started_at, finished_at=''):
    """Persist a pipeline run record. Returns the new run id."""
    initialize_db()
    import json as _json
    config_json = _json.dumps(config_dict or {})
    with _get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO pipeline_runs
               (pipeline_name, direction, source_label, target_label,
                object_name, table_name, operation, status,
                records_success, records_failed, error_message,
                config_json, started_at, finished_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pipeline_name, direction, source_label, target_label,
             object_name, table_name, operation, status,
             records_success, records_failed, error_message,
             config_json, started_at, finished_at)
        )
        conn.commit()
        return cursor.lastrowid


def update_pipeline_run(run_id, status, records_success, records_failed,
                        error_message='', finished_at=''):
    """Update an existing pipeline run after completion."""
    initialize_db()
    with _get_connection() as conn:
        conn.execute(
            """UPDATE pipeline_runs
               SET status=?, records_success=?, records_failed=?,
                   error_message=?, finished_at=?
               WHERE id=?""",
            (status, records_success, records_failed, error_message, finished_at, run_id)
        )
        conn.commit()


def list_pipeline_runs(limit=100):
    """Return all pipeline runs, newest first."""
    initialize_db()
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_pipeline_run(run_id):
    """Return a single pipeline run dict by id."""
    initialize_db()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pipeline_runs WHERE id=?", (run_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_pipeline_run(run_id):
    """Delete a pipeline run record."""
    initialize_db()
    with _get_connection() as conn:
        conn.execute("DELETE FROM pipeline_runs WHERE id=?", (run_id,))
        conn.commit()
