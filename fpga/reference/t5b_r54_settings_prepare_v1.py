"""Finite r54 T5b settings-only alternatives; source preparation, never dispatch.

Exactly one candidate is selected later from actual seed2/3@9.5ns results.
No architecture, arithmetic, timing exception or promoted-clock change.
"""
import copy,hashlib,json,shutil
from pathlib import Path
from fpga.tools.prefit_t5b_seed95_v1 import PARENT,EVIDENCE
from fpga.cloud.plain_fit_v1 import FULL_TCL
ROOT=Path(__file__).resolve().parents[1]
if hashlib.sha256((ROOT/'tools/prefit_t5b_seed95_v1.py').read_bytes()).hexdigest()!='4b893b23b5beddac9d7c9632144793e850f2bc681fb3df34faa36f2bc9d301d1':
    raise ValueError('frozen promoted-parent evidence constants')
BASE=ROOT/'results/throughput-20260929/core27-t5b-provisional-fit-stage-v1/project'
FULL_SHA='92711aace1e4f6f7cd577eb764403382a3a95aa495b02c379c0e27912c15c1b4'
ALLOWED={(4,9.6):'only_if_neither_seed2_nor_seed3_closes_9.5ns',
         (2,9.3):'only_if_seed2_is_selected_from_actual_9.5ns_closure',
         (3,9.3):'only_if_seed3_is_selected_from_actual_9.5ns_closure'}
def need(ok,why):
    if not ok:raise ValueError(why)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def controls(parent_dir,seed,period):
    need(type(seed) is int and (seed,period) in ALLOWED,'finite r54 alternatives')
    qsf=(parent_dir/'probe.qsf').read_text();sdc=(parent_dir/'probe.sdc').read_text()
    need(qsf.count('NUM_PARALLEL_PROCESSORS 6')==1 and qsf.count('SEED 1\n')==1
         and 'ENABLE_INTERMEDIATE_SNAPSHOTS' not in qsf,'exact parent settings anchors')
    need(sdc.count('-period 10 ')==1,'one selected parent clock')
    qsf=qsf.replace('NUM_PARALLEL_PROCESSORS 6','NUM_PARALLEL_PROCESSORS 4').replace('SEED 1\n',f'SEED {seed}\n')
    qsf+='set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON\n'
    sdc=sdc.replace('Exploratory 10 ns clock',f'Exploratory {period:g} ns clock').replace('-period 10 ',f'-period {period:g} ')
    need(hashlib.sha256(FULL_TCL.encode()).hexdigest()==FULL_SHA,'frozen plain flow')
    return {'probe.qsf':qsf,'probe.sdc':sdc,'probe.qpf':(parent_dir/'probe.qpf').read_text(),'run.tcl':FULL_TCL}

