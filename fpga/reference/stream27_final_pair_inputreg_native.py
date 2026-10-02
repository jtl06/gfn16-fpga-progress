"""r75 canonical final-pair input register: normal-first bounded leaf gate."""
import argparse
from collections import deque
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_final_pair_inputreg_native.py'
TOP='genefer_stream27_final_pair_inputreg_compare_v1'
RTL='rtl/kernel/genefer_stream27_merged_final_gs_pair_inputreg_v1.sv'
PAIR='rtl/tb/'+TOP+'.sv'
CPP='rtl/tb/stream27_final_pair_inputreg_normal.cpp'
READY='results/throughput-20260929/stream27-final-pair-inputreg-source-v1/rtl-ready-v2.json'
PARENT='rtl/kernel/genefer_stream27_merged_final_gs_pair_v1.sv'
ENGINE='rtl/kernel/genefer_ntt_banked27_engine.sv'
MUL='rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv'
BF='rtl/tb/stream27_final_pair_frozen_butterfly.sv'
SIZING_TOP='genefer_stream27_final_pair_inputreg_sizing_v1'
SIZING_SV='rtl/tb/'+SIZING_TOP+'.sv'
SIZING_CPP='rtl/tb/stream27_final_pair_inputreg_sizing_normal.cpp'
FIELDS=(104857601,69206017,67239937)
PINS={PARENT:'c860243f74d445324e93d8d2bc202521249316f04364c4bb2e630d4328216d4b',
      ENGINE:'7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9',
      MUL:'501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b'}

def need(ok,why):
    if not ok:raise ValueError(why)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def scale(p):
    # Same normalized final-GS upper domain R^2/N. N=256 is a scalar
    # normalization parameter, not a transform run in this component gate.
    need(p in FIELDS,'FINAL_PAIR_FIELD')
    return pow(1<<32,2,p)*pow(256,-1,p)%p

def butterfly():
    text=(ROOT/ENGINE).read_text();marker='module genefer_ntt_difdit_butterfly27 #('
    need(text.count(marker)==1,'FINAL_PAIR_ONE_FROZEN_BUTTERFLY')
    return text[text.index(marker):]

def verify():
    for name,pin in PINS.items():need(sha((ROOT/name).read_bytes())==pin,'FINAL_PAIR_FROZEN_PIN '+name)
    ready=json.loads((ROOT/READY).read_text())
    need(ready['candidate_id']=='stream27-final-pair-inputreg-v1','FINAL_PAIR_READY_ID')
    for name,pin in ready['source_snapshot'].items():
        need(sha((ROOT/name).read_bytes())==pin,'FINAL_PAIR_FROZEN_NEW_SOURCE '+name)
    return ready

