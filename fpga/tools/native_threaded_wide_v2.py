"""Callable wait4 binding fix over the preserved fixed-wide pilot runner.

The v1 source and its unsubmitted packets remain intact. Only the incorrect
module-versus-class binding, this launcher's SELF and source dependency change;
the exact short role, allocation, tools, locks, quotas and bounds do not change.
"""
import hashlib
from pathlib import Path

PRESERVED_WIDE_V1_SHA = '75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1'
_previous_path = Path(__file__).with_name('native_threaded_wide_v1.py')
_previous_raw = _previous_path.read_bytes()
if hashlib.sha256(_previous_raw).hexdigest() != PRESERVED_WIDE_V1_SHA:
    raise ValueError('frozen wide-v1 source identity')
_adapted_text = _previous_raw.decode()
for _before, _after in (
    ("SELF = 'tools/native_threaded_wide_v1.py'", "SELF = 'tools/native_threaded_wide_v2.py'"),
    ("MeasuredPopen=inherited.load('native_child_usage_v1.py', inherited.USAGE_SHA), validate_threaded=validate_threaded)",
     "MeasuredPopen=inherited.load('native_child_usage_v1.py', inherited.USAGE_SHA).MeasuredPopen, validate_threaded=validate_threaded)"),
    ("return dict(base().PINS, **{'tools/native_threaded_class_v1.py': BASE_SHA,",
     "return dict(base().PINS, **{'tools/native_threaded_wide_v1.py': '" + PRESERVED_WIDE_V1_SHA + "', 'tools/native_threaded_class_v1.py': BASE_SHA,")
):
    if _adapted_text.count(_before) != 1:
        raise ValueError('unique callable-wide successor source anchor')
    _adapted_text = _adapted_text.replace(_before, _after, 1)
# All successor functions share THIS final module namespace, including the
# real __file__, SELF, dependency pins and factories used by native execution.
exec(compile(_adapted_text, str(Path(__file__).resolve()) + '[callable-binding-fix]', 'exec'), globals())
