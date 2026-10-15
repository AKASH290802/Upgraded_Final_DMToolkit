"""
Step 4 · Test Loaded Records — read back what Step 3 loaded and check it.

Salesforce: every loaded record Id is queried back and
    1. the Step 3 counts add up (loaded + failed + skipped = rows sent),
    2. rows rejected in Step 3 are reported,
    3. every loaded record exists,
    4. every value sent is the value stored (compared per field type),
    5. the records were created / changed by this load,
    6. there is one record per match-key value (no duplicates).
SQL Server: the table exists, has the loaded columns, its row count moved by
the loaded rows, and it holds the loaded rows.

The run is recorded with step_flow.record_test_result (it completes Step 4) and
its report is saved to the File Library.
"""

import io
import math
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from ui_components import step_flow

SAMPLE_SIZE = 2000              # records checked by "Sample" (evenly spread over the load)
FULL_CHECK_LIMIT = 20000        # up to this many loaded records, "All" is the default
SQL_READ_LIMIT = 200000         # SQL Server tables up to this size are compared row by row
CLOCK_TOLERANCE = timedelta(minutes=10)   # local clock vs Salesforce server time
MAX_ID_CHUNK = 200
MAX_SOQL_CHARS = 14000          # stays below the REST query URL limit (measured URL-encoded, as sent)
MAX_DETAIL_ROWS = 5000          # mismatches kept for the report

ICONS = {'PASS': '✅ PASS', 'FAIL': '❌ FAIL', 'WARN': '⚠️ WARN', 'SKIP': '⏭️ SKIP'}

# Field types whose values cannot be compared one to one.
_NOT_COMPARABLE = {'address', 'location', 'base64', 'encryptedstring', 'complexvalue', 'anyType'}
_TRUTHY = {'true', '1', 'yes', 'y', 't', 'on'}
_FALSY = {'false', '0', 'no', 'n', 'f', 'off'}


def _check(name: str, status: str, detail: str) -> Dict:
    return {'check': name, 'status': status, 'detail': detail}


# ---------------------------------------------------------------------------
# Value comparison
# ---------------------------------------------------------------------------

