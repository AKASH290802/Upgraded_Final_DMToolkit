"""
Guided migration cycle:
    1 Source/Target Information -> 2 Mapping & Validation -> 3 Data Operations -> 4 Unit Testing

Each step hands its result to the next through plain session keys (not widget
keys, which Streamlit drops when a page is not drawn):

    flow_dataset      set by Step 1 when the user confirms a dataset
    flow_validation   set by Step 2 when a validation run finishes
    flow_load_result  set by Step 3 when a load finishes (with the loaded record Ids)
    flow_test_result  set by Step 4 when the loaded records have been tested

A step is "done" only if its result belongs to the current sidebar org and to
the current result of the step before it, so changing the dataset in Step 1
automatically re-locks Steps 2-4. The Next button of a step is disabled until
the step is done; the tabs inside a step are optional and always have
Previous / Next buttons.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import pandas as pd
import streamlit as st

from ui_components.navigation import (
    STEP1_PAGE, STEP2_PAGE, STEP3_PAGE, STEP4_PAGE, request_page,
)

STEPS = [
    {'num': 1, 'page': STEP1_PAGE, 'title': 'Source/Target Information', 'short': 'Source / Target', 'icon': '🧭',
     'desc': 'Choose the source data and the target object'},
    {'num': 2, 'page': STEP2_PAGE, 'title': 'Mapping & Validation', 'icon': '🔗',
     'desc': 'Map columns to Salesforce fields and validate the rows'},
    {'num': 3, 'page': STEP3_PAGE, 'title': 'Data Operations', 'icon': '🚀',
     'desc': 'Load the validated rows into Salesforce or SQL Server'},
    {'num': 4, 'page': STEP4_PAGE, 'title': 'Unit Testing', 'icon': '🧪',
     'desc': 'Test the loaded records in the target'},
]

# The results of the cycle, oldest first. A new result of step N drops the ones after it.
FLOW_RESULT_KEYS = ('flow_dataset', 'flow_validation', 'flow_load_result', 'flow_test_result')

# Columns validation adds for display; they must not be loaded into a target.
VALIDATION_META_COLUMNS = [
    'Transform_Status', 'Transform_Reason', 'Validation_Details', 'Data_Issue_Details',
    'Validation_Status', 'Validation_Errors', 'Error_Details', 'Row_Number',
]


# ---------------------------------------------------------------------------
# Step 1 result: the dataset
# ---------------------------------------------------------------------------

def set_flow_dataset(df: pd.DataFrame, name: str, object_name: str, source_type: str,
                     source_label: str, details: Optional[Dict] = None,
                     dataset_id: Optional[str] = None) -> str:
    """Store the confirmed Step 1 dataset (in the Data Hub) and reset Steps 2-4."""
    from ui_components.data_hub import initialize_data_hub
    hub = initialize_data_hub()
    org = st.session_state.get('current_org')
    previous = st.session_state.get('flow_dataset') or {}
    unchanged = bool(dataset_id and previous.get('id') == dataset_id and previous.get('object') == object_name
                     and previous.get('org') == org)
    source_details = dict(details or {})
    source_details.update({'org': org, 'target_object': object_name, 'source_label': source_label,
                           'sql_connection': st.session_state.get('current_sql_connection'),
                           'oracle_connection': st.session_state.get('current_oracle_connection')})
    if dataset_id and dataset_id in hub.cached_datasets:
        hub.set_active_dataset(dataset_id)
        hub.rename_dataset(dataset_id, name)
        hub.cached_datasets[dataset_id]['metadata']['source_details'].update(
            {'org': org, 'target_object': object_name})
    else:
        dataset_id = hub.add_dataset(df=df, dataset_name=name, source_type=source_type,
                                     source_details=source_details, set_active=True)
    st.session_state.flow_dataset = {
        'id': dataset_id, 'name': name, 'org': org, 'object': object_name,
        'source_type': source_type, 'source_label': source_label,
        'rows': int(len(df)), 'cols': int(len(df.columns)),
        'columns': [str(c) for c in df.columns],
        'confirmed_at': datetime.now().isoformat(timespec='seconds'),
    }
    st.session_state.current_object = object_name
    if not unchanged:  # same data + same object again: Steps 2-4 stay valid
        st.session_state.pop('flow_validation', None)
        st.session_state.pop('flow_load_result', None)
        st.session_state.pop('flow_test_result', None)
        st.session_state.pop('flow_field_mappings', None)
    return dataset_id


def get_flow_dataset() -> Optional[Dict]:
    """The Step 1 dataset record if it is still valid for the sidebar org."""
    dataset = st.session_state.get('flow_dataset')
    if not dataset or dataset.get('org') != st.session_state.get('current_org'):
        return None
    hub = st.session_state.get('data_hub')
    if hub is None or dataset.get('id') not in hub.cached_datasets:
        return None
    return dataset


def get_flow_df() -> Optional[pd.DataFrame]:
    """A copy of the Step 1 DataFrame, or None."""
    dataset = get_flow_dataset()
    if not dataset:
        return None
    return st.session_state.data_hub.get_dataset(dataset['id'])


def get_flow_object() -> Optional[str]:
    dataset = get_flow_dataset()
    return dataset.get('object') if dataset else None


def step1_done() -> bool:
    dataset = get_flow_dataset()
    return bool(dataset and dataset.get('object') and dataset.get('rows', 0) > 0)


# ---------------------------------------------------------------------------
# Shared Step 2 field mapping (one mapping for every validation tab and Step 3)
# ---------------------------------------------------------------------------

def get_flow_mappings() -> Dict[str, str]:
    """{source column: Salesforce field} for the Step 1 dataset + object ({} when none yet).

    Every Step 2 mapping grid reads this first and writes it back, so a mapping
    made in one tab is the mapping of all tabs (and of what Step 3 loads).
    """
    store = st.session_state.get('flow_field_mappings')
    dataset = get_flow_dataset()
    if not store or not dataset or store.get('dataset_id') != dataset['id']             or store.get('object') != dataset.get('object') or store.get('org') != dataset.get('org'):
        return {}
    return dict(store.get('map') or {})


def set_flow_mappings(mappings: Dict[str, str]) -> bool:
    """Store the shared mapping; returns True if it changed. No-op without a Step 1 dataset."""
    dataset = get_flow_dataset()
    if not dataset:
        return False
    clean = {str(k): v for k, v in (mappings or {}).items()
             if v and v not in ('-- Skip Field --', '⚠️ No mapping', '')}
    if clean == get_flow_mappings():
        return False
    st.session_state.flow_field_mappings = {
        'org': dataset.get('org'), 'object': dataset.get('object'), 'dataset_id': dataset['id'],
        'map': clean, 'version': (st.session_state.get('flow_field_mappings') or {}).get('version', 0) + 1,
    }
    return True


def flow_mappings_version() -> int:
    """Changes whenever the shared mapping changes (grids use it to re-seed their widgets)."""
    return int((st.session_state.get('flow_field_mappings') or {}).get('version', 0)) if get_flow_mappings() else 0


# ---------------------------------------------------------------------------
# Step 2 result: the validated rows
# ---------------------------------------------------------------------------

def publish_validation_result(method: str, object_name: str, valid_df: pd.DataFrame,
                              invalid_df: Optional[pd.DataFrame] = None,
                              field_mappings: Optional[Dict] = None,
                              lookups_resolved: bool = False,
                              lookup_configs: Optional[Dict] = None,
                              used_flow_dataset: bool = True,
                              summary: Optional[Dict] = None,
                              match: Optional[Dict] = None) -> Dict:
    """Record the result of a validation run so Step 3 can load it.

    valid_df keeps the SOURCE column names (field_mappings maps them to
    Salesforce API names); validation-only display columns are dropped.
    used_flow_dataset must be False when the run validated some other source
    than the Step 1 dataset - such a result is kept but does not unlock Step 3.
    match: the record-matching choice made in Step 2, e.g.
    {'strategy': 'External ID', 'fields': ['External_Key__c'], 'separator': '_'},
    which Step 3 uses as the default Insert/Update/Upsert key.
    """
    valid_df = valid_df if valid_df is not None else pd.DataFrame()
    valid_clean = valid_df.drop(columns=[c for c in VALIDATION_META_COLUMNS if c in valid_df.columns])
    invalid_df = invalid_df if invalid_df is not None else pd.DataFrame()
    mappings = {str(k): v for k, v in (field_mappings or {}).items()
                if v and v not in ('-- Skip Field --', '⚠️ No mapping', '')}
    dataset = get_flow_dataset()
    result = {
        'id': uuid.uuid4().hex,
        'method': method,
        'org': st.session_state.get('current_org'),
        'object': object_name,
        'dataset_id': dataset['id'] if (dataset and used_flow_dataset) else None,
        'valid_df': valid_clean.reset_index(drop=True),
        'invalid_df': invalid_df.reset_index(drop=True),
        'field_mappings': mappings,
        'lookups_resolved': bool(lookups_resolved),
        'lookup_configs': dict(lookup_configs or {}),
        'match': dict(match or {}),
        'summary': {
            'total': int(len(valid_clean) + len(invalid_df)),
            'valid': int(len(valid_clean)),
            'invalid': int(len(invalid_df)),
            **(summary or {}),
        },
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    st.session_state.flow_validation = result
    st.session_state.pop('flow_load_result', None)
    st.session_state.pop('flow_test_result', None)
    return result


def get_flow_validation(any_source: bool = False) -> Optional[Dict]:
    """The Step 2 result if it belongs to the sidebar org and the Step 1 dataset."""
    result = st.session_state.get('flow_validation')
    if not result or result.get('org') != st.session_state.get('current_org'):
        return None
    if any_source:
        return result
    dataset = get_flow_dataset()
    if not dataset or result.get('dataset_id') != dataset.get('id'):
        return None
    return result


def step2_done() -> bool:
    result = get_flow_validation()
    return bool(step1_done() and result and result['summary'].get('valid', 0) > 0)


def _step2_blocker() -> str:
    if not step1_done():
        return "Finish Step 1 first."
    result = st.session_state.get('flow_validation')
    if not result or result.get('org') != st.session_state.get('current_org'):
        return "Run a validation (Schema, Enhanced, Custom or SF Validation Rules) on the Step 1 dataset."
    if result.get('dataset_id') != (get_flow_dataset() or {}).get('id'):
        return ("The last validation ran on a different data source than the Step 1 dataset. "
                "Validate the Step 1 dataset, or load the other data in Step 1.")
    if result['summary'].get('valid', 0) == 0:
        return "The last validation found no valid rows to load. Fix the data or mappings and validate again."
    return ""


# ---------------------------------------------------------------------------
# Step 3 result: the load
# ---------------------------------------------------------------------------

def record_load_result(destination: str, target: str, operation: str,
                       success: int, failed: int, skipped: int = 0, *,
                       total: Optional[int] = None, details: Optional[Dict] = None) -> Dict:
    """Record a Step 3 load (and drop an older Step 4 result).

    total: rows sent to the load (default success + failed + skipped); Step 4
    reports rows that are in none of the three counts.
    details: what Step 4 needs to test exactly what was loaded, e.g. for
    Salesforce {'record_ids', 'expected' (DataFrame of the values sent, one row
    per record id), 'created', 'row_positions', 'match', 'started_at_utc',
    'failed_rows'}; for SQL Server {'sql_key', 'schema', 'table', 'mode',
    'expected', 'before_count', 'final_count'}.
    """
    validation = get_flow_validation(any_source=True)
    result = {
        'id': uuid.uuid4().hex,
        'validation_id': validation['id'] if validation else None,
        'org': st.session_state.get('current_org'),
        'destination': destination, 'target': target, 'operation': operation,
        'success': int(success), 'failed': int(failed), 'skipped': int(skipped),
        'total': int(total if total is not None else int(success) + int(failed) + int(skipped)),
        'finished_at': datetime.now().isoformat(timespec='seconds'),
        'details': dict(details or {}),
    }
    st.session_state.flow_load_result = result
    st.session_state.pop('flow_test_result', None)
    return result


def get_flow_load_result() -> Optional[Dict]:
    result = st.session_state.get('flow_load_result')
    validation = get_flow_validation()
    if not result or not validation or result.get('validation_id') != validation['id']:
        return None
    return result


def step3_done() -> bool:
    result = get_flow_load_result()
    return bool(step2_done() and result and result.get('success', 0) > 0)


# ---------------------------------------------------------------------------
# Step 4 result: the tests of the loaded records
# ---------------------------------------------------------------------------

TEST_STATUSES = ('PASS', 'FAIL', 'WARN', 'SKIP')


def record_test_result(checks: List[Dict], records_checked: int, verified: int,
                       details: Optional[Dict] = None) -> Dict:
    """Record a Step 4 run. checks: [{'check', 'status' (PASS/FAIL/WARN/SKIP), 'detail'}].

    records_checked: loaded records the run looked at; verified: those that
    exist in the target with every compared value equal.
    """
    load = get_flow_load_result()
    counts = {s: sum(1 for c in checks if c.get('status') == s) for s in TEST_STATUSES}
    result = {
        'id': uuid.uuid4().hex,
        'load_id': load.get('id') if load else None,
        'org': st.session_state.get('current_org'),
        'destination': load.get('destination') if load else None,
        'target': load.get('target') if load else None,
        'checks': [dict(c) for c in checks],
        'total': len(checks),
        'passed': counts['PASS'], 'failed': counts['FAIL'],
        'warnings': counts['WARN'], 'skipped': counts['SKIP'],
        'records_checked': int(records_checked), 'verified': int(verified),
        'finished_at': datetime.now().isoformat(timespec='seconds'),
        'details': dict(details or {}),
    }
    st.session_state.flow_test_result = result
    return result


def get_flow_test_result() -> Optional[Dict]:
    """The Step 4 result if it tested the current Step 3 load."""
    result = st.session_state.get('flow_test_result')
    load = get_flow_load_result()
    if not result or not load or not load.get('id') or result.get('load_id') != load['id']:
        return None
    return result


def step4_done() -> bool:
    result = get_flow_test_result()
    return bool(step3_done() and result and result.get('total', 0) > 0)


def step4_all_passed() -> bool:
    return bool(step4_done() and get_flow_test_result().get('failed', 0) == 0)


# ---------------------------------------------------------------------------
# Status per step
# ---------------------------------------------------------------------------

def step_done(num: int) -> bool:
    return {1: step1_done, 2: step2_done, 3: step3_done, 4: step4_done}[num]()


def step_has_issues(num: int) -> bool:
    """A finished step whose result needs a look (Step 4 with failed checks)."""
    return num == 4 and step4_done() and not step4_all_passed()


def step_blocker(num: int) -> str:
    """Why step num is not done yet ('' when done)."""
    if step_done(num):
        return ""
    if num == 1:
        org = st.session_state.get('current_org')
        if not org:
            return "Select a Salesforce org in the sidebar."
        from ui_components.connection_manager import get_sf_connection_error
        if get_sf_connection_error(org):
            return f"Connect to {org} first — the login failed (see the sidebar)."
        return "Load a dataset, choose the target object and click ✅ Use this dataset."
    if num == 2:
        return _step2_blocker()
    if num == 3:
        if not step2_done():
            return "Finish Step 2 first."
        return "Load the validated rows (at least one record must succeed)."
    if not step3_done():
        return "Finish Step 3 first."
    return "Run ✅ Test Loaded Records on the records Step 3 loaded."


def step_unlocked(num: int) -> bool:
    """A step can be worked on once every step before it is done."""
    return all(step_done(n) for n in range(1, num))


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def render_stepper(current: int) -> None:
    """Progress header shown at the top of every step page.

    Colours come from the .dm-step--<kind> classes in theme.py, which follow the theme
    on screen in the browser (light and dark values for every kind).
    """
    labels = {
        'done': "✅ Done",
        'done_issues': "⚠️ Done — some checks failed",
        'current': "🟠 Current",
        'here_locked': "🔒 Locked (you are here)",
        'ready': "⏳ Ready",
        'locked': "🔒 Locked",
    }
    cols = st.columns(len(STEPS))
    for col, step in zip(cols, STEPS):
        num = step['num']
        if step_done(num):
            kind = 'done_issues' if step_has_issues(num) else 'done'
        elif num == current and step_unlocked(num):
            kind = 'current'
        elif num == current:
            kind = 'here_locked'
        elif step_unlocked(num):
            kind = 'ready'
        else:
            kind = 'locked'
        classes = f"dm-step dm-step--{kind}" + (" is-current" if num == current else "")
        with col:
            # Two lines per card (state + title); the description is the hover tooltip.
            st.markdown(
                f'<div class="{classes}" title="{step["desc"]}">'
                f'<div class="state">STEP {num} · {labels[kind]}</div>'
                f'<div class="title">{step["icon"]} {step.get("short", step["title"])}</div></div>',
                unsafe_allow_html=True,
            )
    done = sum(step_done(s['num']) for s in STEPS)
    st.progress(done / len(STEPS), text=f"Guided migration: {done} of {len(STEPS)} steps complete")


def render_step_gate(num: int, key_suffix: str = "") -> bool:
    """Show a lock card when an earlier step is unfinished. Returns True if unlocked.

    key_suffix must be unique when the gate is drawn more than once on a page
    (e.g. once per tab).
    """
    if step_unlocked(num):
        return True
    first_open = next(n for n in range(1, num) if not step_done(n))
    step = STEPS[first_open - 1]
    st.warning(f"🔒 **Step {num} is locked.** {step_blocker(first_open)}")
    st.button(f"⬅️ Go to Step {first_open}: {step['title']}",
              key=f"flow_gate_{num}_{first_open}_{key_suffix}",
              on_click=request_page, args=(step['page'],), type="primary")
    return False


def render_dataset_card() -> None:
    """Summary of the Step 1 dataset, for Steps 2 and 3."""
    dataset = get_flow_dataset()
    if not dataset:
        return
    st.info(f"📦 **Step 1 dataset:** {dataset['name']} — {dataset['rows']:,} rows × {dataset['cols']} columns "
            f"from {dataset['source_label']}  →  target object **{dataset['object']}**")


def render_validation_result_card(key_prefix: str = "flow_val") -> None:
    """Latest Step 2 result with downloads; survives reruns and page switches."""
    result = get_flow_validation(any_source=True)
    if not result:
        return
    summary = result['summary']
    counts_for_flow = result.get('dataset_id') == (get_flow_dataset() or {}).get('id')
    with st.container(border=True):
        st.markdown(f"#### 📋 Latest validation result — {result['method']} on **{result['object']}**")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total rows", f"{summary['total']:,}")
        c2.metric("✅ Valid", f"{summary['valid']:,}")
        c3.metric("❌ Invalid", f"{summary['invalid']:,}")
        c4.metric("Mapped fields", len(result['field_mappings']))
        if not counts_for_flow:
            st.caption("ℹ️ This run used a different source than the Step 1 dataset, so it does not unlock Step 3.")
        d1, d2 = st.columns(2)
        stamp = result['created_at'].replace(':', '').replace('-', '')
        with d1:
            if not result['valid_df'].empty:
                st.download_button("📥 Download valid rows", lambda df=result['valid_df']: df.to_csv(index=False),
                                   on_click='ignore',
                                   file_name=f"{result['object']}_valid_{stamp}.csv", mime="text/csv",
                                   key=f"{key_prefix}_dl_valid", use_container_width=True)
        with d2:
            if not result['invalid_df'].empty:
                st.download_button("📥 Download invalid rows", lambda df=result['invalid_df']: df.to_csv(index=False),
                                   on_click='ignore',
                                   file_name=f"{result['object']}_invalid_{stamp}.csv", mime="text/csv",
                                   key=f"{key_prefix}_dl_invalid", use_container_width=True)


def render_load_result_card() -> None:
    result = get_flow_load_result()
    if not result:
        return
    st.success(f"✅ **Step 3 load finished** — {result['operation']} into {result['destination']} "
               f"**{result['target']}**: {result['success']:,} succeeded, {result['failed']:,} failed"
               + (f", {result['skipped']:,} skipped" if result['skipped'] else "")
               + f" ({result['finished_at']})")


def render_test_result_card() -> None:
    """One line about the latest Step 4 run (drawn above the Step 4 tabs)."""
    result = get_flow_test_result()
    if not result:
        return
    text = (f"🧪 **Step 4 tests finished** on {result['destination']} **{result['target']}** — "
            f"{result['passed']} passed, {result['failed']} failed, {result['warnings']} warnings; "
            f"{result['verified']:,} of {result['records_checked']:,} checked records verified "
            f"({result['finished_at']})")
    (st.success if result['failed'] == 0 else st.warning)(text)


# ---------------------------------------------------------------------------
# Tabs inside a step: Previous / Next buttons (every tab is optional)
# ---------------------------------------------------------------------------

_SCROLL_KEY = '_dm_scroll_to_tabs'


def _tab_mirror(key: str) -> str:
    return f"_{key}_mirror"


def keyed_tabs(labels: Sequence[str], key: str):
    """st.tabs that tracks the open tab (Streamlit >= 1.63) and remembers it across page switches.

    Streamlit drops a widget's state when its page is not drawn, so the open tab
    is mirrored in a plain session key and restored from it. Returns
    (containers, open_flags); with older Streamlit every tab counts as open.
    """
    import inspect
    labels = list(labels)
    if 'on_change' not in inspect.signature(st.tabs).parameters:
        return st.tabs(labels), [True] * len(labels)
    mirror = _tab_mirror(key)
    if st.session_state.get(key) not in labels:
        st.session_state.pop(key, None)
        if st.session_state.get(mirror) in labels:
            st.session_state[key] = st.session_state[mirror]
    tabs = st.tabs(labels, key=key, on_change='rerun')
    if st.session_state.get(key) in labels:
        st.session_state[mirror] = st.session_state[key]
    return tabs, [tab.open is not False for tab in tabs]


def open_tab_index(labels: Sequence[str], key: str) -> int:
    """Index of the open tab of keyed_tabs(labels, key) (0 before the first switch)."""
    labels = list(labels)
    value = st.session_state.get(key)
    if value not in labels:
        value = st.session_state.get(_tab_mirror(key))
    return labels.index(value) if value in labels else 0


def open_tab(key: str, label: str) -> None:
    """Open a tab of keyed_tabs on the next draw (call before the tabs are drawn)."""
    st.session_state[key] = label
    st.session_state[_tab_mirror(key)] = label


def _go_to_tab(state_key: str, value, mirror_key: Optional[str] = None) -> None:
    """on_click: open another tab (runs before the page is drawn again)."""
    st.session_state[state_key] = value
    st.session_state[mirror_key or _tab_mirror(state_key)] = value
    count = int(st.session_state.get(_SCROLL_KEY + '_count', 0)) + 1
    st.session_state[_SCROLL_KEY + '_count'] = count
    st.session_state[_SCROLL_KEY] = (count, state_key)   # only the nav of these tabs scrolls


def _scroll_to_tabs(anchor: Optional[str], state_key: Optional[str] = None) -> None:
    """After a Previous/Next click, scroll the tab bar back into view (the buttons sit below the tab).

    Only the nav of the tabs that were switched does it, so a nav of inner tabs drawn
    earlier on the page (e.g. Step 4 > Reports) does not take the scroll.
    """
    request = st.session_state.get(_SCROLL_KEY)
    if not request:
        return
    count, target = request if isinstance(request, tuple) else (request, None)
    if target is not None and state_key is not None and target != state_key:
        return
    st.session_state.pop(_SCROLL_KEY, None)
    selector = json.dumps(anchor or '[data-testid="stTabs"]')
    try:
        st.html(f"""<script>/* dm-tab-scroll {count} */