def seal():
    need(not (ROOT/READY).exists(),'FINAL_PAIR_FRESH_READY')
    for name,pin in PINS.items():need(sha((ROOT/name).read_bytes())==pin,'FINAL_PAIR_FROZEN_PIN '+name)
    # The dispatcher readiness schema deliberately accepts design SV only,
    # not C++ fixtures. Preserve the first metadata attempt unchanged.
    sources={name:sha((ROOT/name).read_bytes()) for name in (RTL,PAIR)}
    first=ROOT/'results/throughput-20260929/stream27-final-pair-inputreg-source-v1/rtl-ready.json'
    original=json.loads(first.read_text()) if first.exists() else None
    if original:
        for name,pin in original['source_snapshot'].items():
            need(sha((ROOT/name).read_bytes())==pin,'FINAL_PAIR_UNCHANGED_FIRST_READY')
    value=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='stream27-final-pair-inputreg-v1',
        candidate_source_sha256=sha(json.dumps(sources,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=original['rtl_ready_at_utc'] if original else datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        source_snapshot=sources)
    if original:value['metadata_repair_of']=str(first.relative_to(ROOT))
    path=ROOT/READY;path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    return value

def counts(latencies=(5,6)):
    need(latencies in ((5,6),(6,7)),'FINAL_PAIR_LEDGER_LATENCIES')
    queues=[deque(),deque()];checked=[0,0];cancelled=[0,0]
    for edge in range(6400):
        reset=not(edge<2 or edge%257 in (100,101));valid=edge<6200 and edge%11!=0
        for k in range(2):
            if not reset:cancelled[k]+=len(queues[k]);queues[k].clear()
            if reset and valid:queues[k].append(edge+latencies[k])
            if queues[k] and queues[k][0]==edge:queues[k].popleft();checked[k]+=1
    need(not any(queues),'FINAL_PAIR_TAIL_LEDGER')
    return dict(edges=6400,old_checked=checked[0],new_checked=checked[1],
        old_cancelled=cancelled[0],new_cancelled=cancelled[1],
        old_holds=6400-checked[0],new_holds=6400-checked[1],old_latency=latencies[0],new_latency=latencies[1])

def expected(p):
    return f'FINAL_PAIR_INPUTREG_PASS p={p} scale={scale(p)} '+' '.join(f'{k}={v}' for k,v in counts().items())+'\n'

def contract():
    return dict(input='u/v/root canonical unsigned32<P; static UPPER_SCALE=R^2/N<P',
        output='both canonical<P; bit-exact unchanged arithmetic',R=1<<32,
        parent_latency=5,candidate_latency=6,II=1,added_input_register_bits=97,
        added_variable_products=0,normalization_pipes=2,
        reset='asynchronous valid+parent flush; payload token-qualified; no stale output',
        cancel='outer field must retain raw immediate commit/accept kills and assert rst_n reset contract',
        metadata='all final-pair lanes plus slot/frame_start/generation/sink gain exactly one edge',
        warm_cycle_delta='one inverse sink edge per operation, integration not yet qualified',
        scope='canonical final inverse pair only; no lazy/GS-wide/root/domain/arithmetic change',
        physical_gain=False,clock_claim=False)

def preflight(manifest,files):
    # Exact label grammar/reserved names used by the frozen
    # native_source_gate_v1.load_manifest; no host/tool impersonation.
    names=[step['name'] for step in manifest['steps']]
    need(names and len(names)==len(set(names)) and all(re.fullmatch('[a-z][a-z0-9-]*',name)
         and name not in ('build','probe','verilator-version','compiler-version') for name in names),
         'FINAL_PAIR_LOCAL_NATIVE_STEP_GRAMMAR')
    build=manifest['build']
    need(len(build['sv_sources'])==len(set(build['sv_sources'])),'FINAL_PAIR_UNIQUE_COMPILED_SOURCES')
    for name in build['sv_sources']+[build['cpp_source']]:
        need(name in files and sha(files[name])==manifest['sources'][name],'FINAL_PAIR_CLOSED_COMPILED_SOURCE')
    for name,pin in manifest['rtl_readiness']['source_snapshot'].items():
        need(name.endswith('.sv') and manifest['sources'][name]==pin,'FINAL_PAIR_NATIVE_SV_READINESS')
    return manifest,files

def role(p):
    ready=verify();need(p in FIELDS,'FINAL_PAIR_FIELD')
    names=(RTL,PAIR,CPP,SELF,*PINS,READY)
    files={name:(ROOT/name).read_bytes() for name in names};files[BF]=butterfly().encode()
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/final-pair/fpga',output_parent='/not-a-dispatch-path/final-pair/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=TOP,sv_sources=[PAIR,RTL,PARENT,MUL,BF],cpp_source=CPP,
            parameters=dict(P=p,Q=(2-p)%(1<<32),UPPER_SCALE=scale(p)),
            cflags=['-std=c++17','-O2','-Werror=return-type',f'-DTEST_P={p}',f'-DTEST_SCALE={scale(p)}']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='normal-old-e5-new-e6-canonical-normalization-reset-bubbles-hold',argv=['{exe}'],
            expected_returncode=0,expected_stdout=expected(p),expected_stderr='')],
        test_role='normal',rtl_readiness=ready,interface_contract=contract(),arithmetic_source_pins=PINS,
        scope='Paired canonical final GS leaf: independent64bit modular oracle, exact both-branch normalization/latency/II/reset/bubbles/hold. No field/fit/clock promotion.')
    return preflight(manifest,files)

