"""Actual old/new CRT module pairing, independent Garner and reset controls."""
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference import stream27_r15_storage_ram_bind as binder
from fpga.reference import stream27_r15_storage_ram_native as normal

ROOT=binder.ROOT
SELF='reference/stream27_r15_crt_numeric_pair_native.py'
CPP='rtl/tb/stream27_r15_crt_numeric_pair_v1.cpp'
TOP='genefer_stream27_r15_crt_numeric_pair_v1'
PARENT='genefer_crt3_27_mont_pipe_parent_r15_v1'
IDS={kind:'s4-p16-r15-crt-numeric-pair-'+kind+'-q1-v1' for kind in ('normal','reset')}


def wrapper():
    return f'''module {TOP} (
 input logic clk,rst_n,in_valid,input logic [31:0] r1,r2,r3,
 output wire parent_valid,candidate_valid,
 output wire signed [95:0] parent_coefficient,candidate_coefficient);
 {PARENT} parent (.clk,.rst_n,.in_valid,.r1,.r2,.r3,
  .ready(),.out_valid(parent_valid),.coefficient(parent_coefficient));
 genefer_crt3_27_mont_pipe candidate (.clk,.rst_n,.in_valid,.r1,.r2,.r3,
  .ready(),.out_valid(candidate_valid),.coefficient(candidate_coefficient));
endmodule
'''


def expected(reset=False):
    mask=(1<<64)-1
    def random(n):
        x=(n+0x9e3779b97f4a7c15)&mask
        x=((x^(x>>30))*0xbf58476d1ce4e5b9)&mask
        x=((x^(x>>27))*0x94d049bb133111eb)&mask
        return x^(x>>31)
    valid=[False]*16
    cycles=accepted=eligible=reset_edges=0
    comparisons=1
    def tick(enable,rst):
        nonlocal valid,cycles,accepted,eligible,reset_edges,comparisons
        valid=[bool(enable and rst)]+valid[:-1] if rst else [False]*16
        accepted+=int(enable and rst)
        eligible+=int(valid[-1]);reset_edges+=int(not rst);cycles+=1;comparisons+=3
    for _ in range(4):tick(True,False)
    if not reset:
        for i in range(10000):tick(i<64 or random(i)%5!=0,True)
    else:
        for age in range(32):
            for _ in range(age):tick(True,True)
            valid=[False]*16;comparisons+=1
            for i in range(3):tick(i%2==0,False)
            for i in range(96):tick(i<48 or random(cycles)%3!=0,True)
    return (f'R15_CRT_{"RESET" if reset else "NORMAL"}_PASS cycles={cycles} accepted={accepted} '
            f'eligible={eligible} comparisons={comparisons} reset_edges={reset_edges} '
            'coefficient96=1 II1=1 E16=1 independent_garner=1\n')


def role(kind='normal'):
    binder.need(kind in IDS,'PAIRED_MODE')
    # Exact donor source graph, not an approximate mechanics-only shift clone.
    _,captured,parent=normal.role('aw8')
    original=parent['files'][binder.CRT]
    # parent above is bound; reverse only these numeric delays.
    original=binder.unbind_crt(original,r1=1,d3=1,x12=1)
    candidate=binder.bind_crt(original,r1=1,d3=1,x12=1)
    binder.need(original.count('module genefer_crt3_27_mont_pipe (')==1,'PARENT_MODULE_IDENTIFIER')
    files={'rtl/'+binder.CRT:candidate.encode(),
           'rtl/'+PARENT+'.sv':original.replace('module genefer_crt3_27_mont_pipe (','module '+PARENT+' (').encode(),
           'rtl/'+binder.NUMERIC_LEAF:binder.numeric_leaf().encode(),
           'rtl/'+TOP+'.sv':wrapper().encode(),
           'rtl/genefer_montgomery_mul27_sparse_pipe.sv':captured['rtl/genefer_montgomery_mul27_sparse_pipe.sv']}
    for n in (CPP,'rtl/tb/native_runtime_context_v1.h',SELF,binder.SELF,normal.SELF,
              'reference/stream27_r15_storage_ram_model.py'):
        files[n]=(ROOT/n).read_bytes()
    snapshot={n:binder.sha(raw) for n,raw in files.items() if n.endswith('.sv')}
    steps=[dict(name='r15-crt-'+kind,argv=['{exe}']+(['--reset-test'] if kind=='reset' else []),
                expected_returncode=0,expected_stdout=expected(kind=='reset'),expected_stderr='')]
    if kind=='reset':
        steps.append(dict(name='r15-crt-wrong-word-control',argv=['{exe}','--wrong-word'],
                          expected_returncode=1,expected_stdout='',expected_stderr='R15_CRT_CANDIDATE_ORACLE\n'))
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
        sources={n:binder.sha(raw) for n,raw in files.items()},
        build=dict(top=TOP,sv_sources=[n for n in files if n.endswith('.sv')],cpp_source=CPP,parameters={},
                   runtime_threads=1,cflags=['-std=c++17','-O2','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=steps,test_role='normal' if kind=='normal' else 'deliberate_fault',
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-p16-r15-crt-numeric-pair-v1',
            source_snapshot=snapshot,candidate_source_sha256=binder.sha(json.dumps(snapshot,sort_keys=True,separators=(',',':'))),
            rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')),
        scope='Source-identical FIELD100 CRT numeric delay delta. Whole coefficient96 every edge, E16/II1, independent Garner, reset ages0..31 and comparison corruption control. No whole owner/fault/publication/clock/resource qualification.',
        promotion_allowed=False)
    return manifest,files


def emit(output,kind='normal'):
    out=Path(output).resolve();binder.need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_PAIR_OUTPUT')
    m,files=role(kind);source=out/'source/fpga';source.mkdir(parents=True)
    for n,raw in files.items():
        p=source/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    m['source_root']=str(source);normal.dump(out/'manifest.json',m)
    return dict(id=IDS[kind],manifest=str(out/'manifest.json'),compiled_rtl=5,status='SOURCE_READY_NOT_NATIVE')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--kind',choices=tuple(IDS),default='normal');a=p.parse_args()
    print(json.dumps(emit(a.output,a.kind),indent=2))
