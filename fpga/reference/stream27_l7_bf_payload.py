"""L7 BF internal numeric payload only: resetless/free-running; E5/II1.

The 195 source reset bits are NOT a register/ALM/LAB saving claim. All tags,
direction, validity and public output reset/hold remain exact. Dirty internal
data is undefined whenever invalid and never authorizes publication.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import re
from fpga.reference import lazy28_butterfly_v1 as oracle
from fpga.reference import stream27_l3_factored_model_v1 as mont

ROOT=oracle.ROOT
SELF='reference/stream27_l7_bf_payload.py'
PARENT=oracle.RTL
PARENT_PIN='ade6280dd1dac0fe3049ac2860dea7bbc7db292b634368e12f557b63865aa00d'
MULT=mont.RTL
MULT_PIN='866c2b19c9e6afbbb56ce71089288334579f90e977ca139b41097d0f9191c690'
RTL='rtl/kernel/genefer_stream27_lazy28_payload_free_v1.sv'
PAIR='rtl/tb/genefer_stream27_l7_bf_payload_pair_v1.sv'
CPP='rtl/tb/stream27_l7_bf_payload_pair_v1.cpp'
OLD_NAME='genefer_ntt_lazy28_butterfly_v1'
NEW_NAME=Path(RTL).stem
CLONE='rtl/tb/genefer_stream27_lazy28_factored_parent_v1.sv'
OLD_MULT='genefer_montgomery_mul28x27_sparse_pipe_v2'
FACTORED_MULT='genefer_stream27_montgomery28x27_factored_v1'
RTL_READY='2026-10-02T00:47:05Z'
FIELD_READY='2026-10-02T00:49:31Z'
MUTANT_READY='2026-10-02T00:57:42Z'
PAYLOAD='''    // No reset or CE on internal numeric payload. Fresh valid tokens fully
    // overwrite their operands before E1 multiplication and E5 publication.
    always_ff @(posedge clk)begin
        pre_v<=gs ? gs_diff_fold : v;pre_w<=w;
        prefix_pipe[0]<=gs ? gs_sum_fold : ct_u;
        for(int k=1;k<5;k=k+1)begin prefix_pipe[k]<=prefix_pipe[k-1];end
    end
'''
need=mont.need
def sha(raw):return hashlib.sha256(raw).hexdigest()
def ident(text,old,new):return re.sub(r'\b'+re.escape(old)+r'\b',new,text)
def parent():
    raw=(ROOT/PARENT).read_bytes();need(sha(raw)==PARENT_PIN,'BF_PAYLOAD_FROZEN_PARENT')
    need(sha((ROOT/MULT).read_bytes())==MULT_PIN,'BF_PAYLOAD_SAME_FACTORED_CHILD')
    return ident(raw.decode(),OLD_MULT,FACTORED_MULT)
def derived():
    text=parent()
    changes=[
        ('// Additive scalar lazy butterfly, not an adopted engine arithmetic profile.',
         '// Isolated L7 internal payload control-set cut, not an adopted field profile.'),
        ('// Accepted edge k -> output edge k+5, II=1, matching the frozen butterfly.',
         '// Accepted edge k -> output edge k+5, II=1; public reset/hold unchanged.'),
        ('// No lazy28 x lazy28 pointwise operation is admitted by this cell.',
         '// pre_v/pre_w/prefix are free-running, resetless numeric payload only.'),
        ('pre_valid<=0;pre_v<=0;pre_w<=0;gs_pipe<=0;','pre_valid<=0;gs_pipe<=0;'),
        ('for(int k=0;k<5;k=k+1)begin prefix_pipe[k]<=0;tag_pipe[k]<=0;end',
         'for(int k=0;k<5;k=k+1)begin tag_pipe[k]<=0;end'),
        ('            if(in_valid)begin pre_v<=gs ? gs_diff_fold : v;pre_w<=w;end\n',''),
        ('            prefix_pipe[0]<=gs ? gs_sum_fold : ct_u;\n',''),
        ('                prefix_pipe[k]<=prefix_pipe[k-1];tag_pipe[k]<=tag_pipe[k-1];',
         '                tag_pipe[k]<=tag_pipe[k-1];'),
        ('    // synthesis translate_off\n    initial if(TAG_W<1)',PAYLOAD+'    // synthesis translate_off\n    initial if(TAG_W<1)')]
    for old,new in changes:
        need(text.count(old)==1,'BF_PAYLOAD_LITERAL_SITE '+old);text=text.replace(old,new,1)
    text=ident(text,OLD_NAME,NEW_NAME)
    reverse=ident(text,NEW_NAME,OLD_NAME)
    for old,new in reversed(changes):
        if new:need(reverse.count(new)==1,'BF_PAYLOAD_REVERSE_SITE');reverse=reverse.replace(new,old,1)
        else:
            # Empty removals reinsert at their exact original neighbours.
            marker='            prefix_pipe[0]<=gs ? gs_sum_fold : ct_u;' if 'if(in_valid)' in old else '            tag_pipe[0]<=in_tag;'
            reverse=reverse.replace(marker,old+marker,1)
    need(reverse==parent(),'BF_PAYLOAD_REVERSE_EXACT')
    return text
def verify():
    need((ROOT/RTL).read_text()==derived(),'BF_PAYLOAD_EXACT_RTL')
    return dict(parent_sha256=PARENT_PIN,multiplier_sha256=MULT_PIN,candidate_sha256=sha((ROOT/RTL).read_bytes()),
        numeric_source_reset_bits_removed=195,numeric_input_CE_bits_removed=55,
        valid_owner_direction_tags_public_reset_preserved=True,public_invalid_hold_preserved=True,
        E0_to_E5=5,II=1,R=1<<32,pipeline_stages_removed=0,
        invalid_internal_payload='arbitrary/free-running; never publication authority',
        arithmetic_range='u/v<2P,w<P; outputs<2P; no lazy28 squared',
        physical_saving_claim=False)

def events(p):
    need(p in oracle.FIELDS,'BF_PAYLOAD_FIELD');rng=random.Random(0x195+p)
    rows=[]
    for i,row in enumerate(oracle.events(p)):
        reset,valid,gs,u,v,w,tag=row;cancel=int(not reset and i%2==1)
        if cancel:reset=1
        if not reset or cancel or not valid:
            u=rng.getrandbits(28);v=rng.getrandbits(28);w=rng.getrandbits(27)
        rows.append((int(reset),int(valid),int(gs),u,v,w,tag,cancel))
    return rows
def coverage(rows,p):
    pending=[];counts=dict(events=len(rows),checked=0,canceled=0,holds=0,dirty=0,ct=0,gs=0)
    for edge,(reset,valid,gs,u,v,w,tag,cancel) in enumerate(rows):
        active=bool(reset and not cancel)
        if not active:counts['canceled']+=len(pending);pending=[]
        if active and valid:
            pending.append(edge+5);counts['gs' if gs else 'ct']+=1
        else:counts['dirty']+=int(u>=2*p or v>=2*p or w>=p)
        if pending and pending[0]==edge:pending.pop(0);counts['checked']+=1
        else:counts['holds']+=1
    need(not pending and counts['dirty']>0,'BF_PAYLOAD_COMPLETE_DIRTY_CORPUS')
    return counts
def corpus(p):
    rows=events(p)
    return f'L7BFPAYLOAD1 {p} {len(rows)}\n'+''.join(' '.join(map(str,row))+'\n' for row in rows),coverage(rows,p)

class Core:
    """Explicit old-value transport, independent ordinary modular multiply."""
    def __init__(self,p,*,free=True,seed=0):
        self.p=p;self.free=free;rng=random.Random(seed)
        self.prefix=[rng.getrandbits(28) for _ in range(5)];self.v=rng.getrandbits(28);self.w=rng.getrandbits(27)
        self.tags=[0]*5;self.forms=[0]*5;self.pre=False;self.mult=[(False,0)]*4;self.output=(False,0,0,0)
    def tick(self,row):
        reset,valid,gs,u,v,w,tag,cancel=row;active=bool(reset and not cancel)
        p=self.p;total=(u+v)&((1<<29)-1);difference=(u+2*p-v)&((1<<29)-1)
        folded=lambda x:(x-2*p if x>=2*p else x)&((1<<28)-1)
        nextprefix=folded(total) if gs else ((u-p if u>=p else u)&((1<<28)-1))
        nextv=folded(difference) if gs else v
        oldprefix=list(self.prefix);oldtags=list(self.tags);oldforms=list(self.forms)
        oldpre=self.pre;oldv,oldw=self.v,self.w;oldmult=list(self.mult)
        if self.free or active:
            self.prefix=[nextprefix]+oldprefix[:4]
            if self.free or valid:self.v,self.w=nextv,w
        if not active:
            self.pre=False;self.tags=[0]*5;self.forms=[0]*5;self.mult=[(False,0)]*4;self.output=(False,0,0,0)
            if not self.free:self.prefix=[0]*5;self.v=self.w=0
            return self.output
        self.pre=bool(valid);self.tags=[tag]+oldtags[:4];self.forms=[gs]+oldforms[:4]
        self.mult=[(oldpre,(oldv*oldw*pow(1<<32,-1,p))%p)]+oldmult[:3]
        product_valid,product=oldmult[3]
        if product_valid:
            prefix=oldprefix[4]
            self.output=(True,prefix if oldforms[4] else prefix+product,
                product if oldforms[4] else prefix+p-product,oldtags[4])
        else:self.output=(False,*self.output[1:])
        return self.output

def validate(stdout,stderr,rc,config,assets):
    need(set(config)=={'p'} and config['p'] in oracle.FIELDS and not assets,'BF_PAYLOAD_NATIVE_CONFIG')
    p=config['p'];_,c=corpus(p)
    expected=f'PASS_L7_BF_PAYLOAD P={p} '+ ' '.join(f'{key}={value}' for key,value in c.items())+' outputs=2 latency=5 ii=1\n'
    need(type(rc) is int and rc==0 and stderr=='' and stdout==expected,'BF_PAYLOAD_TYPED_RESULT')
    return dict(status='PASS_expected_contracts',p=p,**c,outputs=2,latency=5,II=1,
        public_reset_hold_exact=True,dirty_invalid_payload_checked=True,promotion_allowed=False)
def role(p):
    contract=verify();text,counts=corpus(p)
    names=[PARENT,MULT,RTL,PAIR,CPP,SELF,'reference/lazy28_butterfly_v1.py',
        'reference/stream27_l3_factored_model_v1.py','reference/__init__.py']
    files={name:(ROOT/name).read_bytes() for name in names}
    files[CLONE]=ident(parent(),OLD_NAME,Path(CLONE).stem).encode();files['vectors/l7-bf-payload.txt']=text.encode()
    snapshot={name:sha(raw) for name,raw in files.items() if name.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-l7-bf-payload-free-v1',rtl_ready_at_utc=RTL_READY,
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()))
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/l7-bf/fpga',output_parent='/not-a-dispatch-path/l7-bf/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=Path(PAIR).stem,sv_sources=[PAIR,CLONE,RTL,MULT],cpp_source=CPP,
            parameters=dict(P=p,Q=(2-p)%(1<<32)),cflags=['-std=c++17','-Werror=return-type',f'-DTEST_P={p}']),
        probe=dict(argv=['{exe}','--thread-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='normal-paired-bf-payload-values-reset-cancel-holds',argv=['{exe}','{root}/vectors/l7-bf-payload.txt'],expected_returncode=0,
            validator=dict(source=SELF,function='validate',config=dict(p=p),assets={}))],
        test_role='normal',rtl_readiness=readiness,bf_payload_contract=contract,counts=counts)
    preflight(manifest,files)
    return manifest,files
def preflight(manifest,files):
    # Use the actual frozen command grammar before uploading a fresh packet.
    from fpga.tools.native_source_gate_v1 import expand
    for step in [manifest['probe']]+manifest['steps']:
        expand(step['argv'],Path('/fixture/exe'),Path('/fixture/source'))
    need(all(name in files for name in manifest['build']['sv_sources']+[manifest['build']['cpp_source']]),'BF_PAYLOAD_CLOSED_BUILD')
    return manifest
def prepare(output,p,budget):
    from fpga.reference import stream27_l3_factored_native_v1 as common
    need(RTL_READY!='SOURCE_NOT_YET_FROZEN','BF_PAYLOAD_READY_DECLARED')
    return common.prepare(output,p,budget,role_builder=role,family='stream27-l7-bf-payload-rootarg',identity='normal')

def bind(bundle,*,enabled=1):
    need(type(enabled) is int and enabled in (0,1),'BF_PAYLOAD_LITERAL_FLAG')
    b=deepcopy(bundle)
    if not enabled:return b
    contract=verify();name=Path(PARENT).name
    need(b['parameters']['P']==16 and b['parameters'].get('MONT_FACTORED')==1,'BF_PAYLOAD_P16_FACTORED_FIELD')
    need('montgomery_resetfree' not in b and 'bf_payload_free' not in b,'BF_PAYLOAD_ISOLATED_NOT_MONT_MIX')
    need(b['files'].get(name)==parent(),'BF_PAYLOAD_EXACT_BOUND_BF')
    need(b['files'].get(Path(MULT).name)==(ROOT/MULT).read_text(),'BF_PAYLOAD_FROZEN_BOUND_MULTIPLIER')
    changes={}
    for filename,text in list(b['files'].items()):
        if filename==name:
            # Keep source filename stable; module identifiers alone distinguish
            # the candidate. No generated physical root/calendar file changes.
            new=(ROOT/RTL).read_text()
        else:
            new=ident(text,OLD_NAME,NEW_NAME)
            need(ident(new,NEW_NAME,OLD_NAME)==text,'BF_PAYLOAD_CONSUMER_REVERSE')
        if new!=text:
            changes[filename]=dict(parent_sha256=sha(text.encode()),candidate_sha256=sha(new.encode()))
            b['files'][filename]=new
    need(len(changes)>1,'BF_PAYLOAD_REAL_FIELD_CONSUMERS')
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[SELF,RTL]))
    b['source_sha256']={n:sha((ROOT/n).read_bytes()) for n in b['source_dependencies']}
    b['generated_sha256']={n:sha(t.encode()) for n,t in b['files'].items()}
    b['bf_payload_free']=dict(contract,identifier_changes=changes,calendar_delta=0,
        scope='BF internal payload only, same frozen factored Montgomery child; no L7 Mont/L3b mixture or whole area credit.')
    return b

def field_role(aw,p,field,api_sha256,production_ready):
    from fpga.reference import stream27_timing_field_native as normal
    bundle=bind(normal.field_bundle(aw,p,field,api_sha256))
    manifest,files=normal.role(aw,p,field,api_sha256,production_ready,bundle=bundle)
    manifest['rtl_readiness']['candidate_id']=f's4-l7-bf-payload-field-aw{aw}-p{p}-f{field}-v1'
    manifest['rtl_readiness']['rtl_ready_at_utc']=FIELD_READY
    manifest['bf_payload_free']=bundle['bf_payload_free']
    return manifest,files
def prepare_field(output,aw,field,budget,api_sha256):
    from fpga.reference import stream27_timing_field_native as normal
    return normal.prepare(output,aw,16,field,budget,api_sha256,'2026-10-01T23:13:29Z',
        role_builder=field_role,family='s4-l7-bf-payload-field',version=2,
        prerequisites=[f'stream27-l7-bf-payload-rootarg-f{f}-normal-q1-v1' for f in range(3)])

MUTATIONS=(
    ('out-valid-reset','out_valid<=0;y0<=0;y1<=0;out_tag<=0;','y0<=0;y1<=0;out_tag<=0;'),
    ('public-reset','out_valid<=0;y0<=0;y1<=0;out_tag<=0;','out_valid<=0;'),
    ('public-hold','if(product_valid)begin','begin'),
    ('tag-age','out_tag<=tag_pipe[4];','out_tag<=tag_pipe[3];'),
    ('ignored-cancel',None,None))
def mutant_files():
    """Explicit exact symbols, no ambiguous prefix/substr replacement."""
    verify();cells=[];pair=(ROOT/PAIR).read_text();cpp=(ROOT/CPP).read_text()
    top=Path(PAIR).stem+'_mutants';sv='rtl/tb/'+top+'.sv';cc='rtl/tb/l7_bf_payload_mutants.cpp'
    pair=ident(pair,Path(PAIR).stem,top)
    anchor='    output logic [31:0] out_tag,old_out_tag\n'
    need(pair.count(anchor)==1,'BF_PAYLOAD_MUTANT_PORT_SITE')
    pair=pair.replace(anchor,anchor.rstrip('\n')+',\n    output logic [4:0] bad_valid,\n    output logic [27:0] bad_y0[0:4],bad_y1[0:4],\n    output logic [31:0] bad_tag[0:4]\n',1)
    instances=[]
    for index,(role,old,new) in enumerate(MUTATIONS):
        name=f'genefer_stream27_l7_bf_mutant_{index}_v1';text=(ROOT/RTL).read_text()
        if old is not None:
            need(text.count(old)==1,'BF_PAYLOAD_MUTANT_EXACT_ANCHOR '+role);text=text.replace(old,new,1)
        cells.append(ident(text,NEW_NAME,name))
        reset='rst_n' if index==4 else 'local_rst_n'
        # Ignored cancel mutant still kills new admission; its stale internal
        # validity/output is the defect. Never feed an illegal dirty word as a
        # valid operand merely to trigger an unrelated input assertion.
        valid='in_valid&&!cancel' if index==4 else 'in_valid'
        instances.append(f'''    {name} #(.P(P),.Q(Q)) mutant{index} (
        .clk,.rst_n({reset}),.in_valid({valid}),.gs,.u,.v,.w,.in_tag,
        .out_valid(bad_valid[{index}]),.y0(bad_y0[{index}]),.y1(bad_y1[{index}]),.out_tag(bad_tag[{index}]));\n''')
    need(pair.count('endmodule')==1,'BF_PAYLOAD_MUTANT_MODULE_END')
    pair=pair.replace('endmodule',''.join(instances)+'endmodule',1)
    cpp=cpp.replace('V'+Path(PAIR).stem,'V'+top)
    insert=''' unsigned detected=0;
 auto detect=[&](bool expected_valid,uint32_t expected0,uint32_t expected1,uint32_t expected_tag){
  for(unsigned i=0;i<5;i++)if(bool(d.bad_valid&(1u<<i))!=expected_valid||d.bad_y0[i]!=expected0||d.bad_y1[i]!=expected1||d.bad_tag[i]!=expected_tag)detected|=1u<<i;
 };
'''
    anchor=' uint32_t last0=0,last1=0,lasttag=0;bool lastvalid=false;\n'
    need(cpp.count(anchor)==1,'BF_PAYLOAD_MUTANT_MONITOR_SITE');cpp=cpp.replace(anchor,anchor+insert,1)
    anchor='  if(active&&valid){\n';need(cpp.count(anchor)==1,'BF_PAYLOAD_MUTANT_BEFORE_SITE')
    cpp=cpp.replace(anchor,'  detect(lastvalid,last0,last1,lasttag);\n'+anchor,1)
    anchor='  lastvalid=due;\n';need(cpp.count(anchor)==1,'BF_PAYLOAD_MUTANT_AFTER_SITE')
    cpp=cpp.replace(anchor,'  detect(due,last0,last1,lasttag);\n'+anchor,1)
    anchor=' std::cout<<"PASS_L7_BF_PAYLOAD P="';need(cpp.count(anchor)==1,'BF_PAYLOAD_MUTANT_FOOTER_SITE')
    cpp=cpp.replace(anchor,' need(detected==31,"BF_PAYLOAD_MUTANTS_NOT_ALL_DETECTED");\n std::cout<<"PASS_L7_BF_PAYLOAD_MUTANTS P="',1)
    anchor='<<" outputs=2 latency=5 ii=1\\n";';need(cpp.count(anchor)==1,'BF_PAYLOAD_MUTANT_COUNT_SITE')
    cpp=cpp.replace(anchor,'<<" detected="<<detected<<" outputs=2 latency=5 ii=1\\n";',1)
    return {sv:pair.encode(),cc:cpp.encode(),'rtl/tb/l7_bf_payload_mutant_cells.sv':''.join(cells).encode()},top,sv,cc
def validate_mutants(stdout,stderr,rc,config,assets):
    need(set(config)=={'p'} and config['p'] in oracle.FIELDS and not assets,'BF_PAYLOAD_MUTANT_CONFIG')
    p=config['p'];_,c=corpus(p)
    expected=f'PASS_L7_BF_PAYLOAD_MUTANTS P={p} '+' '.join(f'{k}={v}' for k,v in c.items())+' detected=31 outputs=2 latency=5 ii=1\n'
    need(type(rc) is int and rc==0 and stderr=='' and stdout==expected,'BF_PAYLOAD_MUTANT_TYPED_RESULT')
    return dict(status='PASS_expected_contracts',p=p,detected=[m[0] for m in MUTATIONS],**c,promotion_allowed=False)
def mutant_role(p):
    manifest,files=role(p);extra,top,sv,cc=mutant_files();files.update(extra)
    manifest['sources']={name:sha(raw) for name,raw in files.items()}
    manifest['build']=dict(manifest['build'],top=top,
        sv_sources=[sv,CLONE,RTL,MULT,'rtl/tb/l7_bf_payload_mutant_cells.sv'],cpp_source=cc)
    manifest['steps']=[dict(name='deliberate-bf-reset-hold-tag-cancel-mutants',argv=['{exe}','{root}/vectors/l7-bf-payload.txt'],
        expected_returncode=0,validator=dict(source=SELF,function='validate_mutants',config=dict(p=p),assets={}))]
    manifest['test_role']='deliberate_fault'
    snapshot={name:sha(raw) for name,raw in files.items() if name.endswith('.sv')}
    manifest['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-l7-bf-payload-mutants-v1',
        rtl_ready_at_utc=MUTANT_READY,source_snapshot=snapshot,
        candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()))
    preflight(manifest,files)
    return manifest,files
def prepare_mutants(output,p,budget):
    from fpga.reference import stream27_l3_factored_native_v1 as common
    need(MUTANT_READY!='SOURCE_NOT_YET_FROZEN','BF_PAYLOAD_MUTANT_READY')
    return common.prepare(output,p,budget,role_builder=mutant_role,family='stream27-l7-bf-payload-rootarg',identity='mutants')

def field_gate_ids():
    return [f'stream27-l7-bf-payload-rootarg-f{f}-normal-q1-v1' for f in range(3)]+[
        f's4-l7-bf-payload-field-aw{aw}-p16-f{f}-normal-q1-v2' for aw,f in ((8,0),(8,1),(8,2),(16,0),(16,2))]
def fit_gate_ids():
    # Component-sizing exemption: actual leaf + actual small field normals;
    # full-N numerical jobs overlap, and remain required for integration.
    return field_gate_ids()[:6]
def fit_gates():
    refs=[]
    for qid in fit_gate_ids():
        path=ROOT/'queue/evidence'/qid/'gate-receipt.json';raw=path.read_bytes();value=json.loads(raw)
        need(value['id']==qid and value['status']=='PASS_expected_contracts','BF_PAYLOAD_ACTUAL_FIELD_FIT_GATE')
        refs.append(dict(path=str(path),sha256=sha(raw),fields=dict(id=qid,status='PASS_expected_contracts')))
    return refs
def prepare_project(destination,api_sha256):
    """Reuse exact seven-flag parent project controls; BF-only source delta.

    Compare to collected resetful parent, never the losing Montgomery cut.
    This construction completes before the project is captured/submitted.
    """
    from fpga.reference import stream27_l7_resetfree_mont as project_donor
    from fpga.reference import stream27_timing_field_native as normal
    from fpga.tools import fit_dispatch
    destination=Path(destination).resolve()
    before=normal.field_bundle(16,16,0,api_sha256);after=bind(before)
    project_donor.prepare_project(destination,api_sha256,enabled=0)
    # Source filename set and controls remain identical; candidate module
    # declaration/consumer identifiers change under an exact reverse guard.
    need(set(before['files'])==set(after['files']),'BF_PAYLOAD_MATCHED_FILE_SET')
    for name,text in after['files'].items():
        path=destination/'rtl'/name
        need(path.read_text()==before['files'][name],'BF_PAYLOAD_FRESH_DONOR_FILE')
        if text!=before['files'][name]:path.write_text(text)
    path=destination/'manifest.json';m=json.loads(path.read_text())
    m.pop('l7_enabled');m.pop('l7_binding')
    m.update(schema='s4-l7-bf-payload-sevenflag-field-sizing-v1',target='s4_l7_bf_payload_warm_p16_f0',
        source_sha256=after['generated_sha256'],source_dependencies=after['source_sha256'],
        bf_payload_free=after['bf_payload_free'],native_needed_ids=fit_gate_ids(),
        integration_native_needed_ids=field_gate_ids(),
        full_N_native_scope='Automatic F0/F2 successors, not inherited from small N and not a component-sizing prerequisite.',
        comparison=dict(parent_id='s4-l7-resetfree-parent-field-p16-f0-v1',parent_host='Azure',parent_workers=4,
            exact_parent_manifest_sha256='b580c8ff897585934fb2dcde19af9b16bc05c48193c65c76ef135821afabdef0',
            changed_only='195 BF internal numeric reset bits and55 input CE bits plus namespace; unchanged frozen Mont866c',
            controls_parameters_geometry_identical=True,Mont_reset_only_or_L3b_combined=False),
        scope='One F0 seven-flag field BF-only control-set experiment. Report LABs/registers/four-corner timing; no whole area/clock or source bit count saving credit.')
    path.write_text(json.dumps(m,indent=2)+'\n')
    return fit_dispatch.snapshot(destination)
def submit_project(project):
    from fpga.tools import fit_submit
    return fit_submit.submit(ROOT/'queue/standing-fits','s4-l7-bf-payload-field-p16-f0-v1',Path(project).resolve(),'10',1,
        dict(azure4=list('abcd')),'component_probe',dict(exemption='component_sizing_probe'),
        priority=50,requires=fit_gates(),track='S',purpose='p16_diet')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--p',type=int,choices=oracle.FIELDS,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.p,args.budget),indent=2))
