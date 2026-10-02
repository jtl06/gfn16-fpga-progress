"""F3-only measured100 duration binding, with no inherited candidate timing.

Reuses the byte-pinned finite forecast/source guards. Only the actual F3
parser, calendar, role, and native candidate identities differ. No launcher,
full-N arithmetic, or duration-policy override.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types

PARENT_SHA = 'e5d96ccc03c345812b2bce37e8184f170d5fb4c3ccf2757613d51203099ad2d1'
parent = Path(__file__).with_name('anext_upper_soak_duration_v1.py')
raw = parent.read_bytes()
if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
    raise ValueError('frozen measured pilot forecast adapter')
text = raw.decode()
changes = (
    ('from fpga.reference.anext_point_contract_v1 import schedule',
     'from fpga.reference.anext_writeback_contract_v2 import schedule'),
    ('from fpga.reference.anext_upper_soak_output_v1 import normalise',
     'from fpga.reference.anext_writeback_soak_output_v1 import normalise'),
    ('anext-upper-qualification-continuous-role-v3',
     'anext-writeback-qualification-continuous-role-v1'),
    ('740d476ba7fbd590c7d3a64ea1a89b4a51dcf2fbc612a71e28cab3bab4202158',
     'f8c142ff564d11f620b1c124651f5d9d2492b1c21ba6e349dffb49f0036bdc48'),
    ('anext-upper-qualification-pilot-role-v3',
     'anext-writeback-qualification-pilot-role-v1'),
    ('reference/anext_upper_soak_output_v1.py',
     'reference/anext_writeback_soak_output_v1.py'),
    ('reference/anext_point_contract_v1.py',
     'reference/anext_writeback_contract_v2.py'),
    ('anext-upper-backend-cycle-duration-v1',
     'anext-writeback-backend-cycle-duration-v1'),
    ('PASS_A_next_upper_measured_backend_cycle_forecast',
     'PASS_A_next_writeback_measured_backend_cycle_forecast'),
    ("native['status']=='PASS_expected_contracts' and native['native_anext_metrics']==metrics",
     "native['status']=='PASS_expected_contracts' and native['candidate']=='A-next-writeback-v1' and native['candidate_core_sha256']=='04fe3faa490c83395cec936c40cad15644885ddfd83f008b9f8d7e27da9f8fc9' and native['native_anext_metrics']==metrics"),
)
for old, new in changes:
    if text.count(old) != 1:
        raise ValueError('one F3 measured-pilot identity anchor '+old)
    text = text.replace(old, new, 1)
base = types.ModuleType('_frozen_writeback_measured_pilot_forecast')
base.__file__ = str(Path(__file__).resolve())
exec(compile(text, str(parent)+'[explicit-F3-only]', 'exec'), base.__dict__)
predict = base.predict
prepare = base.prepare

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot-dir', type=Path, required=True)
    parser.add_argument('--gate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.pilot_dir, args.gate, args.output), indent=2))