def _blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        if value is pd.NaT or (not isinstance(value, (str, bytes, list, dict)) and pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(value, str) and value.strip() == ''


def _text(value) -> str:
    return str(value).replace('\r\n', '\n').strip()


def _number(value) -> Optional[float]:
    if isinstance(value, bool):
        return float(value)
    try:
        return float(str(value).replace(',', '')) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return None


def _timestamp(value):
    try:
        ts = pd.to_datetime(value, utc=True)
    except (TypeError, ValueError, OverflowError):
        return None
    return None if pd.isna(ts) else ts


def normalize(value, ftype: str = 'string', scale: int = 0):
    """Canonical form of a Salesforce value for comparison (None for blank)."""
    ftype = (ftype or 'string').lower()
    if _blank(value):
        return False if ftype == 'boolean' else None   # a checkbox is never blank in Salesforce
    if ftype == 'boolean':
        if isinstance(value, bool):
            return value
        text = _text(value).lower()
        return True if text in _TRUTHY else False if text in _FALSY else text
    if ftype in ('int', 'double', 'currency', 'percent'):
        # Not rounded here: values_match compares within the field's precision (Salesforce rounds half up).
        number = _number(value)
        return float(number) if number is not None else _text(value)
    if ftype == 'date':
        ts = _timestamp(value)
        return ts.strftime('%Y-%m-%d') if ts is not None else _text(value)
    if ftype == 'datetime':
        ts = _timestamp(value)
        return ts.strftime('%Y-%m-%dT%H:%M:%S') if ts is not None else _text(value)
    if ftype == 'time':
        return _text(value)[:8]
    if ftype == 'multipicklist':
        return tuple(sorted(v.strip() for v in _text(value).split(';') if v.strip()))
    if ftype in ('id', 'reference'):
        return _text(value)[:15]
    return _text(value)


def _has_default(info: Dict) -> bool:
    return bool(info.get('defaultedOnCreate') or info.get('defaultValue') is not None
                or any(v.get('defaultValue') for v in info.get('picklistValues') or []))


def values_match(sent, stored, ftype: str = 'string', scale: int = 0) -> bool:
    a, b = normalize(sent, ftype, scale), normalize(stored, ftype, scale)
    if isinstance(a, float) and isinstance(b, float):
        # Salesforce keeps `scale` decimals (rounded half up), so a sent value may differ by up to
        # half a unit of the last kept decimal; the relative term covers float noise in large values.
        tolerance = 0.5 * 10 ** -max(int(scale or 0), 0)
        return abs(a - b) <= tolerance * (1 + 1e-9) + 1e-9 * max(abs(a), abs(b), 1.0)
    return a == b


# ---------------------------------------------------------------------------
# Salesforce
# ---------------------------------------------------------------------------

def _soql_literal(value, ftype: str) -> Optional[str]:
    if ftype in ('int', 'double', 'currency', 'percent'):
        number = _number(value)
        return None if number is None else (str(int(number)) if float(number).is_integer() else repr(number))
    if ftype in ('boolean', 'date', 'datetime', 'time', 'multipicklist', 'textarea') or ftype in _NOT_COMPARABLE:
        return None
    text = str(value).replace('\\', '\\\\').replace("'", "\\'")
    return f"'{text}'"


def _url_len(text: str) -> int:
    """Length of text in the query URL (simple_salesforce sends ?q=<form-encoded SOQL>)."""
    from urllib.parse import quote_plus
    return len(quote_plus(text))


def _query(sf_conn, soql: str) -> List[Dict]:
    result = sf_conn.query_all(soql)
    records = result.get('records', []) if isinstance(result, dict) else list(result or [])
    return [{k: v for k, v in r.items() if k != 'attributes'} for r in records]


def _field_groups(fields: List[str], budget: int) -> List[List[str]]:
    """Split a select list so each query stays under the length budget (URL-encoded)."""
    groups, current, size = [], [], 0
    for field in fields:
        cost = _url_len(field + ', ')
        if current and size + cost > budget:
            groups.append(current)
            current, size = [], 0
        current.append(field)
        size += cost
    if current or not groups:
        groups.append(current)
    return groups


def fetch_records(sf_conn, object_name: str, ids: List[str], fields: List[str],
                  progress: Optional[Callable[[float], None]] = None) -> Dict[str, Dict]:
    """{Id: record} for the given Ids (every field of `fields`), in few, bounded queries."""
    ids = [i for i in dict.fromkeys(ids) if i]
    # SOQL rejects a field selected twice ("duplicate field selected"), in any letter case.
    seen = {'id'}
    fields = [f for f in fields if not (f.lower() in seen or seen.add(f.lower()))]
    found: Dict[str, Dict] = {}
    groups = _field_groups(fields, MAX_SOQL_CHARS // 2)
    id_cost = _url_len("'001000000000000AAA', ")
    steps = max(1, len(groups) * math.ceil(len(ids) / MAX_ID_CHUNK))
    done = 0
    for group in groups:
        select = ', '.join(['Id'] + group)
        fixed = _url_len(f"SELECT {select} FROM {object_name} WHERE Id IN ()")
        per_chunk = max(20, min(MAX_ID_CHUNK, (MAX_SOQL_CHARS - fixed) // id_cost))
        for start in range(0, len(ids), per_chunk):
            chunk = ids[start:start + per_chunk]
            quoted = ', '.join(f"'{i}'" for i in chunk)
            for record in _query(sf_conn, f"SELECT {select} FROM {object_name} WHERE Id IN ({quoted})"):
                key = str(record.get('Id', ''))
                match = next((i for i in chunk if i[:15] == key[:15]), key)
                found.setdefault(match, {}).update(record)
            done += 1
            if progress:
                progress(min(done / steps, 1.0))
    return found


def _sample_positions(count: int, scope: str) -> List[int]:
    if scope != 'sample' or count <= SAMPLE_SIZE:
        return list(range(count))
    step = count / SAMPLE_SIZE
    return sorted({int(i * step) for i in range(SAMPLE_SIZE)})


def _reconciliation_checks(load: Dict, validation: Optional[Dict]) -> List[Dict]:
    checks = []
    total, success, failed, skipped = (load.get('total', 0), load.get('success', 0),
                                       load.get('failed', 0), load.get('skipped', 0))
    unaccounted = total - success - failed - skipped
    if unaccounted == 0:
        checks.append(_check("Step 3 counts add up", 'PASS',
                             f"{total:,} rows sent = {success:,} loaded + {failed:,} failed + {skipped:,} skipped."))
    elif unaccounted > 0:
        checks.append(_check("Step 3 counts add up", 'FAIL',
                             f"{unaccounted:,} of {total:,} rows sent were neither loaded nor reported as failed "
                             f"or skipped ({success:,} loaded, {failed:,} failed, {skipped:,} skipped)."))
    else:
        checks.append(_check("Step 3 counts add up", 'WARN',
                             f"Loaded + failed + skipped ({success + failed + skipped:,}) is more than the "
                             f"{total:,} rows sent — some rows were counted twice."))
    valid = ((validation or {}).get('summary') or {}).get('valid')
    if valid is not None and total != valid:
        checks.append(_check("All validated rows were loaded", 'WARN',
                             f"Step 2 validated {valid:,} rows; Step 3 sent {total:,}."))
    rejected = failed + skipped
    details = load.get('details') or {}
    if rejected == 0:
        checks.append(_check("No rows rejected in Step 3", 'PASS', "Every row sent was loaded."))
    else:
        reasons = Counter(r.get('reason') or 'unknown' for r in
                          (details.get('failed_rows') or []) + (details.get('skipped_rows') or []))
        top = "; ".join(f"{n:,} × {reason[:90]}" for reason, n in reasons.most_common(3))
        checks.append(_check("No rows rejected in Step 3", 'WARN',
                             f"{failed:,} failed and {skipped:,} skipped in Step 3" + (f" — {top}" if top else "")
                             + ". Fix them and load again, or accept them."))
    return checks


def verify_salesforce_load(sf_conn, load: Dict, validation: Optional[Dict], scope: str = 'all',
                           progress: Optional[Callable[[float], None]] = None) -> Dict:
    """Run every Salesforce check on a recorded Step 3 load. Returns checks + report tables."""
    details = load.get('details') or {}
    object_name = load['target']
    ids = list(details.get('record_ids') or [])
    expected: pd.DataFrame = details.get('expected') if isinstance(details.get('expected'), pd.DataFrame) \
        else pd.DataFrame(index=range(len(ids)))
    rows = list(details.get('row_positions') or [None] * len(ids))
    sent_rows = expected.to_dict('records')
    created = list(details.get('created') or [None] * len(ids))
    checks = _reconciliation_checks(load, validation)

    describe = getattr(sf_conn, object_name).describe()
    field_info = {f['name']: f for f in describe.get('fields', [])}
    positions = _sample_positions(len(ids), scope)
    checked_ids = [ids[p] for p in positions]

    compare, not_compared = [], []
    for field in expected.columns:
        info = field_info.get(field)
        if info is None or '.' in field:
            not_compared.append((field, "not a field of the object (e.g. a relationship reference)"))
        elif info.get('type') in _NOT_COMPARABLE or info.get('encrypted'):
            not_compared.append((field, f"{info.get('type')} values cannot be compared"))
        else:
            compare.append(field)
    audit = [f for f in ('CreatedDate', 'LastModifiedDate', 'SystemModstamp') if f in field_info]
    stored = fetch_records(sf_conn, object_name, checked_ids, compare + audit, progress)
    loaded_fields = {str(c).lower() for c in expected.columns}

    # 3. existence
    missing = [i for i in checked_ids if i not in stored]
    scope_text = (f"all {len(checked_ids):,} loaded records" if len(checked_ids) == len(ids)
                  else f"a sample of {len(checked_ids):,} of {len(ids):,} loaded records")
    if not ids:
        checks.append(_check(f"Loaded records exist in {object_name}", 'SKIP', "Step 3 loaded no records."))
    elif missing:
        checks.append(_check(f"Loaded records exist in {object_name}", 'FAIL',
                             f"{len(missing):,} of {len(checked_ids):,} records were not found (deleted, or not "
                             f"visible to this user) — e.g. {', '.join(missing[:3])}."))
    else:
        checks.append(_check(f"Loaded records exist in {object_name}", 'PASS', f"Found {scope_text}."))

    # 4. values
    mismatch_rows, per_field = [], []
    bad_records = set(missing)
    for field in compare:
        info = field_info[field]
        ftype, scale = info.get('type', 'string'), info.get('scale', 0)
        compared = mismatches = 0
        for pos in positions:
            record_id = ids[pos]
            record = stored.get(record_id)
            if record is None:
                continue
            sent = sent_rows[pos].get(field) if pos < len(sent_rows) else None
            actual = record.get(field)
            compared += 1
            if _blank(sent) and created[pos] is True and _has_default(info):
                continue   # a blank value on insert takes the field's default
            if not values_match(sent, actual, ftype, scale):
                mismatches += 1
                bad_records.add(record_id)
                if len(mismatch_rows) < MAX_DETAIL_ROWS:
                    row = rows[pos] if pos < len(rows) else None
                    mismatch_rows.append({'Step 2 row': (row + 1) if isinstance(row, int) else row,
                                          'Record Id': record_id, 'Field': field,
                                          'Sent': None if _blank(sent) else sent,
                                          'In Salesforce': None if _blank(actual) else actual})
        per_field.append({'Field': field, 'Label': info.get('label', field), 'Type': ftype,
                          'Compared': compared, 'Mismatches': mismatches,
                          'Status': ICONS['PASS'] if mismatches == 0 else ICONS['FAIL']})
    for field, reason in not_compared:
        per_field.append({'Field': field, 'Label': field_info.get(field, {}).get('label', field), 'Type': '—',
                          'Compared': 0, 'Mismatches': 0, 'Status': f"{ICONS['SKIP']} ({reason})"})
    failing_fields = [f['Field'] for f in per_field if f['Mismatches']]
    if not compare:
        checks.append(_check("Field values match what was loaded", 'SKIP', "No comparable fields were loaded."))
    elif failing_fields:
        total_bad = sum(f['Mismatches'] for f in per_field)
        checks.append(_check("Field values match what was loaded", 'FAIL',
                             f"{total_bad:,} value(s) differ in {len(failing_fields)} of {len(compare)} fields: "
                             f"{', '.join(failing_fields[:6])}{' …' if len(failing_fields) > 6 else ''}."))
    else:
        checks.append(_check("Field values match what was loaded", 'PASS',
                             f"{len(compare)} fields × {len(checked_ids) - len(missing):,} records are identical"
                             + (f" ({len(not_compared)} fields not comparable)" if not_compared else "") + "."))

    # 5. created / changed by this load
    checks.append(_audit_check(load, details, stored, positions, ids, created, audit, loaded_fields))

    # 6. duplicates on the match key
    dup_check, duplicates = _duplicate_check(sf_conn, object_name, details.get('match') or {},
                                             sent_rows, list(expected.columns), positions, field_info)
    checks.append(dup_check)

    verified = sum(1 for i in checked_ids if i in stored and i not in bad_records)
    return {'checks': checks, 'records_checked': len(checked_ids), 'verified': verified,
            'field_summary': pd.DataFrame(per_field),
            'mismatches': pd.DataFrame(mismatch_rows, columns=['Step 2 row', 'Record Id', 'Field', 'Sent',
                                                               'In Salesforce']),
            'missing_ids': missing, 'duplicates': duplicates, 'scope': scope_text}


def _audit_check(load, details, stored, positions, ids, created, audit, loaded_fields=frozenset()) -> Dict:
    """Were the records written (and the inserted ones created) by this load?

    SystemModstamp is used for 'modified' because no load can set it; CreatedDate /
    LastModifiedDate are only used when the load did not set them itself (an audit-field
    migration loads historical values on purpose - the value check compares those).
    """
    name = "Records were written by this load"
    started = _timestamp(details.get('started_at_utc'))
    modified_field = ('SystemModstamp' if 'SystemModstamp' in audit else
                      'LastModifiedDate' if 'LastModifiedDate' in audit and 'lastmodifieddate' not in loaded_fields
                      else None)
    check_created = 'CreatedDate' in audit and 'createddate' not in loaded_fields
    if started is None or (modified_field is None and not check_created):
        return _check(name, 'SKIP', "The load start time or a system timestamp (SystemModstamp / "
                                    "LastModifiedDate) is not available, or the load set the audit fields itself.")
    since = started - CLOCK_TOLERANCE
    stale, not_new, checked = [], [], 0
    for pos in positions:
        record = stored.get(ids[pos])
        if record is None:
            continue
        checked += 1
        if modified_field:
            modified = _timestamp(record.get(modified_field))
            if modified is None or modified < since:
                stale.append(ids[pos])
        if created[pos] is True and check_created:
            made = _timestamp(record.get('CreatedDate'))
            if made is None or made < since:
                not_new.append(ids[pos])
    if not checked:
        return _check(name, 'SKIP', "No loaded record was found to check.")
    problems = []
    if stale:
        problems.append(f"{len(stale):,} record(s) were not modified since the load started (e.g. {stale[0]})")
    if not_new:
        problems.append(f"{len(not_new):,} record(s) Step 3 inserted were created earlier (e.g. {not_new[0]})")
    if problems:
        return _check(name, 'FAIL', "; ".join(problems) + ".")
    inserted = sum(1 for p in positions if created[p] is True and ids[p] in stored)
    return _check(name, 'PASS', f"All {checked:,} records were changed by this {load.get('operation', 'load')}"
                  + (f"; {inserted:,} of them were created by it." if inserted else "."))


def _duplicate_check(sf_conn, object_name, match, sent_rows, columns, positions,
                     field_info) -> Tuple[Dict, pd.DataFrame]:
    name = "One record per match key (no duplicates)"
    empty = pd.DataFrame()
    fields = [f for f in (match.get('fields') or []) if f in columns and f in field_info]
    if not fields:
        return _check(name, 'SKIP', "The load had no match key among the loaded fields."), empty
    first = fields[0]
    if not field_info[first].get('filterable', True):
        return _check(name, 'SKIP', f"{first} cannot be used in a query filter."), empty
    keys = set()
    for pos in positions:
        if pos >= len(sent_rows):
            continue
        values = tuple(normalize(sent_rows[pos].get(f), field_info[f].get('type')) for f in fields)
        if all(v is not None for v in values):
            keys.add(values)
    if not keys:
        return _check(name, 'SKIP', f"No loaded record has a value in {', '.join(fields)}."), empty
    ftype = field_info[first].get('type', 'string')
    literals = sorted({lit for lit in (_soql_literal(sent_rows[p].get(first), ftype) for p in positions
                                       if p < len(sent_rows) and not _blank(sent_rows[p].get(first))) if lit})
    if not literals:
        return _check(name, 'SKIP', f"{first} ({ftype}) values cannot be used in a query filter."), empty
    select = ', '.join(dict.fromkeys(['Id'] + fields))
    counts: Counter = Counter()
    ids_by_key: Dict[tuple, List[str]] = {}
    budget = max(200, MAX_SOQL_CHARS - _url_len(f"SELECT {select} FROM {object_name} WHERE {first} IN ()"))
    chunk, size = [], 0
    for literal in literals + [None]:
        cost = _url_len(literal + ', ') if literal is not None else 0
        if literal is not None and (not chunk or size + cost <= budget):
            chunk.append(literal)
            size += cost
            continue
        if chunk:
            for record in _query(sf_conn, f"SELECT {select} FROM {object_name} WHERE {first} IN ({', '.join(chunk)})"):
                key = tuple(normalize(record.get(f), field_info[f].get('type')) for f in fields)
                if key in keys:
                    counts[key] += 1
                    ids_by_key.setdefault(key, []).append(str(record.get('Id')))
        chunk, size = ([literal], cost) if literal is not None else ([], 0)
    dups = {k: n for k, n in counts.items() if n > 1}
    if not dups:
        return _check(name, 'PASS', f"Each of the {len(keys):,} loaded {' + '.join(fields)} values "
                                    f"has exactly one record."), empty
    table = pd.DataFrame([{**{f: v for f, v in zip(fields, key)}, 'Records': n,
                           'Record Ids': ', '.join(ids_by_key.get(key, [])[:10])}
                          for key, n in sorted(dups.items(), key=lambda kv: -kv[1])[:MAX_DETAIL_ROWS]])
    return _check(name, 'FAIL', f"{len(dups):,} {' + '.join(fields)} value(s) have more than one record in "
                                f"{object_name} (e.g. {' | '.join(map(str, next(iter(dups))))})."), table


# ---------------------------------------------------------------------------
# SQL Server
# ---------------------------------------------------------------------------

def _sql_text(value) -> str:
    if _blank(value):
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(round(value, 10))
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).tz_localize(None).isoformat() if pd.Timestamp(value).tzinfo else \
            pd.Timestamp(value).isoformat()
    number = _number(value) if isinstance(value, str) and value.strip()[:1].isdigit() else None
    if number is not None and str(value).strip().lstrip('-').replace('.', '', 1).isdigit():
        return str(int(number)) if number.is_integer() else repr(round(number, 10))
    text = _text(value)
    return {'True': 'true', 'False': 'false'}.get(text, text)


_SQL_INT = {'int', 'bigint', 'smallint', 'tinyint'}
_SQL_DECIMAL = {'decimal', 'numeric', 'money', 'smallmoney'}
_SQL_FLOAT = {'float', 'real'}
_SQL_DATETIME = {'datetime', 'datetime2', 'datetimeoffset'}


def _sql_canon(value, dtype: Optional[str], scale=None) -> str:
    """A value as SQL Server stores it in a column of type dtype (both sides compare as text).

    Text columns stay text (leading zeros, precision kept); numbers, dates and bits follow
    the column's type, so '10' loaded into DECIMAL(18,2) equals Decimal('10.00') read back.
    """
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    dtype = (dtype or '').lower()
    if _blank(value):
        return ''
    if dtype in _SQL_INT or dtype in _SQL_DECIMAL:
        try:
            number = Decimal(str(value).strip().replace(',', ''))
            if dtype in _SQL_INT:
                number = number.quantize(Decimal(1), rounding=ROUND_HALF_UP)
            elif scale is not None and str(scale).strip() not in ('', 'None', 'nan'):
                number = number.quantize(Decimal(1).scaleb(-int(float(scale))), rounding=ROUND_HALF_UP)
            text = format(number.normalize(), 'f')
            return '0' if text in ('-0', '') else text
        except (InvalidOperation, ValueError, TypeError):
            return _text(value)
    if dtype in _SQL_FLOAT:
        number = _number(value)
        return _text(value) if number is None else f"{number:.{7 if dtype == 'real' else 15}g}"
    if dtype == 'bit':
        text = _text(value).lower()
        return '1' if text in _TRUTHY else '0' if text in _FALSY else text
    if dtype == 'date':
        ts = _timestamp(value)
        return ts.strftime('%Y-%m-%d') if ts is not None else _text(value)
    if dtype in _SQL_DATETIME or dtype == 'smalldatetime':
        ts = _timestamp(value)
        if ts is None:
            return _text(value)
        # DATETIME keeps 1/300 s and SMALLDATETIME minutes: compare at that precision.
        return ts.round('min' if dtype == 'smalldatetime' else '10ms').strftime('%Y-%m-%dT%H:%M:%S.%f')[:23]
    if dtype == 'time':
        return _text(value)[:8]
    if dtype == 'uniqueidentifier':
        return _text(value).lower().strip('{}')
    if dtype in ('char', 'nchar'):
        return str(value).replace('\r\n', '\n').rstrip()
    if dtype in ('varchar', 'nvarchar', 'text', 'ntext', 'sysname', 'xml'):
        return str(value).replace('\r\n', '\n')
    return _sql_text(value)


def _row_keys(df: pd.DataFrame, columns: List[str], types: Optional[Dict[str, Tuple]] = None) -> Counter:
    if not types:
        return Counter(tuple(_sql_text(v) for v in row) for row in df[columns].itertuples(index=False, name=None))
    kinds = [types.get(c.lower(), (None, None)) for c in columns]
    return Counter(tuple(_sql_canon(v, dtype, scale) for v, (dtype, scale) in zip(row, kinds))
                   for row in df[columns].itertuples(index=False, name=None))


def verify_sql_load(load: Dict, validation: Optional[Dict], run_query: Callable[[str], pd.DataFrame]) -> Dict:
    """Run the SQL Server checks on a recorded Step 3 load."""
    details = load.get('details') or {}
    schema, table, mode = details.get('schema', 'dbo'), details.get('table'), details.get('mode', '')
    expected: pd.DataFrame = details.get('expected') if isinstance(details.get('expected'), pd.DataFrame) \
        else pd.DataFrame()
    full = f"[{schema}].[{table}]"
    checks = _reconciliation_checks(load, validation)
    loaded = int(load.get('success', 0))
    empty = pd.DataFrame()
    safe = lambda s: str(s).replace("'", "''")  # noqa: E731

    exists = run_query(f"SELECT COUNT(*) AS n FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{safe(schema)}' "
                       f"AND TABLE_NAME = '{safe(table)}'")
    if exists.empty or int(exists.iloc[0, 0]) == 0:
        checks.append(_check(f"Table {schema}.{table} exists", 'FAIL', "The table was not found."))
        return {'checks': checks, 'records_checked': 0, 'verified': 0, 'field_summary': empty,
                'mismatches': empty, 'missing_ids': [], 'duplicates': empty, 'scope': 'the table'}
    checks.append(_check(f"Table {schema}.{table} exists", 'PASS', "Found."))

    cols = run_query(f"SELECT COLUMN_NAME, DATA_TYPE, NUMERIC_SCALE FROM INFORMATION_SCHEMA.COLUMNS "
                     f"WHERE TABLE_SCHEMA = '{safe(schema)}' AND TABLE_NAME = '{safe(table)}'")
    table_cols = {str(c).lower() for c in (cols.iloc[:, 0] if not cols.empty else [])}
    # column -> (DATA_TYPE, NUMERIC_SCALE), to compare each value the way the column stores it
    types = ({str(r[0]).lower(): (str(r[1]), r[2] if len(r) > 2 else None)
              for r in cols.itertuples(index=False, name=None)} if cols.shape[1] >= 2 else {})
    loaded_cols = [str(c) for c in expected.columns]
    missing_cols = [c for c in loaded_cols if c.lower() not in table_cols]
    checks.append(_check("Loaded columns exist in the table", 'FAIL' if missing_cols else 'PASS',
                         (f"Missing: {', '.join(missing_cols[:10])}." if missing_cols
                          else f"All {len(loaded_cols)} loaded columns are there.")))

    count_now = int(run_query(f"SELECT COUNT(*) AS n FROM {full}").iloc[0, 0])
    before = details.get('before_count')
    if mode == "Append to Existing":
        if before is None:
            checks.append(_check("Row count", 'WARN', f"The table has {count_now:,} rows; the count before the "
                                                     f"append is unknown, so the {loaded:,} added rows cannot be "
                                                     "confirmed by count."))
        else:
            added = count_now - int(before)
            checks.append(_check("Row count", 'PASS' if added == loaded else 'FAIL',
                                 f"{int(before):,} rows before + {loaded:,} loaded = {int(before) + loaded:,}; "
                                 f"the table has {count_now:,}."))
    else:
        checks.append(_check("Row count", 'PASS' if count_now == loaded else 'FAIL',
                             f"{loaded:,} rows loaded; the table has {count_now:,}."))

    compare_cols = [c for c in loaded_cols if c not in missing_cols]
    mismatches = empty
    verified = 0
    if not compare_cols or expected.empty:
        checks.append(_check("Table holds the loaded rows", 'SKIP', "No comparable columns."))
    elif count_now > SQL_READ_LIMIT:
        checks.append(_check("Table holds the loaded rows", 'SKIP',
                             f"The table has {count_now:,} rows (more than {SQL_READ_LIMIT:,}), so the rows were "
                             "not compared one by one."))
    else:
        select = ', '.join(f"[{c}]" for c in compare_cols)
        actual = run_query(f"SELECT {select} FROM {full}")
        actual.columns = [str(c) for c in actual.columns]
        lookup = {c.lower(): c for c in actual.columns}
        actual = actual[[lookup.get(c.lower(), c) for c in compare_cols]]
        actual.columns = compare_cols
        want, have = _row_keys(expected, compare_cols, types), _row_keys(actual, compare_cols, types)
        not_found = want - have
        extra = (have - want) if mode != "Append to Existing" else Counter()
        verified = sum(want.values()) - sum(not_found.values())
        if not not_found and not extra:
            checks.append(_check("Table holds the loaded rows", 'PASS',
                                 f"All {sum(want.values()):,} loaded rows are in the table with the same values."))
        else:
            parts = []
            if not_found:
                parts.append(f"{sum(not_found.values()):,} loaded row(s) are not in the table as loaded")
            if extra:
                parts.append(f"{sum(extra.values()):,} row(s) in the table were not loaded")
            checks.append(_check("Table holds the loaded rows", 'FAIL', "; ".join(parts) + "."))
            rows = [dict(zip(compare_cols, key), **{'Problem': 'Loaded, not found in table', 'Count': n})
                    for key, n in list(not_found.items())[:MAX_DETAIL_ROWS]]
            rows += [dict(zip(compare_cols, key), **{'Problem': 'In table, not loaded', 'Count': n})
                     for key, n in list(extra.items())[:MAX_DETAIL_ROWS]]
            mismatches = pd.DataFrame(rows)
    return {'checks': checks, 'records_checked': len(expected), 'verified': verified, 'field_summary': empty,
            'mismatches': mismatches, 'missing_ids': [], 'duplicates': empty, 'scope': f"table {schema}.{table}"}


def _sql_runner(load: Dict) -> Callable[[str], pd.DataFrame]:
    """Queries on the SQL Server connection the load wrote to (by its key, never a copied password)."""
    from ui_components import connection_manager as cm
    from ui_components.data_operations import _sql_query_to_df
    key = (load.get('details') or {}).get('sql_key')
    cfg = cm.sql_connections().get(key) if key else None
    if not cfg:
        # Never fall back to another connection: the same table name elsewhere would be tested instead.
        raise RuntimeError(f"The SQL Server connection the load wrote to ({cm.display_name(key) if key else 'unknown'}) "
                           "is not configured any more — add it again in ⚙️ Configuration to test this load.")
    return lambda query: _sql_query_to_df(cfg, query)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _summary_frame(result: Dict) -> pd.DataFrame:
    return pd.DataFrame([{'Check': c['check'], 'Status': c['status'], 'Detail': c['detail']}
                         for c in result['checks']])


def funnel(dataset: Optional[Dict], validation: Optional[Dict], load: Optional[Dict],
           test: Optional[Dict]) -> List[Tuple[str, Optional[int]]]:
    return [
        ("Step 1 · source rows", (dataset or {}).get('rows')),
        ("Step 2 · valid rows", ((validation or {}).get('summary') or {}).get('valid')),
        ("Step 3 · loaded", (load or {}).get('success')),
        ("Step 4 · verified", (test or {}).get('verified')),
    ]


def _excel_safe(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop the control characters openpyxl refuses to write (they would fail the whole report)."""
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    return frame.map(lambda v: ILLEGAL_CHARACTERS_RE.sub('', v) if isinstance(v, str) else v)


def report_bytes(result: Dict, funnel_rows: List[Tuple[str, Optional[int]]]) -> bytes:
    """Excel report: summary (cycle + checks), fields, mismatches, missing records, duplicates."""
    details = result.get('details') or {}
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        cycle = pd.DataFrame([{'Stage': s, 'Rows': n} for s, n in funnel_rows])
        cycle.to_excel(writer, sheet_name='Summary', index=False)
        _excel_safe(_summary_frame(result)).to_excel(writer, sheet_name='Summary', index=False,
                                                     startrow=len(cycle) + 2)
        for sheet, key in (('Fields', 'field_summary'), ('Mismatches', 'mismatches'), ('Duplicates', 'duplicates')):
            frame = details.get(key)
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                _excel_safe(frame).to_excel(writer, sheet_name=sheet, index=False)
        if details.get('missing_ids'):
            pd.DataFrame({'Missing record Id': details['missing_ids']}).to_excel(
                writer, sheet_name='Missing records', index=False)
    return buffer.getvalue()


def _save_report(result: Dict, funnel_rows) -> Optional[str]:
    """Save the report to the File Library output store; returns the path (None if it failed)."""
    try:
        from ui_components import file_store_manager as fsm
        org = result.get('org') or 'unknown'
        target = str(result.get('target') or 'target').replace('.', '_')
        folder = os.path.join(fsm.OUTPUT_STORE, org, target, 'unit_testing')
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{target}_step4_tests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        with open(path, 'wb') as handle:
            handle.write(report_bytes(result, funnel_rows))
        try:
            fsm.register_output_file(path, org_name=org, object_name=result.get('target') or '',
                                     operation_type='unit_test', row_count=result.get('records_checked', 0),
                                     status='pass' if result.get('failed', 0) == 0 else 'fail')
        except Exception:
            pass
        return path
    except Exception:
        return None


# ---------------------------------------------------------------------------
# UI (the first tab of Step 4)
# ---------------------------------------------------------------------------

def _render_funnel(rows: List[Tuple[str, Optional[int]]]) -> None:
    cols = st.columns(len(rows))
    for col, (label, value) in zip(cols, rows):
        col.metric(label, f"{value:,}" if isinstance(value, int) else "—")


def show_loaded_records_tests(sf_conn) -> None:
    """Tab 1 of Step 4: test the records Step 3 loaded (completes Step 4)."""
    st.subheader("✅ Test Loaded Records")
    st.markdown("Reads back every record Step 3 loaded and checks it against what was sent: counts, existence, "
                "field values, created/changed by this load, and duplicates on the match key.")
    if not step_flow.render_step_gate(4, 'verify'):
        st.caption("The 🔧 Generate, 🏃 Execute and 📊 Reports tabs work without the guided flow.")
        return

    load = step_flow.get_flow_load_result()
    validation = step_flow.get_flow_validation()
    dataset = step_flow.get_flow_dataset()
    test = step_flow.get_flow_test_result()
    _render_funnel(funnel(dataset, validation, load, test))

    details = load.get('details') or {}
    salesforce = load.get('destination') == 'Salesforce'
    if salesforce and not details.get('record_ids'):
        st.warning("⚠️ This load was recorded without its record Ids (it ran before this version). "
                   "Load the rows again in Step 3 to test them here.")
        return
    count = len(details.get('record_ids') or []) if salesforce else int(load.get('success', 0))
    st.info(f"🎯 **Step 3 load:** {load['operation']} into {load['destination']} **{load['target']}** — "
            f"{load['success']:,} loaded, {load['failed']:,} failed, {load['skipped']:,} skipped "
            f"({load['finished_at']}).")

    scope = 'all'
    if salesforce and count > SAMPLE_SIZE:
        options = [f"All {count:,} loaded records", f"A sample of {SAMPLE_SIZE:,} records (evenly spread)"]
        if st.session_state.get('step4_verify_scope') not in options:
            st.session_state['step4_verify_scope'] = options[0] if count <= FULL_CHECK_LIMIT else options[1]
        choice = st.radio("Records to check", options, key='step4_verify_scope', horizontal=True)
        scope = 'all' if choice == options[0] else 'sample'

    if st.button("▶️ Run tests on the loaded records", type="primary", key="step4_run_tests",
                 use_container_width=True):
        progress = st.progress(0.0, text="Reading the loaded records back…")
        try:
            if salesforce:
                if not sf_conn:
                    st.error("❌ The Salesforce connection is not available (see the sidebar).")
                    return
                outcome = verify_salesforce_load(sf_conn, load, validation, scope,
                                                 progress=lambda p: progress.progress(p, text="Reading the "
                                                                                             "loaded records back…"))
            else:
                outcome = verify_sql_load(load, validation, _sql_runner(load))
        except Exception as exc:
            progress.empty()
            st.error(f"❌ The tests could not run: {exc}")
            return
        progress.empty()
        report = {k: outcome[k] for k in ('field_summary', 'mismatches', 'missing_ids', 'duplicates', 'scope')}
        result = step_flow.record_test_result(outcome['checks'], outcome['records_checked'], outcome['verified'],
                                              details=report)
        result['details']['report_path'] = _save_report(result, funnel(dataset, validation, load, result))
        st.rerun()   # redraw the stepper, the summary and the footer with the new result

    if test:
        render_test_results(test, funnel(dataset, validation, load, test))


def render_test_results(result: Dict, funnel_rows) -> None:
    details = result.get('details') or {}
    st.markdown(f"#### 🧪 Results — {details.get('scope', '')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Passed", result['passed'])
    c2.metric("❌ Failed", result['failed'])
    c3.metric("⚠️ Warnings", result['warnings'])
    c4.metric("Verified records", f"{result['verified']:,} / {result['records_checked']:,}")
    frame = _summary_frame(result)
    frame['Status'] = frame['Status'].map(lambda s: ICONS.get(s, s))
    st.dataframe(frame, hide_index=True, use_container_width=True)

    fields = details.get('field_summary')
    if isinstance(fields, pd.DataFrame) and not fields.empty:
        with st.expander(f"🔎 Field by field ({len(fields)} fields)", expanded=bool(result['failed'])):
            st.dataframe(fields, hide_index=True, use_container_width=True)
    mismatches = details.get('mismatches')
    if isinstance(mismatches, pd.DataFrame) and not mismatches.empty:
        with st.expander(f"❌ Differences ({len(mismatches):,} shown)", expanded=True):
            st.dataframe(mismatches.head(200).astype(str), hide_index=True, use_container_width=True)
    if details.get('missing_ids'):
        with st.expander(f"❌ Records not found ({len(details['missing_ids']):,})"):
            st.write(", ".join(details['missing_ids'][:200]))
    duplicates = details.get('duplicates')
    if isinstance(duplicates, pd.DataFrame) and not duplicates.empty:
        with st.expander(f"❌ Duplicate match keys ({len(duplicates):,})", expanded=True):
            st.dataframe(duplicates.head(200).astype(str), hide_index=True, use_container_width=True)

    stamp = result['finished_at'].replace(':', '').replace('-', '')
    target = str(result.get('target') or 'target').replace('.', '_')
    d1, d2 = st.columns(2)
    with d1:
        st.download_button("📥 Download test report (Excel)",
                           lambda: report_bytes(result, funnel_rows), on_click='ignore',
                           file_name=f"{target}_step4_tests_{stamp}.xlsx", key="step4_dl_report",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    with d2:
        if isinstance(mismatches, pd.DataFrame) and not mismatches.empty:
            st.download_button("📥 Download differences (CSV)", lambda: mismatches.to_csv(index=False),
                               on_click='ignore', file_name=f"{target}_step4_differences_{stamp}.csv",
                               mime="text/csv", key="step4_dl_differences", use_container_width=True)
    if details.get('report_path'):
        st.caption(f"💾 The report was also saved to 📁 File Library: `{os.path.basename(details['report_path'])}`")