setTimeout(function () {{
  var el = document.querySelector({selector});
  if (el) {{ el.style.scrollMarginTop = '72px'; el.scrollIntoView({{behavior: 'smooth', block: 'start'}}); }}
  else {{ window.scrollTo({{top: 0, behavior: 'smooth'}}); }}
}}, 80);
</script>""", unsafe_allow_javascript=True)
    except TypeError:  # Streamlit without unsafe_allow_javascript: the tab still switches
        pass


def render_tab_nav(labels: Sequence[str], current: int, state_key: str, key: str,
                   values: Optional[Sequence] = None, mirror_key: Optional[str] = None,
                   anchor: Optional[str] = None) -> None:
    """Previous / Next buttons between the tabs of a page.

    The tabs are optional, so both buttons are always enabled. A click stores
    values[i] (default: the label) in st.session_state[state_key] - the key of a
    keyed st.tabs, or the page's own active-tab key - and scrolls back up to the
    tab bar (anchor: CSS selector of it; default the first st.tabs).
    """
    labels = list(labels)
    values = list(values) if values is not None else labels
    if len(labels) < 2:
        return
    current = max(0, min(int(current), len(labels) - 1))
    col_prev, col_msg, col_next = st.columns([1.4, 2.2, 1.4], vertical_alignment="center")
    with col_prev:
        if current > 0:
            st.button(f"⬅️ Previous: {labels[current - 1]}", key=f"{key}_prev", use_container_width=True,
                      on_click=_go_to_tab, args=(state_key, values[current - 1], mirror_key))
    with col_msg:
        st.caption(f"📑 Tab {current + 1} of {len(labels)} · **{labels[current]}** — the tabs are optional; "
                   f"use only the ones you need.")
    with col_next:
        if current < len(labels) - 1:
            st.button(f"Next: {labels[current + 1]} ➡️", key=f"{key}_next", use_container_width=True,
                      on_click=_go_to_tab, args=(state_key, values[current + 1], mirror_key))
    _scroll_to_tabs(anchor, state_key)


# ---------------------------------------------------------------------------
# Step footer and header
# ---------------------------------------------------------------------------

def start_new_migration() -> None:
    """on_click of the last step: clear the cycle's results and open Step 1 (connections stay)."""
    from ui_components.connection_manager import STAGED_KEY
    for key in FLOW_RESULT_KEYS + ('flow_field_mappings', STAGED_KEY):
        st.session_state.pop(key, None)
    # Step 1 starts empty: its remembered picks (file, table, query, target object...) would load the
    # previous cycle's data again. The kind of source (e.g. SQL Server) stays chosen.
    keep = {'step1_source', 'step1_source__saved'}
    for key in [k for k in list(st.session_state.keys())
                if isinstance(k, str) and (k.startswith('step1_') or k.startswith('_step1_')) and k not in keep]:
        st.session_state.pop(key, None)
    st.session_state['_flow_restart_notice'] = True
    request_page(STEP1_PAGE)


