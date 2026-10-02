"""L7 numeric-payload-only reset cut; no arithmetic, validity or calendar cut.

INVALID result may retain arbitrary prior contents after reset. Only valid
outputs are numerically defined. Bubble holds remain exact, validity resets
immediately, and the first accepted post-reset product is published at E3.
No LAB/area benefit is inferred from source reset-bit counts.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import random
import re

from fpga.reference import stream27_l3_factored_model_v1 as math

ROOT=math.ROOT
SELF='reference/stream27_l7_resetfree_mont.py'
PARENT=math.RTL
PARENT_PIN='866c2b19c9e6afbbb56ce71089288334579f90e977ca139b41097d0f9191c690'
RTL='rtl/kernel/genefer_stream27_montgomery_factored_resetfree_v1.sv'
PAIR='rtl/tb/genefer_stream27_l7_resetfree_pair_v1.sv'
CPP='rtl/tb/stream27_l7_resetfree_pair_v1.cpp'
TOP=Path(PAIR).stem
RTL_READY='2026-10-01T23:46:41Z'
MUTANT_PAIR='rtl/tb/genefer_stream27_l7_resetfree_mutants_v1.sv'
MUTANT_CPP='rtl/tb/stream27_l7_resetfree_mutants_v1.cpp'
MUTANT_READY='2026-10-02T00:15:34Z'
NAMES={
 'genefer_stream27_montgomery_factored_core_v1':'genefer_stream27_montgomery_factored_resetfree_core_v1',
 'genefer_stream27_montgomery_factored_v1':'genefer_stream27_montgomery_factored_resetfree_v1',
 'genefer_stream27_montgomery28x27_factored_v1':'genefer_stream27_montgomery28x27_factored_resetfree_v1'}
OLD='''        if(!rst_n)begin
            valid_pipe<=0;out_valid<=0;result<=0;
            ab_s1<=0;m_s2<=0;hi_s2<=0;hi_s3<=0;carry_s2<=0;mp_hi_s3<=0;
        end else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];'''
NEW='''        if(!rst_n)begin valid_pipe<=0;out_valid<=0;end
        else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
        end
    end
    // Numeric payload deliberately retains arbitrary contents on reset.
    // Existing validity masks are the only publication/capture authority.
    always_ff @(posedge clk)begin
        if(rst_n)begin'''
need,sha=math.need,math.sha

def identifiers(text,mapping):
    for old,new in mapping.items():text=re.sub(r'\b'+re.escape(old)+r'\b',new,text)
    return text

def derived():
    parent=(ROOT/PARENT).read_bytes();need(sha(parent)==PARENT_PIN,'L7_FROZEN_FACTORED_PARENT')
    text=parent.decode();need(text.count(OLD)==1,'L7_EXACT_RESET_SITE')
    candidate=identifiers(text.replace(OLD,NEW,1),NAMES)
    need(identifiers(candidate,{v:k for k,v in NAMES.items()}).replace(NEW,OLD,1)==text,'L7_LITERAL_REVERSE')
    return candidate

def verify():
    need((ROOT/RTL).read_text()==derived(),'L7_EXACT_NUMERIC_RESET_DELTA')
    return dict(parent_sha256=PARENT_PIN,candidate_sha256=sha((ROOT/RTL).read_bytes()),
        removed_source_reset_bits=55+32+23+23+1+27+32,preserved_valid_reset_bits=4,
        latency=3,II=1,R=1<<32,arithmetic_bytes_reverse_exact=True,
        invalid_reset_result='retained/arbitrary, NOT inherited reset-zero equivalence',
        root_or_calendar_delta=0,physical_register_or_LAB_saving_claim=False)

class Core:
    """Bit-width/old-valid model, including arbitrary dirty numeric startup."""
    WIDTHS=dict(ab=55,m=32,h2=23,h3=23,carry=1,mp=27,result=32)
    def __init__(self,p,*,reset_payload=False,seed=0):
        need(p in math.FIELDS,'L7_FIELD');self.p=p;self.reset_payload=reset_payload
        rng=random.Random(seed);self.data={name:rng.getrandbits(width) for name,width in self.WIDTHS.items()}
        self.valid=0;self.out_valid=False
    def tick(self,rst_n,accepted,lhs=0,rhs=0):
        old=dict(self.data);v=self.valid
        if not rst_n:
            self.valid=0;self.out_valid=False
            if self.reset_payload:self.data={name:0 for name in old}
            return self.out_valid,self.data['result']
        self.valid=((v<<1)|bool(accepted))&7;self.out_valid=bool(v&4)
        p=self.p;k,c=math.FIELDS[p];d=32-k;mask=(1<<d)-1
        if accepted:
            need(0<=lhs<2*p and 0<=rhs<p,'L7_INPUT_RANGE');self.data['ab']=lhs*rhs
        if v&1:
            lo=old['ab']&((1<<32)-1);mh=((lo>>k)-c*(lo&mask))&mask
            self.data.update(m=(mh<<k)|(lo&((1<<k)-1)),h2=old['ab']>>32,carry=int((lo>>k)<mh))
        if v&2:self.data.update(mp=c*(old['m']>>d)+((c*(old['m']&mask))>>d)+old['carry'],h3=old['h2'])
        if v&4:
            raw=old['h3']-old['mp'];self.data['result']=raw if raw>=0 else raw+p
        need(all(0<=value<(1<<self.WIDTHS[name]) for name,value in self.data.items()),'L7_WIDTH_MODEL')
        return self.out_valid,self.data['result']

def bind(bundle,*,enabled=1):
    need(type(enabled) is int and enabled in (0,1),'L7_LITERAL_FLAG')
    b=deepcopy(bundle)
    if not enabled:return b
    contract=verify()
    need(b['parameters']['P']==16 and b['parameters'].get('MONT_FACTORED')==1,'L7_P16_FACTORED_FIELD')
    need('montgomery_resetfree' not in b,'L7_NOT_ALREADY_BOUND')
    name=Path(PARENT).name
    need(name in b['files'] and sha(b['files'][name].encode())==PARENT_PIN,'L7_EXACT_BOUND_PARENT')
    b['files'].pop(name);changes={}
    for name,text in list(b['files'].items()):
        if not name.endswith('.sv'):continue
        new=identifiers(text,NAMES)
        need(identifiers(new,{v:k for k,v in NAMES.items()})==text,'L7_CONSUMER_IDENTIFIER_REVERSE')
        if new!=text:changes[name]=dict(parent_sha256=sha(text.encode()),candidate_sha256=sha(new.encode()));b['files'][name]=new
    need(changes,'L7_ACTUAL_CONSUMERS')
    b['files'][Path(RTL).name]=(ROOT/RTL).read_text()
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[SELF,RTL]))
    b['source_sha256']={name:sha((ROOT/name).read_bytes()) for name in b['source_dependencies']}
    b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256']={name:sha(text.encode()) for name,text in b['files'].items()}
    b['montgomery_resetfree']=dict(contract,identifier_changes=changes,scope='Numeric leaf only; valid/owner/fault/state resets and all calendars unchanged. Field gate/fit required.')
    return b

def validate(stdout,stderr,rc,config,assets):
    need(set(config)=={'p'} and config['p'] in math.FIELDS and not assets,'L7_NATIVE_CONFIG')
    expected=f'PASS_L7_RESETFREE P={config["p"]} checked=16925 canceled=224 holds=3166 edges=20091 outputs=4 latency=3 ii=1 dirty_reset_retention=true\n'
    need(type(rc) is int and rc==0 and stderr=='' and stdout==expected,'L7_NATIVE_TYPED_RESULT')
    return dict(status='PASS_expected_contracts',latency=3,II=1,products_per_cell=16925,
        reset_canceled=224,bubble_hold_edges=3166,dirty_retention_checked=True,
        scope='Paired canonical/lazy leaf only; no field resources or clock inheritance.',promotion_allowed=False)

def role(p):
    contract=verify();need(p in math.FIELDS and RTL_READY!='UNDECLARED','L7_FROZEN_SOURCE_READY')
    names=(PARENT,RTL,PAIR,CPP,SELF,'reference/stream27_l3_factored_model_v1.py','reference/__init__.py')
    files={name:(ROOT/name).read_bytes() for name in names};snapshot={name:sha(raw) for name,raw in files.items() if name.endswith('.sv')}
    import json
    ready=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-l7-resetfree-mont-v1',rtl_ready_at_utc=RTL_READY,
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()))
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='/unbound/l7/fpga',output_parent='/unbound/l7/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=TOP,sv_sources=[PAIR,PARENT,RTL],cpp_source=CPP,parameters=dict(P=p,Q=(2-p)%(1<<32)),
            cflags=['-std=c++17','-Werror=return-type',f'-DTEST_P={p}']),
        probe=dict(argv=['{exe}','--thread-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='normal-paired-resetfree-arithmetic-busyreset-cancel-holds',argv=['{exe}'],expected_returncode=0,
            validator=dict(source=SELF,function='validate',config=dict(p=p),assets={}))],test_role='normal',rtl_readiness=ready,reset_contract=contract)
    return manifest,files

def prepare(output,p,budget):
    from . import stream27_l3_factored_native_v1 as common
    return common.prepare(output,p,budget,role_builder=role,identity='normal',family='stream27-l7-resetfree')

def validate_mutants(stdout,stderr,rc,config,assets):
    need(set(config)=={'p'} and config['p'] in math.FIELDS and not assets,'L7_MUTANT_CONFIG')
    expected=f'PASS_L7_RESETFREE_MUTANTS P={config["p"]} checked=16925 canceled=224 holds=3166 detected=31 edges=20091 outputs=4 latency=3 ii=1 dirty_reset_retention=true\n'
    need(type(rc) is int and rc==0 and stdout==expected and stderr=='','L7_MUTANT_TYPED_RESULT')
    return dict(status='PASS_expected_contracts',detected=['pipe-reset','output-reset','invalid-hold','high-word','ignored-cancel'],
        good_products_per_cell=16925,good_outputs=4,latency=3,II=1,promotion_allowed=False)

def mutant_role(p):
    import json
    manifest,files=role(p)
    files.update({MUTANT_PAIR:(ROOT/MUTANT_PAIR).read_bytes(),MUTANT_CPP:(ROOT/MUTANT_CPP).read_bytes()})
    manifest['sources']={name:sha(raw) for name,raw in files.items()}
    manifest['build']=dict(manifest['build'],top=Path(MUTANT_PAIR).stem,
        sv_sources=manifest['build']['sv_sources']+[MUTANT_PAIR],cpp_source=MUTANT_CPP)
    manifest['steps']=[dict(name='deliberate-reset-valid-hold-arithmetic-cancel-mutants',argv=['{exe}'],expected_returncode=0,
        validator=dict(source=SELF,function='validate_mutants',config=dict(p=p),assets={}))]
    manifest['test_role']='deliberate_fault'
    snapshot={name:sha(raw) for name,raw in files.items() if name.endswith('.sv')}
    manifest['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-l7-resetfree-mutants-v1',
        rtl_ready_at_utc=MUTANT_READY,source_snapshot=snapshot,
        candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()))
    return manifest,files

def prepare_mutants(output,p,budget):
    from fpga.reference import stream27_l3_factored_native_v1 as common
    return common.prepare(output,p,budget,role_builder=mutant_role,identity='mutants',family='stream27-l7-resetfree')

def field_role(aw,p,field,api_sha256,production_ready):
    from fpga.reference import stream27_timing_field_native as normal
    bundle=bind(normal.field_bundle(aw,p,field,api_sha256))
    manifest,files=normal.role(aw,p,field,api_sha256,production_ready,bundle=bundle)
    manifest['rtl_readiness']['candidate_id']=f's4-l7-resetfree-field-aw{aw}-p{p}-f{field}-v1'
    manifest['rtl_readiness']['rtl_ready_at_utc']=RTL_READY
    manifest['l7_resetfree']=bundle['montgomery_resetfree']
    return manifest,files

def prepare_field(output,aw,field,budget,api_sha256):
    from fpga.reference import stream27_timing_field_native as normal
    return normal.prepare(output,aw,16,field,budget,api_sha256,'2026-10-01T23:13:29Z',
        role_builder=field_role,family='s4-l7-resetfree-field',version=1,
        prerequisites=[f'stream27-l7-resetfree-f{f}-normal-q1-v1' for f in range(3)])

def field_gate_ids(enabled):
    stem,version=('s4-l7-resetfree-field',1) if enabled else ('s4-r75-field',2)
    ids=[f'{stem}-aw{aw}-p16-f{field}-normal-q1-v{version}'
        for aw,field in ((8,0),(8,1),(8,2),(16,0),(16,2))]
    if enabled:ids=[f'stream27-l7-resetfree-f{field}-normal-q1-v1' for field in range(3)]+ids
    return ids

def fit_gates(enabled):
    import json
    refs=[]
    for qid in field_gate_ids(enabled):
        path=ROOT/'queue/evidence'/qid/'gate-receipt.json';raw=path.read_bytes();value=json.loads(raw)
        need(value['id']==qid and value['status']=='PASS_expected_contracts','L7_ACTUAL_FIELD_FIT_GATES')
        refs.append(dict(path=str(path),sha256=sha(raw),fields=dict(id=qid,status='PASS_expected_contracts')))
    return refs

def prepare_project(destination,api_sha256,*,enabled):
    """Same seven-flag field/settings, only L7 leaf/identifier delta.

    No native-only short top is fitted. LAB count, registers and timing are
    the measurements; scalar source reset counts cannot supply area credit.
    """
    import json
    from fpga.reference import stream27_timing_field_native as normal
    from fpga.cloud.plain_fit_v5 import FULL_TCL
    from fpga.tools import fit_dispatch
    need(type(enabled) is int and enabled in (0,1),'L7_FIELD_FIT_LITERAL_FLAG')
    destination=Path(destination).resolve();need(destination.is_relative_to(ROOT) and not destination.exists(),'L7_FIELD_FIT_FRESH')
    before=normal.field_bundle(16,16,0,api_sha256);b=bind(before,enabled=enabled)
    rtl=destination/'rtl';rtl.mkdir(parents=True)
    for name,text in b['files'].items():
        with (rtl/name).open('x') as stream:stream.write(text)
    params={name:value for name,value in b['parameters'].items() if name!='FIELD'}
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE 10AX115N4F40E3SG',
        'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4','set_global_assignment -name SEED 1',
        'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on','set_global_assignment -name SDC_FILE probe.sdc']
    qsf += ['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in b['rtl_sources']]
    qsf += [f'set_parameter -name {name} {value}' for name,value in params.items()]
    ports=['rst_n','in_slot_valid','frame_start','context_enabled','generation_in[*]','live_generation[*]','base_in[*]',
        'epoch_in[*]','correction_epoch[*]','correction_valid','correction_generation[*]','data_in[*]','c0_in[*]','c1_in[*]',
        'out_slot_valid','out_frame_start','out_eligible','out_error','fault_pending','generation_out[*]','data_out[*]',
        'out_epoch[*]','commit_valid','commit_frame_start','commit_generation[*]','commit_epoch[*]','commit_data[*]',
        'owner_count[*]','frame_accept','correction_accept','output_row[*]','cycle_count[*]','frame_count[*]']
    qsf += ['set_instance_assignment -name VIRTUAL_PIN ON -to {'+port+'}' for port in ports]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
        'probe.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n# Matched component reset-release exclusion; not whole/reset sign-off.\nset_false_path -from [get_ports {rst_n}]\n',
        'run.tcl':FULL_TCL}
    for name,text in controls.items():
        with (destination/name).open('x') as stream:stream.write(text)
    manifest=dict(schema='s4-l7-matched-sevenflag-field-sizing-v1',status='source_prepared_actual_native_required',
        top=b['top'],target='s4_l7_'+('candidate' if enabled else 'parent')+'_warm_p16_f0',
        edition='pro',device='10AX115N4F40E3SG',compile_processors=4,seed=1,clock_period_ns=10,address_width=16,
        bitstream_generation=False,allowed_stages=['syn','fit','sta'],core_parameters=params,
        source_sha256=b['generated_sha256'],control_sha256={name:sha(text.encode()) for name,text in controls.items()},
        intermediate_snapshots=True,source_dependencies=b['source_sha256'],geometry=b['geometry'],
        l7_enabled=enabled,l7_binding=b.get('montgomery_resetfree'),native_needed_ids=field_gate_ids(enabled),
        matched_parent=dict(api_sha256=api_sha256,generated_sha256=before['generated_sha256'],
            all_parameters_and_geometry_unchanged=True,extra_DSP_by_source=0,leaf_latency_delta=0),
        required_measurements=['direct LAB count','needed/placed ALMs','registers','M20K','DSP','four-corner setup/hold/pulse'],
        scope='One F0 seven-flag warm P16 field, reset-only matched pair. No scalar area credit, no whole fit/clock or 88-90% LAB guarantee. Shared whole overhead and other-prime packing remain separate.',
        full_N_numeric_locally_performed=False,promotion_allowed=False)
    with (destination/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    return fit_dispatch.snapshot(destination)

def submit_project(project,*,enabled):
    from fpga.tools import fit_submit
    qid='s4-l7-resetfree-'+('candidate' if enabled else 'parent')+'-field-p16-f0-v1'
    return fit_submit.submit(ROOT/'queue/standing-fits',qid,Path(project).resolve(),'10',1,
        dict(azure4=list('abcd'),aws6=list('ab')),'component_probe',dict(exemption='component_sizing_probe'),
        priority=50,requires=fit_gates(enabled),track='S',purpose='p16_diet')

if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    parser.add_argument('--p',type=int,choices=tuple(math.FIELDS));parser.add_argument('--aw',type=int,choices=(8,16))
    parser.add_argument('--field',type=int,choices=(0,1,2));parser.add_argument('--api-sha256')
    parser.add_argument('--project-mode',choices=('parent','candidate'));parser.add_argument('--submit-project',action='store_true');args=parser.parse_args()
    if args.project_mode:
        enabled=int(args.project_mode=='candidate')
        result=submit_project(args.output,enabled=enabled) if args.submit_project else prepare_project(args.output,args.api_sha256,enabled=enabled)
    elif args.aw is not None:
        need(args.field is not None and args.api_sha256,'L7_FIELD_CLI')
        result=prepare_field(args.output,args.aw,args.field,args.budget,args.api_sha256)
    else:
        need(args.p in math.FIELDS,'L7_SCALAR_CLI');result=prepare(args.output,args.p,args.budget)
    print(json.dumps(result,indent=2))