def prepare(output,p,budget):
    from fpga.reference import stream27_l3_factored_native_v1 as package
    return package.prepare(output,p,budget,role_builder=role,identity='normal3',family='stream27-final-pair-inputreg')

def sizing_cpp():
    text=(ROOT/CPP).read_text().replace(TOP,SIZING_TOP)
    sites=[('d.in_valid=valid;d.u=u;d.v=v;d.normalized_lower_root=w;',
        'd.in_valid=valid?3:0;d.u=u|(u<<28);d.v=v|(v<<28);d.normalized_lower_root=w|(w<<32);'),
        ('d.clk=0;d.rst_n=reset;', 'if(edge%3==0)u+=P;if(edge%5==0)v+=P;\n        d.clk=0;d.rst_n=reset;'),
        ('(((u+v)%P)*SCALE%P)*ri%P,b=(((u+P-v)%P)*w%P)*ri%P;',
         '(((u%P+v%P)%P)*SCALE%P)*ri%P,b=(((u%P+P-v%P)%P)*w%P)*ri%P;'),
        ('edge+5+k','edge+6+k'),('FINAL_PAIR_INPUTREG_PASS','FINAL_PAIR_INPUTREG_SIZING_PASS'),
        ('old_latency=5 new_latency=6','old_latency=6 new_latency=7')]
    for before,after in sites:
        need(text.count(before)==1,'FINAL_PAIR_SIZING_BENCH_UNIQUE_SITE '+before)
        text=text.replace(before,after,1)
    return text

def write_sizing_bench():
    path=ROOT/SIZING_CPP;text=sizing_cpp()
    if path.exists():need(path.read_text()==text,'FINAL_PAIR_FROZEN_SIZING_BENCH');return
    with path.open('x') as f:f.write(text)

def sizing_role(p):
    manifest,files=role(p)
    need((ROOT/SIZING_CPP).read_text()==sizing_cpp(),'FINAL_PAIR_EXACT_SIZING_BENCH')
    files.update({name:(ROOT/name).read_bytes() for name in (SIZING_SV,SIZING_CPP)})
    manifest['sources']={name:sha(raw) for name,raw in files.items()}
    manifest['build'].update(top=SIZING_TOP,sv_sources=[SIZING_SV,RTL,PARENT,MUL,BF],cpp_source=SIZING_CPP)
    stdout=f'FINAL_PAIR_INPUTREG_SIZING_PASS p={p} scale={scale(p)} '+' '.join(f'{k}={v}' for k,v in counts((6,7)).items())+'\n'
    manifest['steps']=[dict(name='normal-matched-source-ff-lazy-canonical-boundary-old-e6-new-e7',argv=['{exe}'],
        expected_returncode=0,expected_stdout=stdout,expected_stderr='')]
    manifest['scope']='Two independent registered source sets; actual current lazy28 one-subtract canonical boundary plus unchanged/final-inputreg pairs. E6/E7 incl source FF; no field clock.'
    return preflight(manifest,files)

def prepare_sizing(output,p,budget):
    from fpga.reference import stream27_l3_factored_native_v1 as package
    return package.prepare(output,p,budget,role_builder=sizing_role,identity='sizing-normal',family='stream27-final-pair-inputreg')

def native_gates():
    qid='stream27-final-pair-inputreg-f0-sizing-normal-q1-v1'
    path=ROOT/'queue/evidence'/qid/'gate-receipt.json';raw=path.read_bytes();g=json.loads(raw)
    need(g['id']==qid and g['status']=='PASS_expected_contracts','FINAL_PAIR_ACTUAL_MATCHED_WRAPPER_NATIVE')
    return [dict(path=str(path),sha256=sha(raw),fields=dict(id=qid,status='PASS_expected_contracts'))]