def render_step_footer(num: int, tab_nav: Optional[Dict] = None) -> None:
    """Tab Previous / Next (optional tabs) above the step Back / Next buttons.

    Next is disabled until the step is done; on the last step it starts a new
    migration. tab_nav: the arguments of render_tab_nav for a page with tabs.
    """
    st.divider()
    if tab_nav:
        render_tab_nav(**tab_nav)
    done = step_done(num)
    last = num == len(STEPS)
    col_back, col_msg, col_next = st.columns([1.2, 3.6, 1.2])
    with col_back:
        if num > 1:
            prev = STEPS[num - 2]
            st.button(f"⬅️ Back: {prev['title']}", key=f"flow_back_{num}", use_container_width=True,
                      on_click=request_page, args=(prev['page'],))
    with col_msg:
        if done and not last:
            st.success(f"✅ Step {num} complete — continue to Step {num + 1}.")
        elif done and step_has_issues(num):
            result = get_flow_test_result()
            st.warning(f"⚠️ **Migration cycle finished with {result['failed']} failed check(s).** Review them "
                       "below, fix the data and load again (Step 3), or start a new migration.")
        elif done:
            st.success(f"🎉 **Migration cycle complete** — all {len(STEPS)} steps are done and every check "
                       "passed. Start the next migration when you are ready.")
        else:
            st.caption(f"⏳ **Next is disabled:** {step_blocker(num)}")
    with col_next:
        if not last:
            nxt = STEPS[num]
            st.button(f"Next: {nxt['title']} ➡️", key=f"flow_next_{num}", type="primary",
                      disabled=not done, use_container_width=True,
                      on_click=request_page, args=(nxt['page'],))
        else:
            st.button("🔁 Start a new migration", key=f"flow_next_{num}", type="primary",
                      disabled=not done, use_container_width=True, on_click=start_new_migration,
                      help="Clears this migration's results and opens Step 1. The connections, the Data Hub "
                           "datasets and all saved files stay.")


