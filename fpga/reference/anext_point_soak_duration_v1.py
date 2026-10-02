"""Explicit point-source binding of the frozen measured100-pilot forecast.

No previous candidate timing is consumed. The existing source/artifact/typed
pilot guards and forecast arithmetic are retained; only the exact point role
and parser identities change. This is not a launcher or numeric generator.
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
    ('from fpga.reference.anext_upper_soak_output_v1 import normalise', 'from fpga.reference.anext_point_soak_output_v1 import normalise'),
    ('anext-upper-qualification-continuous-role-v3', 'anext-point-qualification-continuous-role-v1'),
    ('740d476ba7fbd590c7d3a64ea1a89b4a51dcf2fbc612a71e28cab3bab4202158', 'fe6a0dda35ed7311643f2c9dc9a34f40a9b9017129ca7d0ab2228a7101a23fc0'),
    ('anext-upper-qualification-pilot-role-v3', 'anext-point-qualification-pilot-role-v1'),
    ('reference/anext_upper_soak_output_v1.py', 'reference/anext_point_soak_output_v1.py'),
    ('anext-upper-backend-cycle-duration-v1', 'anext-point-backend-cycle-duration-v1'),
    ('PASS_A_next_upper_measured_backend_cycle_forecast', 'PASS_A_next_point_measured_backend_cycle_forecast'),
    ("native['status']=='PASS_expected_contracts' and native['native_anext_metrics']==metrics",
     "native['status']=='PASS_expected_contracts' and native['candidate']=='A-next-point-v1' and native['candidate_core_sha256']=='f37123255ed08225f9c26a5d556fafb94c4e3eda9547b28713be956cda4cbe7b' and native['native_anext_metrics']==metrics"),
)
for old, new in changes:
    if text.count(old) != 1:
        raise ValueError('one point measured-pilot identity anchor '+old)
    text = text.replace(old, new, 1)
base = types.ModuleType('_frozen_point_measured_pilot_forecast')
base.__file__ = str(Path(__file__).resolve())
exec(compile(text, str(parent)+'[explicit-point-only]', 'exec'), base.__dict__)
predict = base.predict
prepare = base.prepare


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot-dir', type=Path, required=True)
    parser.add_argument('--gate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.pilot_dir, args.gate, args.output), indent=2))
