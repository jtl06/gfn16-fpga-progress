"""Normal-first four-cell comparison: new/frozen canonical and lazy REDC."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference import stream27_l3_factored_model_v1 as s
ROOT=s.ROOT
SELF='reference/stream27_l3_factored_native_v1.py'
TOP='genefer_stream27_l3_factored_pair_v1';PAIR='rtl/tb/'+TOP+'.sv'
CPP='rtl/tb/stream27_l3_factored_pair_v1.cpp'
DONOR='rtl/tb/montgomery28x27_sparse_v2.cpp'
READY='results/throughput-20260929/stream27-l3-factored-source-v1/rtl-ready-v2.json'
PINS={s.RTL:'866c2b19c9e6afbbb56ce71089288334579f90e977ca139b41097d0f9191c690',
 'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv':'501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
 'rtl/kernel/genefer_montgomery_mul28x27_sparse_pipe_v2.sv':'a93cb002eb08e585e62a847ef4b070175ae8108919da30ea5bf67dad3a597026',
 DONOR:'123ce08170b27109d00a43702796b820e78be4edcb8d1a6cacc5f945261472d9'}
PACKAGE_SHA='03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
STAGER_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
COMPANION_SHA='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a'
HIGH={104857601:6003,69206017:528,67239937:52}
PAIR_TEXT='''// Native comparison fixture only, not an integration or physical probe.
module genefer_stream27_l3_factored_pair_v1 #(
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,
    input logic [27:0] lhs,
    input logic [26:0] rhs,
    output logic [3:0] out_valid,
    output logic [31:0] lazy_result,canonical_result,old_lazy_result,old_canonical_result
);
    wire [31:0] x={4'b0,lhs},y={5'b0,rhs};
    wire [31:0] canonical_lhs=x>=P ? x-P : x;
    genefer_stream27_montgomery28x27_factored_v1 #(.P(P),.Q(Q)) lazy_new (
        .clk,.rst_n,.in_valid,.lhs,.rhs,.out_valid(out_valid[0]),.result(lazy_result));
    genefer_stream27_montgomery_factored_v1 #(.P(P),.Q(Q)) canonical_new (
        .clk,.rst_n,.in_valid,.lhs(canonical_lhs),.rhs(y),.out_valid(out_valid[1]),.result(canonical_result));
    genefer_montgomery_mul28x27_sparse_pipe_v2 #(.P(P),.Q(Q)) lazy_old (
        .clk,.rst_n,.in_valid,.lhs,.rhs,.out_valid(out_valid[2]),.result(old_lazy_result));
    genefer_montgomery_mul27_sparse_pipe #(.P(P),.Q(Q)) canonical_old (
        .clk,.rst_n,.in_valid,.lhs(canonical_lhs),.rhs(y),.out_valid(out_valid[3]),.result(old_canonical_result));
endmodule
'''
def verify_pins():
    for n,p in PINS.items():s.need(s.sha((ROOT/n).read_bytes())==p,'L3_NATIVE_FROZEN_PIN '+n)
def cpp():
    verify_pins();t=(ROOT/DONOR).read_text()
    old='genefer_montgomery_mul28x27_sparse_pipe_v2';t=t.replace(old,TOP)
    t=t.replace('d.result','d.lazy_result')
    def once(a,b):
        nonlocal t
        s.need(t.count(a)==1,'L3_DONOR_SITE '+a);t=t.replace(a,b)
    once('else if(d.lazy_result!=held)',
      'else if(d.lazy_result!=held || d.canonical_result!=held || d.old_lazy_result!=held || d.old_canonical_result!=held)')
    once('bool(d.out_valid)!=due','d.out_valid!=(due?15:0)')
    once('d.lazy_result!=pending.front().expected || d.lazy_result>=P',
      'd.lazy_result!=pending.front().expected || d.canonical_result!=pending.front().expected || '
      'd.old_lazy_result!=pending.front().expected || d.old_canonical_result!=pending.front().expected || d.lazy_result>=P')
    once('if(d.lazy_result!=held)',
      'if(d.lazy_result!=held || d.canonical_result!=held || d.old_lazy_result!=held || d.old_canonical_result!=held)')
    once('PASS_MONT28 P=','PASS_L3_FACTORED P=')
    once('<<" edges="<<edge<<"\\n";','<<" edges="<<edge<<" outputs=4\\n";')
    return t
def verify():
    verify_pins();s.need((ROOT/PAIR).read_text()==PAIR_TEXT and (ROOT/CPP).read_text()==cpp(),'L3_NATIVE_EXACT_FIXTURE')
def validate(stdout,stderr,rc,config,assets):
    s.need(set(config)=={'p'} and config['p'] in HIGH and not assets,'L3_NORMAL_CONFIG')
    p=config['p'];expected=f'PASS_L3_FACTORED P={p} checked=16925 canceled=224 holds=3166 high_inputs={HIGH[p]} edges=20091 outputs=4\n'
    s.need(type(rc) is int and rc==0 and stderr=='' and stdout==expected,'L3_NORMAL_TYPED_RESULT')
    return dict(status='PASS_expected_contracts',p=p,products_per_cell=16925,independent_result_checks=4*16925,
      latency=3,II=1,reset_cancelled=224,hold_edges=3166,high_inputs=HIGH[p],outputs=4,
      profile='unchanged_R2^32',promotion_allowed=False,physical_mapping_measured=False)
def dump(path,v):
    with path.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def role(p):
    verify();s.need(p in HIGH,'L3_NORMAL_FIELD')
    names=(*PINS,PAIR,CPP,SELF,'reference/stream27_l3_factored_model_v1.py',
       'tests/test_stream27_l3_factored_model_v1.py','reference/__init__.py',READY)
    files={n:(ROOT/n).read_bytes() for n in names}
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
      source_root='/not-a-dispatch-path/stream27-l3/fpga',output_parent='/not-a-dispatch-path/stream27-l3/output',
      sources={n:s.sha(raw) for n,raw in files.items()},
      build=dict(top=TOP,sv_sources=[PAIR,s.RTL,'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv',
          'rtl/kernel/genefer_montgomery_mul28x27_sparse_pipe_v2.sv'],cpp_source=CPP,
          parameters=dict(P=p,Q=(2-p)%(1<<32)),cflags=['-std=c++17','-Werror=return-type',f'-DTEST_P={p}']),
      probe=dict(argv=['{exe}','--thread-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[dict(name='normal-four-cell-values-latency',argv=['{exe}'],expected_returncode=0,
          validator=dict(source=SELF,function='validate',config=dict(p=p),assets={}))],
      scope='Normal standalone canonical/lazy arithmetic, independent ordinary modular oracle plus both frozen leaves. No field/stream/fit clock claim.',
      reduction=s.ledger(),test_role='normal',rtl_readiness=json.loads((ROOT/READY).read_text()))
    return m,files
def prepare(output,p,budget,*,role_builder=None,identity='normal',family='stream27-l3-factored'):
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve();s.need(not output.exists(),'L3_FRESH_OUTPUT')
    s.need(not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE','queue/PAUSE')),'L3_PAUSE')
    m,files=(role if role_builder is None else role_builder)(p);source=output/'input/source/fpga';source.mkdir(parents=True)
    for n,raw in files.items():
        path=source/n;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m);variants=[]
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f'{family}-f{list(HIGH).index(p)}-{identity}-{pair}-v1';packet=output/('packet-'+pair)
        r=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],
          ticket_sha256=r['ticket_sha256'],manifest_sha256=s.sha((packet/'manifest.json').read_bytes()),native_root=r['native_root'],
          runner='tools/native_class_package_v2.py',runner_sha256=PACKAGE_SHA,stager=str(ROOT/'tools/native_package_v3.py'),
          stager_sha256=STAGER_SHA,stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=COMPANION_SHA)],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=f'{family}-f{list(HIGH).index(p)}-{identity}-q1-v1',owner='merged-ntt-model',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
      tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
      minimum_ram_gib=4,minimum_ram_rationale='Explicit bounded four-scalar-cell exploration, desired8; no full transform or measured peak claim.',
      est_minutes=2,promotion_bound=False,packages=variants,test_role=m['test_role'],rtl_readiness=m['rtl_readiness'])
    dump(output/'global-ticket-v1.json',ticket);return dict(id=ticket['id'],ticket=str(output/'global-ticket-v1.json'),source_files=len(files))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write-fixture',action='store_true');p.add_argument('--p',type=int,choices=tuple(HIGH))
    p.add_argument('--output',type=Path);p.add_argument('--budget',type=Path);a=p.parse_args()
    if a.write_fixture:
        verify_pins()
        for name,text in ((PAIR,PAIR_TEXT),(CPP,cpp())):
            s.need(not (ROOT/name).exists(),'L3_FIXTURE_FRESH')
            with (ROOT/name).open('x') as f:f.write(text)
        verify();print('source_ready_normal_only')
    else:print(json.dumps(prepare(a.output,a.p,a.budget),indent=2))
