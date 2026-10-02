"""Generate isolated AW16 NORMAL-only successor from reviewed AW5 adapter.

No native/cloud action. Frozen AW5 runner and all candidate RTL stay unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ANCESTOR='reference/core27_prefill_aw5_v2_regression.py'
ANCESTOR_SHA='b0b88a4c9c6e117d0552db49a1b63d5c85d862b3f776e5e83d561e89fcbc0828'
CANDIDATE='reference/core27_prefill_aw16_regression.py'
PARENT_REPORT='results/throughput-20260929/core27-prefetch-r2-rootfused-crtmont-aw16-v1/report.json'
PARENT_SHA='d32023abd40f925fade2f4844e7eb57a4cc9fee2c19203ec51569165e8ea3808'


def need(ok,why):
    if not ok:raise ValueError(why)


def once(text,before,after):
    need(text.count(before)==1,'unique AW16 adapter anchor: '+before[:60])
    return text.replace(before,after,1)


def generate(root=ROOT):
    root=Path(root);data=(root/ANCESTOR).read_bytes()
    need(hashlib.sha256(data).hexdigest()==ANCESTOR_SHA,'frozen AW5 runner drift')
    need(hashlib.sha256((root/PARENT_REPORT).read_bytes()).hexdigest()==PARENT_SHA,'qualified AW16 parent drift')
    source=data.decode()
    source=once(source,'one bounded AW5-first T5 gate group','the bounded AW16 NORMAL-only T5 gate')
    source=once(source,'No automatic dispatch, AW16, mutation execution, cloud or physical action.',
        'No automatic dispatch, targeted/mutation execution, cloud or physical action.')
    source=source.replace('/core27-prefill-aw5-v2/snapshot-v2/fpga','/core27-prefill-aw16/snapshot-v1/fpga')
    source=once(source,"NORMAL_REPORT = 'results/throughput-20260929/core27-prefetch-r2-rootfused-crtmont-aw5-v1/report.json'","NORMAL_REPORT = '"+PARENT_REPORT+"'")
    source=once(source,"NORMAL_REPORT_SHA = '1bc9950b438397ed2e1bcb230996b6f02d7a30d9d42d65f9d664857ed610bceb'","NORMAL_REPORT_SHA = '"+PARENT_SHA+"'")
    source=once(source,"RUNNER = 'reference/core27_prefill_aw5_v2_regression.py'","RUNNER = '"+CANDIDATE+"'")
    source=once(source,"TARGET_VECTOR_SHA = '1080d4454da030795060b347cf1dd7f06cebae4c2451272cd6fecc01378d3603'\n",'')
    source=once(source,'V1_ADAPTER_PINS = {','V1_ADAPTER_PINS = {\n    '+repr(ANCESTOR)+': '+repr(ANCESTOR_SHA)+',\n'+
        "    'results/throughput-20260929/core27-prefill-aw5-normal-v2/report.json': 'a94f431c20319cba713df4d9e845fbd36bea237d82d355a353aff7f523ec5f5d',\n"+
        "    'results/throughput-20260929/core27-prefill-aw5-normal-v2/independent-review-v1.json': '82a7077f14bf57d79b66cd93b37dfe266100f208c0f9e7849903a93fff0f5121',")
    a=source.index('EXTRA = (');b=source.index('GIB = ',a)
    source=source[:a]+'''EXTRA = (
    'rtl/tb/core27_prefill_probe_v3.sv',
    'rtl/tb/core27_prefill_normal_v3.cpp',
    'rtl/tb/core27_prefill_normal_v3_threaded.cpp',
    'reference/core27_prefill_aw16_structure.py',
    'tests/test_core27_prefill_aw16_structure.py',
    RUNNER,
)
GROUPS = ('normal',)
'''+source[b:]
    source=once(source,"for name in ('core27_prefill_probe_v3.sv', 'core27_prefill_tail_probe_v3.sv'):","for name in ('core27_prefill_probe_v3.sv',):")
    source=once(source,"    if group == 'normal': paths += ['rtl/tb/core27_prefill_probe_v3.sv']\n    else: paths += ['rtl/tb/core27_prefill_fault_bridge.sv', 'rtl/tb/core27_prefill_tail_probe_v3.sv']",
        "    require(group == 'normal', 'AW16 normal-only compiled closure')\n    paths += ['rtl/tb/core27_prefill_probe_v3.sv']")
    a=source.index('def top(group):');b=source.index('def load_project(',a)
    source=source[:a]+'''def top(group):
    require(group == 'normal', 'AW16 normal-only top')
    return 'core27_prefill_probe_v3'


def commands(exe, vector, group):
    require(group == 'normal', 'AW16 normal-only invocation')
    return [('normal', [str(exe), str(vector), 'profile'])]


'''+source[b:]
    source=once(source,"    vectors = importlib.import_module('reference.core27_prefill_target_vectors')\n",'')
    source=once(source,'    return baseline, vectors','    return baseline')
    source=once(source,'    baseline, vectors = load_project(root, pins)','    baseline = load_project(root, pins)')
    source=once(source,"groups=list(GROUPS), aw=5,", "groups=list(GROUPS), aw=16,")
    source=once(source,"qualification='Normal and targeted controls only; eight mutant native gates remain separate. AW16 not authorized by this runner.'", "qualification='AW16 normal only; no targeted/mutant or physical promotion admitted.'")
    source=once(source,"manifest['aw'] == 5", "manifest['aw'] == 16")
    source=once(source,"'fixed AW5 gate profile'", "'fixed AW16 NORMAL-only gate profile'")
    source=once(source,'aw=5, n=32','aw=16, n=65536')
    source=once(source,"len(parent['metrics']) == 568", "len(parent['metrics']) == 12")
    source=once(source,"'all normal operations'", "'all12 AW16 normal operations'")
    source=once(source,"        expected = dict(old, conversion=0 if row['prefill_before'] else old['conversion'], carry=old['carry']+5)",
        "        require(old['conversion'] == 4102 and (not row['prefill_before'] or old['profile_before'] == 1), 'AW16 conversion/profile eligibility')\n        expected = dict(old, conversion=0 if row['prefill_before'] else 4102, carry=old['carry']+5)")
    source=once(source,"PASS n=32 squares=568 readbacks=561 aborts=20", "PASS n=65536 squares=12 readbacks=10 aborts=0")
    source=once(source,"require('PASS n=65536 squares=12 readbacks=10 aborts=0' in output, 'exact normal footer')",
        "require(output.splitlines().count('PASS n=65536 squares=12 readbacks=10 aborts=0') == 1, 'unique exact AW16 footer')")
    a=source.index('def check_target_output(');b=source.index('def execute(',a)
    source=source[:a]+source[b:]
    source=source.replace("prefix='gfn16-t5-aw5-'", "prefix='gfn16-t5-aw16-'")
    source=once(source,'group=group, aw=5,','group=group, aw=16,')
    source=once(source,'command_timeout_seconds=1800, total_budget_seconds=3600','command_timeout_seconds=3600, total_budget_seconds=5400')
    source=once(source,"limitation='Single AW5 group only; not full T5 qualification, AW16, fit, clock or board result.'", "limitation='AW16 normal gate only; not targeted reset/mutation, full T5, fit, clock or board qualification.'")
    source=once(source,"time.monotonic()-started < 3600", "time.monotonic()-started < 5400")
    source=once(source,"time.monotonic()-before < 1800", "time.monotonic()-before < 3600")
    a=source.index("        if group == 'normal':\n            report['vectors']");b=source.index('        remember(vector)',a)
    source=source[:a]+'''        require(group == 'normal', 'AW16 normal-only vectors')
        report['vectors'] = baseline.write_vectors(vector, 16, 20260929, True)
        require(report['vectors'] == parent['vectors'], 'exact frozen AW16 vectors')
'''+source[b:]
    source=once(source,"bench = 'rtl/tb/core27_prefill_normal_v3_threaded.cpp' if group == 'normal' else 'rtl/tb/core27_prefill_tail_v2.cpp'", "bench = 'rtl/tb/core27_prefill_normal_v3_threaded.cpp'")
    source=once(source,"'-GAW=5'", "'-GAW=16'")
    a=source.index("            if group == 'normal': report['metrics']");b=source.index("            require(sha(exe)",a)
    source=source[:a]+"            report['metrics'] = check_normal(output, parent)\n"+source[b:]
    source=once(source,"report['status'] = 'passed_aw5_group_only'", "report['status'] = 'passed_aw16_normal_only'")
    need("else 'rtl/tb/core27_prefill_tail" not in source and 'def check_target_output' not in source and "'-GAW=5'" not in source,'targeted execution removed')
    return source


def validate(root=ROOT):
    root=Path(root);need((root/CANDIDATE).read_text()==generate(root),'AW16 adapter body drift')
    return dict(status='source_only_AW16_normal_not_dispatched',ancestor_sha256=ANCESTOR_SHA,
        candidate_sha256=hashlib.sha256((root/CANDIDATE).read_bytes()).hexdigest(),
        parent_report_sha256=PARENT_SHA,aw=16,normal_operations=12,readbacks=10,
        unchanged_RTL=True,normal_group_only=True,command_timeout_seconds=3600,total_budget_seconds=5400)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--emit-patch',action='store_true')
    args=parser.parse_args()
    if args.emit_patch:
        need(not (ROOT/CANDIDATE).exists(),'fresh AW16 adapter required')
        print('*** Begin Patch\n*** Add File: '+str(ROOT/CANDIDATE))
        for line in generate().splitlines():print('+'+line)
        print('*** End Patch')
    else:print(json.dumps(validate(),indent=2))
