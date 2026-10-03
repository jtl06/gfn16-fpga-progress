"""Separate full-size output-word cross-talk detector, not production mutation."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_storage_combo_crosstalk.py'
CPP='rtl/tb/stream27_p16_two_context_crosstalk.cpp'
HEADER='rtl/tb/s4_p16_two_context_full_config.h'
TOP='genefer_stream27_combo_crosstalk_observer_v1'
READY='2026-10-02T09:49:14Z'
BASES=[604832956,999999937]
def need(ok,why):
    if not ok:raise ValueError('R84_CROSSTALK_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,v):
    with Path(path).open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def config():return dict(aw=16,p=16,contexts=2,bases=BASES,address=17,mutation='native-output-word-bit0-context0')
def validate(stdout,stderr,rc,config,assets):
    need(config==globals()['config']() and assets=={},'CONFIG')
    need(type(rc) is int and rc==0 and stderr=='' and stdout.startswith('R84_C2_CROSSTALK_PASS '),'TYPED_OUTPUT')
    v=json.loads(stdout.removeprefix('R84_C2_CROSSTALK_PASS '))
    expected=dict(aw=16,p=16,contexts=2,bases=BASES,squares=4,peer_verified_words=65536,
        mutated_context=0,mutated_address=17,typed_mismatches=1,signed96=True,peer_bit_identical=True,
        metadata_unchanged=True,native_output_word_only=True,model_threads=1)
    need(set(v)==set(expected)|{'seconds'} and all(v[k]==x and type(v[k]) is type(x) for k,x in expected.items()),'EXACT_MUTANT_PEER_CONTRACT')
    need(stdout.endswith('\n') and '\n' not in stdout[:-1] and type(v['seconds']) in (int,float)
        and math.isfinite(v['seconds']) and 0<v['seconds']<3700,'BOUNDED_ONE_FOOTER')
    return dict(status='PASS_expected_contracts',measurements=v,promotion_allowed=False,
        scope='One native-only output-word mutation detected by unchanged full reference, peer all65536 words unchanged; not a production RAM/configuration fault or whole qualification.')

def role():
    from fpga.reference import stream27_context_storage_combo_native as normal
    m,files,bundle=normal.role('full');oldtop=m['build']['top'];old='rtl/'+oldtop+'.sv';text=files.pop(old).decode()
    root=m['r84']['native_observer']['production_top']
    sites=[('module '+oldtop+' #(','module '+TOP+' #('),
        (' output logic dbg_setup_done,dbg_setup_context,',' input logic mutant_enable,\n output logic dbg_setup_done,dbg_setup_context,'),
        ('\n '+root+' #(\n','\n wire [95:0] native_read_data;\n '+root+' #(\n'),
        (' ) candidate (.*);',' ) candidate (.read_data(native_read_data), .*);'),
        ('endmodule\n'," assign read_data=(mutant_enable && read_valid && !host_context && host_addr==16'd17) ? (native_read_data ^ 96'd1) : native_read_data;\nendmodule\n")]
    for a,b in sites:need(text.count(a)==1,'EXACT_OBSERVER_SITE');text=text.replace(a,b,1)
    need(not re.search(r'\b(always|always_ff|always_comb|initial)\b',text),'NO_STATE_OR_LATENCY')
    new='rtl/'+TOP+'.sv';files[new]=text.encode()
    header=files[HEADER].decode();need(header.count(oldtop)==2,'EXACT_NATIVE_MODEL_HEADER')
    files[HEADER]=header.replace(oldtop,TOP).encode()
    files[CPP]=(ROOT/CPP).read_bytes();files[SELF]=(ROOT/SELF).read_bytes()
    m['build']['top']=TOP;m['build']['cpp_source']=CPP
    m['build']['sv_sources']=[new if name==old else name for name in m['build']['sv_sources']]
    m['sources']={name:sha(raw) for name,raw in files.items()}
    m['steps']=[dict(name='deliberate-full-c2-single-word-crosstalk',argv=['{exe}'],expected_returncode=0,
        validator=dict(source=SELF,function='validate',config=config(),assets={}))]
    m['test_role']='deliberate_fault';m['r84']['mutation']=config()['mutation']
    m['r84']['comparison']='Joint SAME CONTEXTS2 run against independent reference; full peer image checked while native-only word mutation armed.'
    m['r84']['native_observer']['mutation_added_edges']=0
    snapshot={name:sha(raw) for name,raw in files.items() if name.endswith('.sv')}
    m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-p16-c2-combo-full-crosstalk-v1',
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=READY)
    return m,files

def prepare(output,budget):
    from fpga.tools import native_class_package_v2 as package
    need(READY!='SOURCE_NOT_YET_FROZEN','SOURCE_FREEZE_REQUIRED')
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_OUTPUT')
    need(not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE','queue/PAUSE')),'PAUSE')
    m,files=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    manifest=out/'manifest.json';dump(manifest,m);variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-combo-crosstalk-'+pair+'-v1';packet=out/('packet-'+pair)
        r=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=r['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes())) for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    q=dict(schema='gfn16-global-ticket-v1',id='s4-p16-c2-combo-crosstalk-q1-v1',owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Bounded exploratory4GiB word mutant after own combined full normal; stateless native-only observer, desiredGCP8 retained; resource failures preserved.',
        est_minutes=20,promotion_bound=False,test_role='deliberate_fault',rtl_readiness=m['rtl_readiness'],packages=variants,allowed_hosts=['gfn16-pilot-c4d','aethia'],
        after=['s4-p16-c2-combo-full-normal-q1-v1'],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',q)
    return dict(id=q['id'],ticket=str(out/'global-ticket.json'),compiled_rtl=len(m['build']['sv_sources']),status='prepared_not_native')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.budget),indent=2))
