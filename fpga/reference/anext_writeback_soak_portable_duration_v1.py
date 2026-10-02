"""Actual-Azure-only F3 measured100 forecast; no GCP timing borrowed."""
import argparse
import hashlib
import json
from pathlib import Path
import types

PARENT_SHA = 'b8ae6ba601c0f8f4bfafd277002ccc384e4a1f4466b1c843249af78d7153098e'
parent = Path(__file__).with_name('anext_writeback_soak_duration_v1.py')
if hashlib.sha256(parent.read_bytes()).hexdigest() != PARENT_SHA:
    raise ValueError('frozen F3 measured100 forecast')
from fpga.reference import anext_writeback_soak_duration_v1 as prior

text = prior.text
changes = (
    ('anext-writeback-qualification-continuous-role-v1', 'anext-writeback-continuous-portable-role-v1'),
    ('f8c142ff564d11f620b1c124651f5d9d2492b1c21ba6e349dffb49f0036bdc48',
     'c4fdb4b4a64ff1cb33aed03a66be4dd18a79b6ca9e899b2cc877c3d9d1fea2f7'),
    ('anext-writeback-qualification-pilot-role-v1', 'anext-writeback-pilot-portable-role-v1'),
    ("r['host']=='gfn16-pilot-c4d'", "r['host'] in TARGETS"),
    ('actual GCP pilot completion', 'actual admitted Azure pilot completion'),
    ("compatible_hosts=['gfn16-pilot-c4d']", "compatible_hosts=[r['host']]"),
    ("native['status']=='PASS_expected_contracts' and native['candidate']=='A-next-writeback-v1'",
     "native['status']=='PASS_expected_contracts' and native['actual_reference_host']==r['host'] and native['generation_reference_host']=='gfn16-pilot-c4d' and native['actual_runtime_manifest_sha256']==TARGETS[r['host']][1] and native['candidate']=='A-next-writeback-v1'"),
    ("step['validator']['source'],'donor/fpga/soak/runtime.json'}",
     "step['validator']['source'],'donor/fpga/soak/runtime.json','portable/target-f16.json','portable/target-burst.json','donor/fpga/reference/core27_t5b_soak_cross_runtime_v1.py'}"),
    ('anext-writeback-backend-cycle-duration-v1', 'anext-writeback-Azure-backend-cycle-duration-v1'),
    ('PASS_A_next_writeback_measured_backend_cycle_forecast', 'PASS_A_next_writeback_Azure_measured_backend_cycle_forecast'),
    ("json.loads(FULL_REFERENCE.read_text())['elapsed_seconds']",
     "json.loads(FULL_REFERENCE.read_text())['elapsed_seconds']"),
)
for old, new in changes:
    if text.count(old) != 1:
        raise ValueError('unique actual-target forecast anchor '+old)
    text = text.replace(old, new, 1)
base = types.ModuleType('_frozen_actual_Azure_F3_forecast')
base.__file__ = str(Path(__file__).resolve())
base.TARGETS = {
    'gfn16-azure-f16': ('target-f16', '1ed8253a93078657227941ea9e1f08d2420dc1a27d992f0e767b2136ebf5f8dc'),
    'gfn16-azure-sim-f32': ('target-burst', '1a5125fa55711298b5412df91105e47aa4c13b6b42ab32191fd8b23696f081f2'),
}
exec(compile(text, str(parent)+'[explicit-actual-Azure]', 'exec'), base.__dict__)
predict = base.predict


def prepare(pilot_dir, gate, output):
    # Frozen body verifies exact compiled/driver/calendar/worker numerical
    # admission and every pilot boundary before copying the continuous role.
    value = base.prepare(pilot_dir, gate, output)
    report = json.loads((Path(pilot_dir)/'report.json').read_text())
    residual = report['seconds'] - sum(row['seconds'] for row in report['steps'])
    if type(residual) not in (int, float) or residual <= 0:
        raise ValueError('positive actual native validation/non-command observation')
    # Full1000 has <=10x100 prefix/reduction work and11 reads vs20; do not
    # use only the different-host original-generation elapsed time.
    replay = max(value['forecast']['full_reference_replay_seconds_estimate'], residual*10*1.75+10)
    value['forecast']['full_reference_replay_seconds_estimate'] = replay
    value['forecast']['actual_target_non_command_seconds_observed'] = residual
    value['forecast']['replay_basis'] = 'At least10x observed actual-target100 non-command time with1.75margin; includes parsing/admission/source checks, conservatively not isolated GMP timing. Original generation measurement retained as additional floor.'
    value['original_generation_reference_host'] = 'gfn16-pilot-c4d'
    value['actual_measured_target_host'] = report['host']
    path = Path(output)/'forecast.json'
    path.write_text(json.dumps(value, indent=2)+'\n')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot-dir', type=Path, required=True)
    parser.add_argument('--gate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.pilot_dir, args.gate, args.output), indent=2))