def assess(project):
    p=Path(project).resolve();m=json.loads((p/'manifest.json').read_text());e=p/'evidence'
    for name,pin in EVIDENCE.items():need(sha(e/name)==pin,'exact promoted evidence '+name)
    parent=json.loads((e/'parent-manifest.json').read_text())
    for name,pin in parent['control_sha256'].items():need(sha(e/('parent-'+name))==pin,'frozen parent control')
    need(m['source_sha256']==parent['source_sha256'] and len(m['source_sha256'])==16,'unchanged16RTL')
    need({x.name for x in (p/'rtl').iterdir()}==set(m['source_sha256']),'closed RTL set')
    for name,pin in m['source_sha256'].items():need(sha(p/'rtl'/name)==pin,'RTL byte drift')
    seed,period=m['seed'],m['clock_period_ns'];need(type(seed) is int and (seed,period) in ALLOWED,'only requested settings')
    # Reconstruct from the byte-pinned parent controls; no Tcl normalization.
    qsf=(e/'parent-probe.qsf').read_text().replace('NUM_PARALLEL_PROCESSORS 6','NUM_PARALLEL_PROCESSORS 4').replace('SEED 1\n',f'SEED {seed}\n')+'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON\n'
    sdc=(e/'parent-probe.sdc').read_text().replace('Exploratory 10 ns clock',f'Exploratory {period:g} ns clock').replace('-period 10 ',f'-period {period:g} ')
    expected={'probe.qsf':qsf,'probe.sdc':sdc,'probe.qpf':(e/'parent-probe.qpf').read_text(),'run.tcl':FULL_TCL}
    need(hashlib.sha256(FULL_TCL.encode()).hexdigest()==FULL_SHA,'frozen plain Tcl')
    for name,text in expected.items():need((p/name).read_text()==text,'unapproved control delta '+name)
    for key in ('top','device','address_width','core_parameters','arithmetic_profile','core_field_basis','core_montgomery_radix_bits','root_profile_format','bitstream_generation'):
        need(m[key]==parent[key],'functional setting drift '+key)
    need(m['compile_processors']==4 and m['parent_physical_manifest_sha256']==PARENT,'parent/workers')
    need(m['control_sha256']=={name:sha(p/name) for name in expected},'source/control manifest')
    need(m['promotion_allowed'] is False and m['usable_clock_mhz'] is None and m['throughput'] is None,'no unmeasured promotion')
    need(m['selection_condition']==ALLOWED[(seed,period)],'conditional selection evidence required')
    return dict(status='PASS_exact_T5b_r54_settings_only_source',manifest_sha256=sha(p/'manifest.json'),
        checker_sha256=sha(__file__),parent_manifest_sha256=PARENT,seed=seed,clock_period_ns=period,workers=4,
        source_sha256=m['source_sha256'],control_sha256=m['control_sha256'],
        design_prescreen_exemption='constraint_seed_only',conditional_selection=ALLOWED[(seed,period)],
        snapshots_enabled=True,plain_syn_fit_sta=True,native_crossing_coverage_complete=False,
        native_DA_pass=False,launch_authority_conferred=False,promotion_allowed=False,
        limitation='Exact inherited topology only. Fit owner selects one from actual predecessor results; normal source/tool/host/budget/locks still required. Diagnostics post-fit under r53.')

def prepare(output,seed,period):
    output=Path(output).resolve();need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'fresh output/no PAUSE')
    need(sha(BASE/'manifest.json')==PARENT,'frozen production parent')
    parent=json.loads((BASE/'manifest.json').read_text())
    for name,pin in parent['source_sha256'].items():need(sha(BASE/'rtl'/name)==pin,'parent RTL')
    for name,pin in parent['control_sha256'].items():need(sha(BASE/name)==pin,'parent controls')
    control=controls(BASE,seed,period)
    evidence={'parent-manifest.json':BASE/'manifest.json',
        'parent-100-review.json':ROOT/'results/throughput-20260929/core27-t5b-100-audit-m8azn-v1/independent-review-v1.json',
        'parent-9668-review.json':ROOT/'results/throughput-20260929/core27-t5b-selected9668-audit-m8azn-v3/independent-review-v1.json',
        'advisor-verification-T5b.md':ROOT/'docs/briefs/2026-10-01-advisor-verification-T5b.md'}
    for name,path in evidence.items():need(sha(path)==EVIDENCE[name],'promoted evidence')
    (output/'rtl').mkdir(parents=True);(output/'evidence').mkdir()
    for name in parent['source_sha256']:shutil.copyfile(BASE/'rtl'/name,output/'rtl'/name)
    for name,path in evidence.items():shutil.copyfile(path,output/'evidence'/name)
    for name in parent['control_sha256']:shutil.copyfile(BASE/name,output/'evidence'/('parent-'+name))
    for name,text in control.items():(output/name).write_text(text)
    m=copy.deepcopy(parent)
    for key in ('adapter_sha256','resource_policy_sha256','frozen_policy_sha256','resource_profile','execution_changes','evidence_sha256','qualification'):m.pop(key,None)
    m.update(seed=seed,clock_period_ns=period,compile_processors=4,target=f'T5b_r54_seed{seed}_{period:g}ns_F16_plain',
        status='prepared_not_executed',parent_physical_manifest_sha256=PARENT,selection_condition=ALLOWED[(seed,period)],
        isolated_RTL_change='none',runtime_single_variable_comparison=False,
        note='Conditional source-only r54 alternative, not three launches. Four workers and target/seed differ from inherited fit; no higher clock or promotion inherited.',
        control_sha256={name:sha(output/name) for name in control})
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    result=assess(output);(output.parent/'source-preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--period',type=float,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.seed,a.period),indent=2))
