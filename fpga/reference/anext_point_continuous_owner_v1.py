"""Consume only the point-specific actual uninterrupted1000 terminal result.

Retains the reviewed-style artifact/parser path; never runs HDL or full-N
arithmetic. The new fixed bound-role and raw1000 contract cannot accept a
prior original/upper run or a100-operation pilot as this terminal gate.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[1]
PARENT_SHA = '8514a2159ef61b3b90c59fe862567fcac455cfeed74ab0d4295abb5f6a34f32a'
ROLE_SHA = '22ba1130b769e91faaa0ba458bd51135e2b0c070ee4688031945637a76155c9e'
parent = Path(__file__).with_name('anext_point_qualification_owner_v1.py')
if hashlib.sha256(parent.read_bytes()).hexdigest() != PARENT_SHA:
    raise ValueError('frozen point qualification consumer')
spec = importlib.util.spec_from_file_location('_fixed_point_consumer_parent', parent)
parent_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent_module)
text = parent_module.text
changes = (
    ("need(kind in ('prp','short','pilot'),'finite observed qualification')", "need(kind=='continuous','exact uninterrupted1000 only')"),
    ("job=f'anext-point-{kind}-q3-v1'", "job='anext-point-continuous-aw16-q3-v1'"),
    ("role=ROOT/f'artifacts/anext-point-qualification-{kind}-role-v1';rm=json.loads(read(role/'manifest.json'))",
     "role=ROOT/'artifacts/anext-point-continuous-bound-role-v1';rm=json.loads(read(role/'manifest.json','"+ROLE_SHA+"'))"),
    ('PASS_owner_point_qualification_native_replay', 'PASS_owner_point_uninterrupted1000_native_replay'),
)
for old, new in changes:
    if text.count(old) != 1:
        raise ValueError('one continuous evidence identity anchor '+old)
    text = text.replace(old, new, 1)
base = types.ModuleType('_fixed_point_continuous_consumer')
base.__file__ = str(Path(__file__).resolve())
exec(compile(text, '[point actual continuous1000 evidence only]', 'exec'), base.__dict__)


def consume():
    result = base.replay('continuous')
    directory = ROOT/'queue/evidence/anext-point-continuous-aw16-q3-v1/attempt-0/collected/output/native'
    report = json.loads((directory/'report.json').read_text())
    manifest = json.loads((directory/'approved-manifest.json').read_text())
    base.need(len(manifest['steps']) == 1 and manifest['steps'][0]['argv'] ==
              ['{exe}', '{root}/donor/reference/continuous.txt'], 'actual continuous corpus, not pilot argv')
    step = manifest['steps'][0]['name']
    run = next(item for item in report['steps'] if item['name'] == step)
    rows = [(line.split(' ', 1)[0], json.loads(line.split(' ', 1)[1])) for line in (directory/run['log']).read_text().splitlines()]
    checks = [row for name, row in rows if name == 'ANEXT_SOAK_CHECK']
    operations = [row for name, row in rows if name == 'ANEXT_SOAK_STEP']
    footer = rows[-1][1]
    base.need(rows[-1][0] == 'ANEXT_SOAK_PASS'
              and all(type(value) is int for key, value in footer.items() if key not in ('case_id', 'mode')),
              'strict integer footer, not boolean/count coercion')
    base.need(len(operations) == 1000 and [row['step'] for row in checks] == list(range(0, 1001, 100))
              and all(len(row['digits']) == 65536 for row in checks), '1000 operations and all eleven full arrays')
    base.need(footer['resets'] == 1 and footer['loaded_digits'] == 65536
              and footer['operations'] == 1000 and footer['doubles'] == 488
              and footer['cycles'] == 21914089 and footer['cold_prefill'] == 10
              and footer['warm_prefill'] == 990 and footer['cache_cold'] == 1
              and footer['cache_warm'] == 999, 'strict no-reload retained-state footer')
    native = report['validations'][step]
    donor = native['donor_reference_validation']
    base.need(native['candidate'] == 'A-next-point-v1' and donor['uninterrupted_1000_square_rtl'] is True
              and donor['native_qualification_allowed'] is True
              and native['donor_runtime_admission']['package_version'] == '2.3.1'
              and native['donor_runtime_admission']['runtime_manifest_sha256'] ==
              '84fb40c8e6452d4b660d9302e83584dd3c4761aa6219495e57f2df582401cf0b', 'actual point and pinned GCP numerical admission')
    bench = (ROOT/'rtl/tb/anext_point_soak_v1.cpp').read_text()
    begin = bench.index('for (unsigned k = 0; k < bits.size(); ++k)')
    loop = bench[begin:bench.index('require(next_check == count', begin)]
    base.need(bench.count('Core d{&context}') == 1 and bench.count('d.rst_n=0;') == 1
              and 'd.rst_n' not in loop and 'command(0' not in loop and 'command(1' not in loop,
              'one model and initial reset/load, no mid-loop reset/reload')
    result.update(total_readback_words=sum(len(row['digits']) for row in checks),
                  checkpoint_residue_sha256=donor['checkpoint_residue_sha256'],
                  reset_reload_source_and_footer_checked=True, runtime_admission=native['donor_runtime_admission'],
                  model_user_seconds=run['user_seconds'], model_system_seconds=run['system_seconds'],
                  cumulative_children_peak_rss_kib=run['cumulative_children_peak_rss_kib'],
                  isolated_model_peak_rss_measured=False,
                  metric_scope='One point GCP serial run; unit peak includes compile/reference. Cumulative children RSS is not an isolated model peak. No prior-image/cross-host/thread ratio.',
                  consumer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  independent_review_and_advisor_acceptance_still_required=True)
    return result


if __name__ == '__main__':
    print(json.dumps(consume(), indent=2))
