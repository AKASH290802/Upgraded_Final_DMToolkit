"""AppTest entry point for the Step 3 (Data Operations) tests.

Same as app_under_test.py (real streamlit_app, Salesforce and SQL Server queries
faked) plus:
  * load_data_to_sql_server is faked (no pyodbc / SQL Server needed); every call
    is recorded in SQL_WRITES,
  * a test hook that publishes a Step 2 result (the same call Step 2 makes) so
    these tests do not depend on the Mapping & Validation page,
  * for Step 4: the fake SQL Server keeps the tables it "writes" (session
    '_test_sql_tables') and answers the Step 4 queries on them; with
    st.session_state['_test_persist_sf'] = True, Salesforce bulk writes are kept
    in session '_test_sf_overlay' ({object: {Id: record}}) and queries see them.

Hook: set st.session_state['_test_publish_validation'] = {
    'method': ..., 'object': ..., 'field_mappings': {...}, 'lookups_resolved': bool}
before a run; the Step 1 rows with an empty first mapped column become invalid.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for path in (ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)
os.chdir(ROOT)

import re  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import pandas as pd  # noqa: E402

import fake_salesforce  # noqa: E402
fake_salesforce.install()

import streamlit as st  # noqa: E402

import streamlit_app  # noqa: E402
from ui_components import data_operations, step_flow  # noqa: E402

SQL_ROWS = pd.DataFrame({
    'AccountName': ['Initech', 'Umbrella', ''],
    'Acct_No': ['B-1', 'B-2', 'B-3'],
    'Phone': ['5550001111', '5550002222', '5550003333'],
    'Industry': ['Energy', 'Banking', 'Energy'],
})

# dicts: table, schema, mode, columns, rows (kept in session: the script reruns)
SQL_WRITES = st.session_state.setdefault('_test_sql_writes', [])


# Where each SQL query ran (the server of the config it got), kept in session.
SQL_READS = st.session_state.setdefault('_test_sql_reads', [])


# Tables the fake load wrote: 'schema.table' -> DataFrame (kept in session).
SQL_TABLES = st.session_state.setdefault('_test_sql_tables', {})
_TABLE = r"\[([^\]]*)\]\.\[([^\]]*)\]"


def _answer_table_query(query):
    """The Step 4 queries on a table the fake load wrote (None when it is another query)."""
    q = ' '.join(query.split())
    m = re.search(r"FROM INFORMATION_SCHEMA\.(TABLES|COLUMNS) WHERE TABLE_SCHEMA = '([^']*)' "
                  r"AND TABLE_NAME = '([^']*)'", q)
    if m and q.startswith(('SELECT COUNT(*) AS n', 'SELECT COLUMN_NAME')):
        table = SQL_TABLES.get(f"{m.group(2)}.{m.group(3)}")
        if m.group(1) == 'TABLES':
            return pd.DataFrame({'n': [int(table is not None)]})
        return pd.DataFrame({'COLUMN_NAME': list(table.columns) if table is not None else []})
    m = re.search(r"^SELECT COUNT\(\*\) AS n FROM " + _TABLE + r"$", q)
    if m and f"{m.group(1)}.{m.group(2)}" in SQL_TABLES:
        return pd.DataFrame({'n': [len(SQL_TABLES[f"{m.group(1)}.{m.group(2)}"])]})
    m = re.search(r"^SELECT (.+) FROM " + _TABLE + r"$", q)
    if m and f"{m.group(2)}.{m.group(3)}" in SQL_TABLES:
        cols = [c.strip().strip('[]') for c in m.group(1).split(',')]
        return SQL_TABLES[f"{m.group(2)}.{m.group(3)}"][cols].copy()
    return None


def _fake_sql_query_to_df(db_cfg, query, command_timeout=None, chunk_size=5000, lock_timeout_ms=5000):
    fake_salesforce.QUERIES.append(('sql', query))
    SQL_READS.append({'server': (db_cfg or {}).get('server'), 'query': query})
    answer = _answer_table_query(query)
    if answer is not None:
        return answer
    if 'INFORMATION_SCHEMA.TABLES' in query:
        return pd.DataFrame({'TABLE_SCHEMA': ['dbo'], 'TABLE_NAME': ['Accounts']})
    return SQL_ROWS.copy()


def _fake_load_data_to_sql_server(db_config, df, table_name, schema_name, load_mode, batch_size,
                                  index_columns, nullable_columns, include_index, check_constraints):
    SQL_WRITES.append({'table': table_name, 'schema': schema_name, 'mode': load_mode,
                       'columns': list(df.columns), 'rows': len(df)})
    name = f"{schema_name}.{table_name}"
    append = load_mode == "Append to Existing" and name in SQL_TABLES
    before = len(SQL_TABLES[name]) if append else 0
    written = df.copy()
    SQL_TABLES[name] = pd.concat([SQL_TABLES[name], written], ignore_index=True) if append else written.copy()
    st.success(f"(fake) loaded {len(df)} rows into {schema_name}.{table_name}")
    return {'success': len(df), 'failed': 0, 'error': None, 'before_count': before,
            'final_count': len(SQL_TABLES[name]), 'written_df': written}


# Salesforce records written by bulk loads (only with '_test_persist_sf'), kept in session.
SF_OVERLAY = st.session_state.setdefault('_test_sf_overlay', {})


def _now_sf():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000+0000')


def _persisting_write(original):
    """Bulk writes that the later queries see (inserts get CreatedDate, all get LastModifiedDate)."""
    def write(self, operation, records):
        results = original(self, operation, records)
        table = SF_OVERLAY.setdefault(self.name, {})
        for record, result in zip(records, results):
            if operation == 'update' or record.get('Id'):
                rid = record['Id']
                base = table.get(rid) or next(
                    (dict(r) for r in fake_salesforce.RECORDS.get(self.name, []) if r['Id'] == rid),
                    {'Id': rid, 'CreatedDate': '2020-01-01T00:00:00.000+0000'})
                base.update(record)
                base['LastModifiedDate'] = _now_sf()
                table[rid] = base
                result['id'] = rid
            else:
                table[result['id']] = {**record, 'Id': result['id'], 'CreatedDate': _now_sf(),
                                       'LastModifiedDate': _now_sf()}
        return results
    return write


def _with_overlay(base):
    """_records_for plus the records the persisting bulk writes kept."""
    def records_for(soql):
        rows = base(soql)
        match = re.search(r'\bFROM\s+(\w+)', soql, re.IGNORECASE)
        obj = match.group(1) if match else ''
        overlay = SF_OVERLAY.get(obj, {})
        if not overlay:
            return rows
        merged = [dict(r, **overlay[r['Id']]) if r.get('Id') in overlay else r for r in rows]
        seen = {r.get('Id') for r in rows}
        merged += [{'attributes': {'type': obj, 'url': f'/services/data/v59.0/sobjects/{obj}/{rid}'}, **rec}
                   for rid, rec in overlay.items() if rid not in seen]
        return merged
    return records_for


def _where_filtered(base):
    """Wrap fake_salesforce._records_for to honour `WHERE <field> IN (...)` / `WHERE <field> = '...'`.

    The insert uniqueness check asks which values already exist; the base fake
    returns every record for any query, so every insert looked like a duplicate.
    Queries with any other WHERE shape behave exactly as before.
    """
    import re
    pattern = re.compile(r"\bWHERE\s+(\w+)\s+(?:IN\s*\(([^)]*)\)|=\s*'([^']*)')\s*$", re.IGNORECASE)

    def records_for(soql):
        rows = base(soql)
        match = pattern.search(soql.strip())
        if not match:
            return rows
        field = match.group(1)
        if match.group(2) is not None:
            values = {v.strip().strip("'") for v in match.group(2).split(',')}
        else:
            values = {match.group(3)}
        return [r for r in rows if str(r.get(field)) in values]

    return records_for


# AppTest runs this script inside the test process, so module patches would
# outlive the run and change the fakes other test files get.  Patch for THIS run
# only and restore the previous objects when the run ends (see the finally below).
_PATCHES = [
    (fake_salesforce, '_records_for', _where_filtered(fake_salesforce._records_for)),
    (data_operations, '_sql_query_to_df', _fake_sql_query_to_df),
    (data_operations, 'load_data_to_sql_server', _fake_load_data_to_sql_server),
]
if st.session_state.get('_test_persist_sf'):
    _describes = {name: dict(desc, fields=list(desc['fields'])) for name, desc in fake_salesforce.DESCRIBES.items()}
    _describes['Account']['fields'].append(fake_salesforce._field(
        'LastModifiedDate', 'datetime', 'Last Modified Date', nillable=False, createable=False, updateable=False))
    _PATCHES = [
        (fake_salesforce, '_records_for', _where_filtered(_with_overlay(fake_salesforce._records_for))),
        (fake_salesforce, 'DESCRIBES', _describes),
        (fake_salesforce._FakeBulkType, '_write', _persisting_write(fake_salesforce._FakeBulkType._write)),
    ] + _PATCHES[1:]

# Hook: st.session_state['_test_second_sql'] = True adds a second SQL Server
# connection ('sql_Second', server 'second-host') to the configured credentials.
if st.session_state.get('_test_second_sql'):
    _real_load_credentials = streamlit_app.load_credentials

    def _load_credentials_with_second_sql():
        creds = dict(_real_load_credentials() or {})
        creds['sql_Second'] = {'server': 'second-host', 'database': 'SecondDb',
                               'username': 'sa', 'password': 'x'}
        st.session_state.available_sql_connections = list(
            data_operations.cm.classify_credentials(creds)['sqlserver'])
        return creds

    _PATCHES.append((streamlit_app, 'load_credentials', _load_credentials_with_second_sql))
_ORIGINALS = [(mod, name, getattr(mod, name)) for mod, name, _ in _PATCHES]
for _mod, _name, _value in _PATCHES:
    setattr(_mod, _name, _value)

try:
    _publish = st.session_state.pop('_test_publish_validation', None)
    if _publish:
        df = step_flow.get_flow_df()
        mappings = _publish['field_mappings']
        first_col = next(iter(mappings))
        bad = df[first_col].astype(str).str.strip() == ''
        step_flow.publish_validation_result(
            method=_publish.get('method', 'Enhanced Validation'),
            object_name=_publish['object'],
            valid_df=df[~bad],
            invalid_df=df[bad],
            field_mappings=mappings,
            lookups_resolved=_publish.get('lookups_resolved', True),
            match=_publish.get('match'),
        )

    import isolation  # noqa: E402
    isolation.isolate_file_library()
    streamlit_app.main()
finally:
    for _mod, _name, _value in _ORIGINALS:
        setattr(_mod, _name, _value)
