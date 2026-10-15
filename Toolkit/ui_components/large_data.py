"""
Support for big source files.

* Uploads: the limit is server.maxUploadSize in .streamlit/config.toml (MB).
  An uploaded file is held in memory, then read into a table that takes a few
  times the file size, and each step keeps its own copy of the rows - so the
  real limit is the memory of the machine running the app. Bigger files can be
  copied into the DataFiles folder and picked from the File Library (read from
  disk, no upload).
* Tables: Streamlit 1.63+ sends a table of more than 150,000 rows to the browser
  page by page (lazy delivery), so a big table never hits the browser message
  limit (server.maxMessageSize). On older Streamlit, st.dataframe shows at most
  DISPLAY_ROW_CAP rows instead; downloads always keep every row.
* memory_warning(): an estimate of the memory needed to read a file, compared
  with the memory that is free, before the file is read.
"""

import os
from typing import Optional

import pandas as pd
import streamlit as st

DISPLAY_ROW_CAP = 100_000

# Memory of one table copy, as a multiple of the file size (measured with pandas 3 on a
# 110 MB / 1M-row CSV: 1.5x). Excel is compressed about 6x, so its table is much bigger.
_TABLE_FACTOR = {'.csv': 1.5, '.txt': 1.5, '.psv': 1.5, '.json': 2.0, '.xlsx': 9.0, '.xls': 3.0}
# Reading needs the file bytes plus the parser's working copies (Excel via openpyxl is far heavier).
# .txt is read with the delimiter-sniffing python engine, which needs several times more than the C parser.
_READ_FACTOR = {'.csv': 2.5, '.txt': 10.0, '.psv': 2.5, '.json': 8.0, '.xlsx': 30.0, '.xls': 12.0}
# The whole cycle keeps ~3 table copies (Step 1, Data Hub, Step 2 valid rows); a Salesforce load
# adds the row payload (~4.7 tables, measured 7x the CSV) and the Step 4 reference (~1.3 tables).
CYCLE_TABLES_SALESFORCE = 9.0

DATAFILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'DataFiles')


def upload_limit_mb() -> int:
    try:
        return int(st.get_option('server.maxUploadSize'))
    except Exception:
        return 200


def _gb(num_bytes: float) -> str:
    return f"{num_bytes / 1024 ** 3:.1f} GB" if num_bytes >= 1024 ** 3 else f"{num_bytes / 1024 ** 2:.0f} MB"


def _ext(file_name: str) -> str:
    return os.path.splitext(file_name.lower())[1]


def memory_estimate(size_bytes: int, file_name: str) -> int:
    """Memory needed to read the file."""
    return int(size_bytes * _READ_FACTOR.get(_ext(file_name), 2.5))


def cycle_estimate(size_bytes: int, file_name: str) -> int:
    """Peak memory of the whole migration cycle when the rows are loaded into Salesforce."""
    return int(size_bytes * _TABLE_FACTOR.get(_ext(file_name), 1.5) * CYCLE_TABLES_SALESFORCE)


def free_memory() -> Optional[int]:
    try:
        import psutil
        return int(psutil.virtual_memory().available)
    except Exception:
        return None


def memory_warning(size_bytes: int, file_name: str) -> Optional[str]:
    """A warning when READING the file may need more memory than is free (None otherwise)."""
    if size_bytes < 50 * 1024 ** 2:
        return None
    need, free = memory_estimate(size_bytes, file_name), free_memory()
    if free is None or need <= 0.8 * free:
        return None
    tip = (" Excel files need far more memory than CSV — save the sheet as CSV first."
           if _ext(file_name) in ('.xlsx', '.xls') else "")
    return (f"⚠️ Reading **{file_name}** ({_gb(size_bytes)}) needs about **{_gb(need)}** of memory, and "
            f"**{_gb(free)}** is free on this machine. Close other programs, or load the data from SQL Server / "
            f"Oracle instead.{tip}")


def cycle_notice(size_bytes: int, file_name: str) -> Optional[str]:
    """A note when the file can be read but a full Salesforce load may run out of memory (None otherwise)."""
    if size_bytes < 50 * 1024 ** 2:
        return None
    need, free = cycle_estimate(size_bytes, file_name), free_memory()
    if free is None or need <= free:
        return None
    return (f"ℹ️ **{file_name}** ({_gb(size_bytes)}) can be read, but validating and loading all of it into "
            f"Salesforce needs up to **{_gb(need)}** of memory while **{_gb(free)}** is free. Close other programs, "
            f"split the file, or load it into SQL Server (needs about a third of that).")


def streamlit_lazy_tables() -> bool:
    """True when this Streamlit delivers big tables lazily (page by page) by itself."""
    try:
        from streamlit.dataframe import lazy_df_source
        return hasattr(lazy_df_source, 'AUTO_LAZY_ROW_THRESHOLD')
    except ImportError:
        return False


def install_dataframe_cap() -> None:
    """On Streamlit without lazy tables: st.dataframe shows at most DISPLAY_ROW_CAP rows (once per process).

    With lazy tables (1.63+) nothing is patched: capping would turn the lazy, paged
    delivery of a big table into one large message - the very limit the cap avoids.
    """
    if streamlit_lazy_tables():
        return
    from streamlit.delta_generator import DeltaGenerator
    if getattr(DeltaGenerator.dataframe, '_dm_capped', False):
        return
    original = DeltaGenerator.dataframe

    def dataframe(self, data=None, *args, **kwargs):
        if isinstance(data, pd.DataFrame) and len(data) > DISPLAY_ROW_CAP:
            total = len(data)
            result = original(self, data.head(DISPLAY_ROW_CAP), *args, **kwargs)
            self.caption(f"Showing the first {DISPLAY_ROW_CAP:,} of {total:,} rows — the downloads contain "
                         f"every row.")
            return result
        return original(self, data, *args, **kwargs)

    dataframe._dm_capped = True
    dataframe.__doc__ = original.__doc__
    DeltaGenerator.dataframe = dataframe
    # st.dataframe is bound to the main container at import time; rebind it.
    st.dataframe = dataframe.__get__(st._main, DeltaGenerator)
