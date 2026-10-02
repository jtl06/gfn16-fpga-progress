"""R84 full-N normal-first SAME-C2 context-alone/joint host qualification.

Only source/constants/calendar emission locally. Full-N NTT, real host RAM,
canonicalization and all signed96 comparisons execute on admitted workers.
Native-only transparent observations prove distinct profile snapshots; they
are not a production wrapper, a separate C1 pairing, or whole-fit evidence.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_tagcompact_native.py'
CPP='rtl/tb/stream27_p16_two_context_full_native.cpp'
HEADER='rtl/tb/s4_p16_two_context_full_config.h'
API='reference/stream27_host_contexts.py'
API_PIN='8e262811f2a6d296ef55530a2c67adde7fcd632bf87c8e4f6700782994182290'
NETS='reference/stream27_contexts_explicit_nets.py'
REFERENCE='rtl/tb/stream27_host_chain_full_reference_v1.h'
NTT='rtl/tb/stream27_shared_reference_ntt_v1.h'
PINS={REFERENCE:'88849a77ad7c58fc99f6d56eeded2a772a78fbe2b2da03fabdf7ac71aaf12c54',
    NTT:'c7837ba92829293131efda704dfdde347708641bf9aff46dccbcb87b825ba390',API:API_PIN,
    NETS:'861d6d1e795c8177b93305df75021f5fc40364c880d40cba863222b08bbd588a'}
FLAGS=dict(corr_serial_bfs=2,mont_factored=1,cold_launch_fence=1,ram_closure=1,explicit_net_declarations=1,comm_tag_compact=1)
BASES=[604832956,999999937]
COUNT=2
ROOT_PIN='cb734faeef4ebe4e95d8a6924e8467253d66e686a0aaa5ec13b2c2cca8bd9e3b'
TOP='genefer_stream27_p16_c2_full_observer_v1'
NATIVE_READY='2026-10-02T04:07:49Z'
def need(ok,why):
    if not ok:raise ValueError('R84_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def dump(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')

def observed(bundle):
    """Read-only native wrapper; no added state, production bytes unchanged."""
    b=dict(bundle);b['files']=dict(bundle['files']);b['rtl_sources']=list(bundle['rtl_sources'])
    b['generated_sha256']=dict(bundle['generated_sha256'])
    old=b['top'];text=b['files'][old+'.sv'];begin=text.index('module '+old+' #(');end=text.index(');',begin)+2
    header=text[begin:end];parameters=re.findall(r'\b([A-Z][A-Z0-9_]*)=\d+',header)
    need(len(parameters)==len(set(parameters)) and set(parameters)==set(b['parameters'])|{'EPOCH_SEED0','EPOCH_SEED1'},'OBSERVER_PARAMETER_JOIN')
    head=header.replace('module '+old+' #(','module '+TOP+' #(',1)
    head=head[:-2]+',\n output logic dbg_setup_done,dbg_setup_context,\n output logic [1:0] dbg_config_valid,\n output logic [63:0] dbg_base,\n output logic [191:0] dbg_reciprocal,\n output logic [153:0] dbg_limit,\n output logic [15:0] dbg_generation\n);'
    wrapper=head+'\n '+old+' #(\n  '+',\n  '.join('.'+n+'('+n+')' for n in parameters)+'\n ) candidate (.*);\n'
    wrapper+=' assign dbg_setup_done=candidate.setup_done;\n assign dbg_setup_context=candidate.setup_done_context;\n assign dbg_config_valid=candidate.config_valid;\n'
    for port,name in [('dbg_base','profile_base'),('dbg_reciprocal','profile_reciprocal'),('dbg_limit','profile_limit'),('dbg_generation','profile_generation')]:
        wrapper+=f' assign {port}={{candidate.engine.arithmetic.{name}[1],candidate.engine.arithmetic.{name}[0]}};\n'
    wrapper+='endmodule\n'
    need(not re.search(r'\b(always|always_ff|always_comb|initial)\b',wrapper),'OBSERVER_NO_ADDED_STATE')
    need(all(b['files'][n]==v for n,v in bundle['files'].items()),'OBSERVER_PRODUCTION_BYTES')
    b['files'][TOP+'.sv']=wrapper;b['top']=TOP;b['rtl_sources'].append(TOP+'.sv');b['generated_sha256'][TOP+'.sv']=sha(wrapper.encode())
    b['native_observer']=dict(production_top=old,production_root_sha256=sha(text.encode()),added_edges=0,
        source_selection_or_arithmetic_changed=False,scope='Native-only exact host ABI plus read-only setup/profile snapshots, never fitted.')
    return b

def config():return dict(aw=16,p=16,contexts=2,bases=BASES,count=2,interval=8459)
def validate(stdout,stderr,rc,config,assets):
    need(config==globals()['config']() and assets=={},'CONFIG')
    need(type(rc) is int and rc==0 and stderr=='' and stdout.startswith('R84_C2_FULL_PASS '),'NORMAL_OUTPUT')
    v=json.loads(stdout.removeprefix('R84_C2_FULL_PASS '));need(stdout.endswith('\n') and '\n' not in stdout[:-1],'ONE_FOOTER')
    expected=dict(aw=16,p=16,contexts=2,bases=BASES,squares=8,reads=6*65536,signed96=True,
        context_alone_bit_identical=True,independent_reference=True,interval=8459,pair_launch_cycles=8459,
        peer_live_reads=65536,model_threads=1)
    need(set(v)==set(expected)|{'launches','single_cycles','joint_cycles','overlap_edges','done_edges','warm_edges','setup_edges','single_first','seconds'},'FOOTER_KEYS')
    need(all(v[k]==x and type(v[k]) is type(x) for k,x in expected.items()),'EXACT_COUNTS')
    for name in ('single_cycles','done_edges','warm_edges','setup_edges','single_first'):
        need(type(v[name]) is list and len(v[name])==2 and all(type(x) is int and x>0 for x in v[name]),'MEASURED_EDGE_VECTOR')
    need(type(v['launches']) is list and len(v['launches'])==2 and all(type(row) is list and len(row)==2 and all(type(x) is int and x>0 for x in row) for row in v['launches']),'MEASURED_FIRST_EDGES')
    a,b=v['launches'];need(a[1]-a[0]==8459 and b[1]-b[0]==8459 and b[0]-a[0]==4229 and a[1]-b[0]==4230,'EXACT_PAIR_CALENDAR')
    need(all(v['warm_edges'][c]==v['launches'][c][1]+12557+1 and v['setup_edges'][c]<v['launches'][c][0]
        and v['done_edges'][c]>v['warm_edges'][c]+10*65536 for c in range(2)),'WARM_SETUP_PUBLICATION_SEAMS')
    need(type(v['joint_cycles']) is int and v['joint_cycles']>=max(v['done_edges'])+65536 and v['joint_cycles']<3*11*65536+100000,'JOINT_BOUND')
    need(type(v['overlap_edges']) is int and v['overlap_edges']>0 and type(v['seconds']) in (int,float) and math.isfinite(v['seconds']) and 0<v['seconds']<3700,'MEASURED_NORMAL_SCOPE')
    return dict(status='PASS_expected_contracts',measurements=v,promotion_allowed=False,
        scope='SameC2 single-active runs versus joint and independent native reference; no separateC1-source pairing, long chain, wholeclock/memory/fit qualification.')

def role():
    from fpga.reference import stream27_host_contexts as core
    for name,pin in PINS.items():need(sha((ROOT/name).read_bytes())==pin,'FROZEN_PIN '+name)
    production=core.prepare(65536,16,contexts=2,allow_full_constants=True,**FLAGS)
    need(production['generated_sha256'][production['top']+'.sv']==ROOT_PIN,'EXACT_FULL_PRODUCTION_ROOT')
    g=production['geometry'];need([g[k] for k in ('rows','first_digit','carry_done','warm_interval')]==[4096,8458,12557,8459],'FULL_CALENDAR')
    b=observed(production)
    header=f'''#include <algorithm>
#include <cstdint>
#include "V{b['top']}.h"
using DUT=V{b['top']};
constexpr unsigned AW=16,P=16,N=65536,T=N/P,COUNT=2,INTERVAL=8459,FIRST_DIGIT=8458,CARRY_DONE=12557;
constexpr uint64_t MAX_EDGES=3*11ull*N+100000;
constexpr uint32_t BASES[2]={{604832956,999999937}},SEEDS[2]={{0x9135ba27u,0x6a09e667u}};
constexpr unsigned EPOCHS[2]={{65534,42}},BITS[2][2]={{{{0,1}},{{1,0}}}};
'''
    files={'rtl/'+n:t.encode() for n,t in b['files'].items()}
    files.update({CPP:(ROOT/CPP).read_bytes(),HEADER:header.encode(),REFERENCE:(ROOT/REFERENCE).read_bytes(),NTT:(ROOT/NTT).read_bytes(),
        SELF:(ROOT/SELF).read_bytes(),'rtl/tb/native_runtime_context_v1.h':(ROOT/'rtl/tb/native_runtime_context_v1.h').read_bytes()})
    for name in production['source_dependencies']:files['lineage/'+name]=(ROOT/name).read_bytes()
    snapshot={n:sha(raw) for n,raw in files.items() if n.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-p16-c2-tagcompact-full-normal-v1',
        source_snapshot=snapshot,candidate_source_sha256=sha(canonical(snapshot)),rtl_ready_at_utc=NATIVE_READY)
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
        sources={n:sha(raw) for n,raw in files.items()},
        build=dict(top=b['top'],sv_sources=['rtl/'+n for n in b['rtl_sources']],cpp_source=CPP,
            parameters=dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),cflags=['-std=c++17','-O2','-Werror=return-type'],runtime_threads=1),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='normal-full-c2-two-bases-context-alone-and-joint',argv=['{exe}'],expected_returncode=0,
            validator=dict(source=SELF,function='validate',config=config(),assets={}))],
        test_role='normal',rtl_readiness=readiness,r84=dict(flags=FLAGS,geometry=g,native_observer=b['native_observer'],
            explicit_net_declarations=production['explicit_net_declarations'],
            parameters=b['parameters'],production_generated_sha256=production['generated_sha256'],production_source_sha256=production['source_sha256'],
            profiles='Actual base32/reciprocal96/limit77/gen8 captured at addressed E98 context; read-only native snapshot checks.',
            comparison='Context0-alone/context1-alone/joint SAME CONTEXTS2 productionRTL, not a distinct CONTEXTS1 DUT.',
            independent_reference='Frozen native threeprime iterative NTT, centered128CRT, direct integer carry/mod b^N+1; smallschoolbook/wholeinteger selfcheck.',
            full_N_numeric_locally_performed=False,whole_memory_or_fit_claim=False,promotion_allowed=False))
    from fpga.tools.native_source_gate_v1 import expand
    for step in [m['probe']]+m['steps']:expand(step['argv'],Path('/exe'),Path('/root'))
    return m,files

def small_role():
    """Unchanged admitted N256/P16 host corpus on the corrected source only."""
    from fpga.reference import stream27_host_contexts as core
    from fpga.reference import stream27_host_contexts_native as donor
    for name,pin in PINS.items():need(sha((ROOT/name).read_bytes())==pin,'FROZEN_PIN '+name)
    m,files=donor.role(p=16,diet=True,n=256,counts=(3,14));old=m['build']['top']
    b=core.prepare(256,16,contexts=2,**FLAGS)
    for name in m['build']['sv_sources']:files.pop(name)
    files.update({'rtl/'+n:t.encode() for n,t in b['files'].items()})
    header=files[donor.HEADER].decode();need(header.count(old)==2,'SMALL_MODEL_HEADER')
    files[donor.HEADER]=header.replace(old,b['top']).encode();files[SELF]=(ROOT/SELF).read_bytes()
    for name in b['source_dependencies']:files['lineage/'+name]=(ROOT/name).read_bytes()
    m['build'].update(top=b['top'],sv_sources=['rtl/'+n for n in b['rtl_sources']],parameters=dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42))
    m['host_contexts'].update(geometry=b['geometry'],generated_sha256=b['generated_sha256'],source_sha256=b['source_sha256'])
    m['sources']={n:sha(raw) for n,raw in files.items()}
    snapshot={n:sha(raw) for n,raw in files.items() if n.endswith('.sv')}
    m['test_role']='normal';m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',
        candidate_id='s4-p16-c2-tagcompact-aw8-normal-v1',source_snapshot=snapshot,
        candidate_source_sha256=sha(canonical(snapshot)),rtl_ready_at_utc=NATIVE_READY)
    m['r84_explicit_small']=dict(geometry=b['geometry'],flags=FLAGS,parameters=b['parameters'],
        generated_sha256=b['generated_sha256'],source_sha256=b['source_sha256'],explicit_net_declarations=b['explicit_net_declarations'],
        old_source_native_PASS_inherited=False,full_N_numeric_locally_performed=False,promotion_allowed=False)
    return m,files

def prepare(output,budget,stage='full'):
    from fpga.tools import native_class_package_v2 as package
    need(NATIVE_READY!='SOURCE_NOT_YET_FROZEN','ACTUAL_NATIVE_SOURCE_FREEZE_REQUIRED')
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_OUTPUT')
    need(not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE','queue/PAUSE')),'PAUSE')
    need(stage in ('aw8','full'),'EXPLICIT_NORMAL_STAGE')
    m,files=small_role() if stage=='aw8' else role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=out/'manifest.json';dump(manifest,m);variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-tagcompact-'+stage+'-normal-'+pair+'-v1';packet=out/('packet-'+pair)
        result=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve());ticket=json.loads((packet/'ticket.json').read_text())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=result['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/name),sha256=sha((ROOT/name).read_bytes())) for name in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    qid='s4-p16-c2-tagcompact-'+stage+'-normal-q1-v1'
    logical=dict(schema='gfn16-global-ticket-v1',id=qid,owner='ram27-recovery',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
        minimum_ram_rationale='Existing fullN8GiB bounded exploratory normal; no measured C2 peak inherited.',
        est_minutes=25,promotion_bound=False,test_role='normal',rtl_readiness=m['rtl_readiness'],packages=variants)
    if stage=='full':logical.update(after=['s4-p16-c2-tagcompact-aw8-normal-q1-v1'],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical)
    return dict(id=qid,ticket=str(out/'global-ticket.json'),compiled_rtl=len(m['build']['sv_sources']),status='normal_prepared_not_native')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True)
    p.add_argument('--stage',choices=('aw8','full'),default='full')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.budget,a.stage),indent=2))

