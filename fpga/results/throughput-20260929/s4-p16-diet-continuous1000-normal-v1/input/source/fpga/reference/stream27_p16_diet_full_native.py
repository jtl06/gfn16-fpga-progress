"""Normal-first fullN whole-P16 diet/T5b role, source generation only locally.

Same independent native iterative reference and legacy1/feed8 dense program
as the canonical register donor. All actual HDL/fullN arithmetic is queued.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_p16_diet_full_native.py'
TEST = 'tests/test_stream27_host_chain_diet.py'
CPP = 'rtl/tb/stream27_p16_diet_full_native.cpp'
OLD_CPP = 'rtl/tb/stream27_host_chain_full_native_v1.cpp'
REFERENCE = 'rtl/tb/stream27_host_chain_full_reference_v1.h'
NTT = 'rtl/tb/stream27_shared_reference_ntt_v1.h'
HEADER = 'rtl/tb/s4_host_chain_full_config_v1.h'
N, P, BASE, SEED = 65536, 16, 604832956, 65534
IDENTIFIER = 's4-aw16-p16-diet-whole-normal-q1-v1'
CANDIDATE = 's4-p16-diet-whole-v1'
FLAGS = dict(CORR_SERIAL_BFS=2, COMM_STAGE_SHARED_MLAB=1, MONT_FACTORED=1, CANONICAL_PIPE_STAGES=1)
GEOMETRY = dict(first_digit=8458, warm_interval=8459, carry_done=12557, rows=4096)
PINS = {OLD_CPP:'30cada68746f625d95641e59e49b079b0896e0534a5288f196f95200ea8d4fa7',
    REFERENCE:'88849a77ad7c58fc99f6d56eeded2a772a78fbe2b2da03fabdf7ac71aaf12c54',
    NTT:'c7837ba92829293131efda704dfdde347708641bf9aff46dccbcb87b825ba390'}


def need(ok, label):
    if not ok: raise ValueError('S4_P16_DIET_FULL_'+label)


def sha(raw): return hashlib.sha256(raw).hexdigest()


def counts():
    interval, done = GEOMETRY['warm_interval'], GEOMETRY['carry_done']
    return dict(jobs=2, operations=9, feed_descriptors=7, true_final_rows=2*N//P,
        paired_reads=2*N, copied_words=2*N, partial_reads=1,
        canonical_cycles=18*N, image_copy_cycles=2*(N+3),
        candidate_cycles=(102+done+2+10*N+4)+(3+7*interval+done+2+10*N+4),
        fifo_peak=4, full_exchanges=3, backpressure_edges=3*interval-4)


def config(): return dict(aw=16,p=16,base=BASE,epoch_seed=SEED,mode='normal',**FLAGS)


def validate(stdout, stderr, returncode, config, assets):
    need(type(config) is dict and config == globals()['config']() and
         all(type(config[k]) is int for k in ('aw','p','base','epoch_seed',*FLAGS)) and assets == {}, 'CONFIG')
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int, 'OUTPUT_TYPES')
    prefix='S4_P16_DIET_HOST_PASS aw=16 p=16 '+' '.join(f'{key}={value}' for key,value in counts().items())+' t5b_wait_edges='
    match = re.fullmatch(re.escape(prefix)+r'([1-9][0-9]*)\n', stdout, re.ASCII)
    need(returncode == 0 and stderr == '' and bool(match), 'TYPED_NORMAL')
    wait = int(match.group(1));need(9 <= wait <= 9*(20*N+100000), 'T5B_BOUND')
    return dict(status='PASS_expected_contracts',counts=counts(),measured_t5b_wait_edges=wait,
        flags=FLAGS,geometry=GEOMETRY,promotion_allowed=False,
        scope='Actual wholeP16 C1 dense legacy1 plus dependentfeed8, 2N signed96 T5b/reference reads; no PRP/1000/resource/clock/promotion inference.')


def bench_source():
    need(sha((ROOT/OLD_CPP).read_bytes()) == PINS[OLD_CPP], 'FROZEN_BENCH')
    text = (ROOT/OLD_CPP).read_text()
    replacements = [('AW==16 && P==8 && N==65536','AW==16 && P==16 && N==65536',1),
        ('isolated exact full-N P8 host gate','isolated exact full-N composed-diet P16 host gate',1),
        ('(special?7u:6u)','(special?10u:9u)',2),('c.canonical==12*N','c.canonical==18*N',1),
        ('S4_FULL_HOST_PASS aw=16 p=8','S4_P16_DIET_HOST_PASS aw=16 p=16',1)]
    for before,after,count in replacements:
        need(text.count(before)==count, 'BENCH_ANCHOR:'+before);text=text.replace(before,after)
    return text


def role():
    from fpga.reference import stream27_host_chain_diet as core
    for name,pin in PINS.items():need(sha((ROOT/name).read_bytes())==pin,'REFERENCE_PIN:'+name)
    kwargs=dict(contexts=1,allow_full_constants=True,canonical_pipe_stages=1,
        corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
    b=core.prepare(N,P,paired=True,**kwargs)
    standalone=core.prepare(N,P,paired=False,**kwargs)
    need(all(b['files'].get(name)==text for name,text in standalone['files'].items()), 'PAIR_STANDALONE_JOIN')
    need(all(b['geometry'][key]==value for key,value in GEOMETRY.items()), 'GEOMETRY')
    files={'rtl/'+name:text.encode() for name,text in b['files'].items()}
    files[CPP]=bench_source().encode()
    for name in (REFERENCE,NTT,SELF,TEST):files[name]=(ROOT/name).read_bytes()
    files[HEADER]=f'''#include <cstdint>
#include "V{b['top']}.h"
using DUT=V{b['top']};
constexpr unsigned AW=16,P=16,N=65536,BASE={BASE};
constexpr uint64_t FIRST_DIGIT=8458,INTERVAL=8459,CARRY_DONE=12557,EXPECTED_CYCLES={counts()['candidate_cycles']},T5B_WAIT_LIMIT=20*N+100000;
'''.encode()
    for name in dict.fromkeys(b['source_dependencies']+list(PINS)):
        files['lineage/'+name]=(ROOT/name).read_bytes()
    parameters=dict(AW=16,P=16,CONTEXTS=1,EPOCH_SEED=SEED,**FLAGS)
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/p16-diet/fpga',output_parent='/not-a-dispatch-path/p16-diet/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=CPP,
            parameters=parameters,cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='p16-diet-whole-full9-normal',argv=['{exe}'],expected_returncode=0,
            validator=dict(source=SELF,function='validate',config=config(),assets={}))],
        full_host=dict(base=BASE,epoch_seed=SEED,counts=counts(),geometry=b['geometry'],flags=FLAGS,
            host_contract=b['host_contract'],cycle_contract=b['cycle_contract'],diet_binding=b['diet_binding'],
            generated_sha256=b['generated_sha256'],source_sha256=b['source_sha256'],
            standalone_top=standalone['top'],standalone_generated_sha256=standalone['generated_sha256'],
            candidate_root_sha256=sha(standalone['files'][standalone['top']+'.sv'].encode()),
            dense_input='xorshift32 seed0x9135ba27 modulo604832956; signed-1 at17/N-1',
            jobs=[dict(kind='legacy',count=1,bits=[0]),dict(kind='dependent_feed',count=8,bits=[0,1,0,1,1,0,1,0],reload=False)],
            oracle='Frozen independent threeprime iterative NTT/centered128 CRT/serial Euclidean carry; native bounded schoolbook selfcheck; actual paired T5b.',
            copied_words='Footer aliases successful paired reads; real N-copy completion asserted separately in RTL/C++.',
            standalone_raw_array_dump=False,full_N_numeric_locally_performed=False,native_executed=False,
            author_not_independent_reviewer=True,whole_resources_measured=False,promotion_allowed=False))
    return m,files,standalone


def prepare(output):
    need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')), 'PAUSE')
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_OWNED_OUTPUT')
    m,files,standalone=role()
    out.mkdir(parents=True);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    manifest=out/'manifest.json';manifest.write_text(json.dumps(m,indent=2)+'\n')
    now=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    plan=dict(schema='gfn16-candidate-ladder-v1',candidate_id=CANDIDATE,owner='independent-review',track='S',
        flags=dict(CANONICAL_PIPE_STAGES=1),roles=[dict(id=IDENTIFIER,stage='aw16',test_role='normal',
            manifest=dict(path=str(manifest),sha256=sha(manifest.read_bytes())),source_root=str(source),
            resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
            priority='P1',after=[],est_minutes=25)],
        composed_source_flags=FLAGS,rtl_completed_at_utc=now,
        scope='Normal-first actual whole source; resource screen is synthesis-only and separately queued, not whole-fit GO.')
    (out/'candidate.json').write_text(json.dumps(plan,indent=2)+'\n')
    return dict(status='RTL_ready_normal_not_yet_submitted',candidate=plan['candidate_id'],
        manifest_sha256=sha(manifest.read_bytes()),source_members=len(files),rtl_members=len(m['build']['sv_sources']),
        standalone_rtl_members=len(standalone['rtl_sources']),candidate_cycles=counts()['candidate_cycles'],
        rtl_completed_at_utc=now,native_executed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(parser.parse_args().output),indent=2))
