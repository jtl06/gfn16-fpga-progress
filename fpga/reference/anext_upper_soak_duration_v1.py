"""A-next-only duration evidence from a real100-operation pilot.

The denominator is measured backend cycles, NOT measured whole-bench ticks.
No full-size integer arithmetic, native execution, or resource-policy override.
"""
import hashlib,json,math,shutil
from pathlib import Path
from fpga.reference.anext_point_contract_v1 import schedule
from fpga.reference.anext_upper_soak_output_v1 import normalise
from fpga.reference.core27_t5b_soak_v1 import reference
ROOT=Path(__file__).resolve().parents[1]
ROLE=ROOT/'artifacts/anext-upper-qualification-continuous-role-v3'
ROLE_SHA='740d476ba7fbd590c7d3a64ea1a89b4a51dcf2fbc612a71e28cab3bab4202158'
PILOT_ROLE=ROOT/'artifacts/anext-upper-qualification-pilot-role-v3/source/fpga'
STEP='anext-soak-chunk00'
FULL_REFERENCE=ROOT/'queue/evidence/soak-t5b-aw16-full-reference-q3-v1/attempt-0/collected/output/command-report.json'
FULL_SHA='cbb16451e8ac0273105cb426b3d4ea996125132ff4ae700ad67894063383d2a4'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def predict(seconds,backend_cycles,reference_seconds):
    s=schedule(16);pilot=s['cold_loaded_backend']+99*s['warm_backend']
    continuous=s['cold_loaded_backend']+9*s['cold_cached_backend']+990*s['warm_backend']
    need(type(backend_cycles) is int and backend_cycles==pilot,'actual100 backend count')
    need(type(seconds) in (int,float) and math.isfinite(seconds) and seconds>0 and type(reference_seconds) in (int,float) and math.isfinite(reference_seconds) and reference_seconds>0,'positive finite measurements')
    need(continuous<=10*pilot,'backend work dominates under10x scaling')
    upper=seconds/pilot;margin=1.75
    return dict(measured_ticks={STEP:pilot},model_seconds_per_tick_upper_observed=upper,margin=margin,
        continuous_operations=1000,continuous_model_ticks=continuous,
        continuous_command_seconds_estimate=upper*continuous*margin,
        full_reference_replay_seconds_estimate=2*reference_seconds+10,
        tick_basis='Measured square backend cycles only; excluded host edges are NOT represented as measured total bench ticks.',
        conservative_host_work='10x pilot has10 initial loads and20 full reads; continuous1000 has1 initial load and11 full reads. Numerator includes pilot host time; nine continuous read-induced prefill-cold transitions are in the exact backend sum. Margin covers observed-rate variation, not a timing guarantee.')

def prepare(pilot_dir,gate_path,output):
    pilot_dir,gate_path,output=Path(pilot_dir).resolve(),Path(gate_path).resolve(),Path(output).resolve()
    need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'fresh output/no PAUSE')
    need(sha(ROLE/'manifest.json')==ROLE_SHA and sha(FULL_REFERENCE)==FULL_SHA,'frozen continuous role/reference measurement')
    m=json.loads((ROLE/'manifest.json').read_text());p=json.loads((pilot_dir/'approved-manifest.json').read_text());r=json.loads((pilot_dir/'report.json').read_text());g=json.loads(gate_path.read_text())
    for name in ('reference/anext_upper_soak_output_v1.py','reference/anext_point_contract_v1.py','reference/core27_t5b_soak_v1.py','reference/core27_crtmont_soak_v1.py'):
        need(sha(ROOT/name)==m['sources'][name]==p['sources'][name],'frozen local metadata/parser dependency')
    need(g['status']=='PASS_expected_contracts' and g['manifest_sha256']==sha(pilot_dir/'approved-manifest.json') and g['report_sha256']==sha(pilot_dir/'report.json'),'actual automatic pilot gate bindings')
    need(r['status']=='completed_native_commands_unreviewed' and r['host']=='gfn16-pilot-c4d','actual GCP pilot completion')
    need(m['build']==p['build'] and m['probe']==p['probe'],'unchanged source model/build/probe')
    step=p['steps'][0];need(len(p['steps'])==1 and step['name']==STEP and step['validator']['config']=={'negative':'none'},'normal100 pilot only')
    observed=next(x for x in r['steps'] if x['name']==STEP)
    need(type(observed['returncode']) is int and observed['returncode']==0 and observed['error'] is None,'real model rc0')
    oracle_path=PILOT_ROLE/step['validator']['assets']['oracle'];need(sha(oracle_path)==p['sources'][step['validator']['assets']['oracle']],'exact pilot oracle asset')
    oracle=json.loads(oracle_path.read_text());ref=reference()
    stdout=(pilot_dir/observed['log']).read_text();stderr=(pilot_dir/observed['stderr_log']).read_text()
    need(sha(pilot_dir/observed['log'])==observed['sha256'] and sha(pilot_dir/observed['stderr_log'])==observed['stderr_sha256'],'native model log binding')
    converted,metrics=normalise(stdout,oracle,ref)
    rows=ref.validate_rows(converted,stderr,0,{'negative':'none'},oracle) # metadata/array comparison only; no GMP call.
    need(rows['operations']==100 and metrics['cold_prefill']==1 and metrics['warm_prefill']==99,'actual warm-heavy100 pilot')
    native=r['validations'][STEP]
    need(native['status']=='PASS_expected_contracts' and native['native_anext_metrics']==metrics and native['donor_reference_validation']['independent_gmpy2_boundary_replay'] is True,'native admitted GMP replay retained')
    names=set(m['build']['sv_sources'])|{m['build']['cpp_source'],'rtl/tb/native_runtime_context_v1.h',step['validator']['source'],'donor/fpga/soak/runtime.json'}
    pins={name:m['sources'][name] for name in sorted(names)}
    need(all(p['sources'].get(name)==pin for name,pin in pins.items()),'same compiled/driver/validator/runtime pins')
    forecast=dict(schema='anext-upper-backend-cycle-duration-v1',status='PASS_A_next_upper_measured_backend_cycle_forecast',
        generator_sha256=sha(__file__),compatible_hosts=['gfn16-pilot-c4d'],
        short_manifest_sha256=sha(pilot_dir/'approved-manifest.json'),short_report_sha256=sha(pilot_dir/'report.json'),short_gate_sha256=sha(gate_path),
        source_model_build=m['build'],source_model_pins=pins,
        forecast=predict(observed['seconds'],sum(x['cycles'] for x in metrics['metrics']),json.loads(FULL_REFERENCE.read_text())['elapsed_seconds']),
        opaque_step_id_note='The continuous role retains the pilot step identifier only. Its argv and oracle explicitly select continuous1000; no chunk/reset/reload substitution.',
        local_full_n_integer_computation=False,promotion_allowed=False)
    source=output/'role/source/fpga';source.mkdir(parents=True)
    for name,pin in m['sources'].items():
        original=ROLE/'source/fpga'/name;need(sha(original)==pin,'continuous closed source')
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
    need(len(m['steps'])==1 and m['steps'][0]['name']=='anext-soak-none' and m['steps'][0]['argv'][-1]=='{root}/donor/reference/continuous.txt','exact continuous command')
    m['steps'][0]['name']=STEP # opaque shared binding; actual corpus remains continuous1000.
    (output/'role/manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    (output/'forecast.json').write_text(json.dumps(forecast,indent=2)+'\n')
    return forecast

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--pilot-dir',type=Path,required=True);p.add_argument('--gate',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.pilot_dir,a.gate,a.output),indent=2))
