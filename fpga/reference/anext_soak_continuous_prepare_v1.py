"""Normal-only 1000-square retained-state role; no runner/cap change or arithmetic.

The short pilot supplies the identical driver/validator negative controls.
This stages already-generated continuous assets, not ten independent chunks.
"""
import hashlib,json,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT='reference/anext_soak_prepare_v1.py'
PIN='a1544d997e7d9504596372f612f13f7db8447dab8b4e64efce9a3c6a4e96ccb5'

def implementation():
    raw=(ROOT/PARENT).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('frozen short preparer')
    text=raw.decode()
    changes=[
        ('soak-t5b-aw16-short-reference-q3-v1','soak-t5b-aw16-full-reference-q3-v1'),
        ('ec528027b82c3560ad1ab7109ec1ade3a87e7a32ec782a821449ca8993509018','cbb16451e8ac0273105cb426b3d4ea996125132ff4ae700ad67894063383d2a4'),
        ('70a67b08378f66d4d65178643f7b9ead78dd0d76e0327145f38d8face1fccc9e','51bf3a1c72d278eca68ceb21deedae5dc430369e9c556c90d018aad3e611e62b'),
        ("for name,pin in generation['files'].items():", "for name in ('continuous.txt','continuous.json','plan.json'):\n        pin=generation['files'][name]"),
        ("plan['squares']==2,'short donor recipe'", "plan['squares']==1000 and plan['checkpoint_every']==100,'continuous donor recipe'"),
        ("'tests/test_anext_soak_v1.py','tests/test_anext_soak_prepare_v1.py')", "'tests/test_anext_soak_v1.py','tests/test_anext_soak_prepare_v1.py',\n                 'reference/anext_soak_continuous_prepare_v1.py','tests/test_anext_soak_continuous_prepare_v1.py')"),
        ("for negative in ('none','boundary','loaded-state'):", "for negative in ('none',):"),
        ("operations=2,checkpoint_read_invalidates_prefill=True,expected_prefill_cold=2,", "operations=1000,checkpoint_read_invalidates_prefill=True,expected_prefill_cold=10,"),
        ("expected_cache_loads=1,expected_cache_hits=1,promotion_allowed=False", "expected_cache_loads=1,expected_cache_hits=999,promotion_allowed=False"),
    ]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('exact continuous preparation anchor '+old)
        text=text.replace(old,new)
    module=types.ModuleType('_anext_continuous_preparer');module.__file__=str(ROOT/PARENT)
    exec(compile(text,str(ROOT/PARENT)+'[continuous-assets-only]', 'exec'),module.__dict__)
    return module

def prepare(output):return implementation().prepare(output)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(p.parse_args().output),indent=2))
