"""AppTest entry point: app_step2.py plus a saved picklist value mapping
Industry 'Banking' -> 'Agriculture' for every org/object (restored after each run)."""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for path in (ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

from ui_components import utils as _utils  # noqa: E402

_original_transform = _utils.transform_picklist_value


def _fake_transform(org_name, object_name, field_name, source_value):
    if field_name == 'Industry':
        return {'Banking': 'Agriculture'}.get(str(source_value), source_value)
    return source_value


_utils.transform_picklist_value = _fake_transform
try:
    runpy.run_path(os.path.join(HERE, 'app_step2.py'), run_name='__main__')
finally:
    _utils.transform_picklist_value = _original_transform
