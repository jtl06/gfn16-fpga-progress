"""Identity-only point binding of the frozen retained-evidence consumer.

No native/GMP/full-size arithmetic execution. Actual point PRP/short/pilot
reports are consumed, never reports from the upper or original candidate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types

PARENT_SHA = '891c611d1f115744ef7e7b75a181ccc84f3a74c903d8573ce85d530cc2e0ab3a'
parent = Path(__file__).with_name('anext_upper_qualification_owner_v1.py')
raw = parent.read_bytes()
if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
    raise ValueError('frozen qualification artifact consumer')
text = raw.decode()
changes = (
    ('from fpga.reference.anext_upper_qualification_v3 import verify,CORE', 'from fpga.reference.anext_point_qualification_v1 import verify,CORE'),
    ('from fpga.reference.anext_upper_soak_output_v1 import normalise', 'from fpga.reference.anext_point_soak_output_v1 import normalise'),
    ('from fpga.reference.anext_upper_small_prp_v1 import validate as prp_validate', 'from fpga.reference.anext_point_small_prp_v1 import validate as prp_validate'),
    ("job=f'anext-upper-{kind}-q1-v1'", "job=f'anext-point-{kind}-q3-v1'"),
    ("artifacts/anext-upper-qualification-{kind}-role-v3", "artifacts/anext-point-qualification-{kind}-role-v1"),
    ('rtl/kernel/genefer_anext_upper_core_v1.sv', 'rtl/kernel/genefer_anext_point_core_v1.sv'),
    ('exact upper candidate', 'exact point candidate'),
    ('PASS_owner_upper_qualification_native_replay', 'PASS_owner_point_qualification_native_replay'),
)
for old, new in changes:
    if text.count(old) != 1:
        raise ValueError('one point retained-evidence identity anchor '+old)
    text = text.replace(old, new, 1)
base = types.ModuleType('_frozen_point_qualification_consumer')
base.__file__ = str(Path(__file__).resolve())
exec(compile(text, str(parent)+'[point-source-only]', 'exec'), base.__dict__)
replay = base.replay


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('prp', 'short', 'pilot'))
    args = parser.parse_args()
    print(json.dumps(replay(args.kind), indent=2))