def prepare_project(destination):
    from fpga.cloud import plain_fit_v5 as fit
    from fpga.tools import fit_dispatch
    native_gates();manifest,files=sizing_role(FIELDS[0])
    destination=Path(destination).resolve();need(destination.is_relative_to(ROOT) and not destination.exists(),'FINAL_PAIR_FRESH_PROJECT')
    rtl=destination/'rtl';rtl.mkdir(parents=True)
    sources={Path(name).name:files[name] for name in manifest['build']['sv_sources']}
    for name,raw in sources.items():
        with (rtl/name).open('xb') as f:f.write(raw)
    donor=ROOT/'results/throughput-20260929/stream27-l3-static-directions-f0-source-v1/project'
    qsf=(donor/'probe.qsf').read_text();qsf=qsf[:qsf.index('set_global_assignment -name TOP_LEVEL_ENTITY ')]
    qsf+=f'set_global_assignment -name TOP_LEVEL_ENTITY {SIZING_TOP}\n'
    qsf+=''.join(f'set_global_assignment -name SYSTEMVERILOG_FILE rtl/{name}\n' for name in sources)
    qsf+=''.join(f'set_parameter -name {name} {value}\n' for name,value in manifest['build']['parameters'].items())
    for port in ('rst_n','in_valid[*]','u[*]','v[*]','normalized_lower_root[*]','old_valid','new_valid',
                 'old_error','new_error','old_y0[*]','old_y1[*]','new_y0[*]','new_y1[*]'):
        qsf+=f'set_instance_assignment -name VIRTUAL_PIN ON -to {{{port}}}\n'
    controls={name:(donor/name).read_text() for name in ('probe.qpf','probe.sdc','run.tcl')};controls['probe.qsf']=qsf
    need(controls['run.tcl']==fit.FULL_TCL,'FINAL_PAIR_PLAIN_FLOW')
    for name,text in controls.items():
        with (destination/name).open('x') as f:f.write(text)
    value=dict(schema='stream27-final-pair-inputreg-sizing-v1',status='prepared_not_fitted',top=SIZING_TOP,
        target='stream27_final_pair_inputreg_f0',edition='pro',device='10AX115N4F40E3SG',compile_processors=4,
        bitstream_generation=False,allowed_stages=['syn','fit','sta'],clock_period_ns=10,seed=1,intermediate_snapshots=True,
        core_parameters=manifest['build']['parameters'],source_sha256={name:sha(raw) for name,raw in sources.items()},
        control_sha256={name:sha(text.encode()) for name,text in controls.items()},native_prerequisites=native_gates(),
        arithmetic_source_pins=PINS,cell_comparison=['original','registered_pair'],independent_input_sets=2,
        expected_variable_products_by_source=4,source_input_domain='lazy28<2P, boundary canonical<P',
        source_register_latency=1,parent_latency=5,candidate_latency=6,wrapper_latencies=[6,7],II=1,
        source_inputs={name:sha((ROOT/name).read_bytes()) for name in (SELF,ENGINE)},
        scope='Matched registered-source canonical-boundary scalar final pair sizing, not spatial field/whole clock. Added one full input bundle, no extra product or normalization change.',
        promotion_allowed=False)
    with (destination/'manifest.json').open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    return fit_dispatch.snapshot(destination)

def submit_project(project):
    from fpga.tools import fit_submit
    return fit_submit.submit(ROOT/'queue/standing-fits','stream27-final-pair-inputreg-f0-v1',Path(project).resolve(),
        '10',1,dict(azure4=list('abcd'),aws6=list('ab')),'component_probe',dict(exemption='component_sizing_probe'),
        priority=20,requires=native_gates(),track='S',purpose='clock_push')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seal',action='store_true');parser.add_argument('--write-sizing-bench',action='store_true')
    parser.add_argument('--p',type=int,choices=FIELDS);parser.add_argument('--output',type=Path);parser.add_argument('--budget',type=Path)
    parser.add_argument('--sizing-normal',action='store_true');parser.add_argument('--project',type=Path);parser.add_argument('--submit',action='store_true')
    args=parser.parse_args()
    if args.seal:value=seal()
    elif args.write_sizing_bench:write_sizing_bench();value='sizing-normal-source-ready'
    elif args.project:value=submit_project(args.project) if args.submit else prepare_project(args.project)
    else:value=(prepare_sizing if args.sizing_normal else prepare)(args.output,args.p,args.budget)
    print(json.dumps(value,indent=2))