def render_step_header(num: int, subtitle: str = "") -> None:
    """Title + stepper + connection banner for a step page."""
    from ui_components.connection_manager import render_connection_banner
    step = STEPS[num - 1]
    st.title(f"{step['icon']} Step {num} · {step['title']}")
    if subtitle:
        st.caption(subtitle)   # a muted line under the title, not body-size text
    render_stepper(num)
    render_connection_banner()
    notice = st.session_state.pop('_org_change_notice', None)
    if notice:
        kept = (" Your Step 1 data is still staged — choose the target object and click "
                "✅ Use this dataset again." if notice.get('kept_staged') else "")
        st.info(f"🔄 The sidebar org changed from **{notice['from']}** to **{notice['to'] or 'none'}**, "
                f"so the guided flow was reset (target objects, mappings and validations belong to one org).{kept}")
    if st.session_state.pop('_flow_restart_notice', None):
        st.info("🔁 **New migration started.** The previous cycle's results were cleared — load the next "
                "dataset here. Its files and Data Hub datasets are still available.")


def default_to_flow_object(widget_key: str, options, placeholders=('',)) -> None:
    """Pre-select the guided flow's object in a picker (Step 1 target, else the current object).

    Call BEFORE the widget is drawn. Only fills an empty picker (no value, or one of the
    placeholders such as '-- Select Object --'), so a user's real choice stays.
    """
    if st.session_state.get(widget_key) not in (None,) + tuple(placeholders):
        return
    candidate = get_flow_object() or st.session_state.get('current_object')
    if candidate and candidate in list(options):
        st.session_state[widget_key] = candidate
