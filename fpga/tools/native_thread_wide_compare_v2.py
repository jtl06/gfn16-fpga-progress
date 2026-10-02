"""Unchanged matched wide replay using the callable-fixed runtime identity."""
import hashlib
from pathlib import Path

PRESERVED_COMPARISON_SHA = 'abdd838ced9d91173fd08af6894516b6c167169ec6710d09fea9f93b874f08e4'
_raw = Path(__file__).with_name('native_thread_wide_compare_v1.py').read_bytes()
if hashlib.sha256(_raw).hexdigest() != PRESERVED_COMPARISON_SHA:
    raise ValueError('frozen wide-comparison source')
_text = _raw.decode()
for _old, _new, _count in (
    ('native_threaded_wide_v1.py', 'native_threaded_wide_v2.py', 2),
    ('75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1',
     '0342e1a85f70ec3ba0afe3612f408d9e2ccffb770ebcef7b2e4352f228ff7ff5', 1)
):
    if _text.count(_old) != _count:
        raise ValueError('exact callable-wide comparison anchor')
    _text = _text.replace(_old, _new)
exec(compile(_text, str(Path(__file__).resolve()) + '[callable-runtime-identity]', 'exec'), globals())
