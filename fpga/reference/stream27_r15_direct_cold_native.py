"""AUTHOR N256 direct-wrapper healthy normal; actual guarded load and original compute.

Captured FIELD100 reference vectors/healthy calendar are inputs, never inherited
execution. New63 production source and one fresh Azure-native result required.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from . import stream27_r15_direct_cold_bind_v2 as binder
from . import stream27_r15_direct_write_native as packet_base

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_direct_cold_native.py'
BASE=ROOT/'results/throughput-20260929/trackS-r15-direct-cold-native-v1'
DONOR=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1/aw8-normal'
BINDER='reference/stream27_r15_direct_cold_bind_v2.py'
PIN='2158f682a0437b6f4697ab70ea312dd1b673b00a75802e27cfecbdd1dfd6f811'
LOADER='rtl/kernel/genefer_stream27_r15_raw_loader_v1.sv'
LOADER_PIN='007218786058ccacabed012238076ec684c834c4cc78f54f42c7c4f7450cb686'
INC='rtl/tb/stream27_r15_direct_cold_load.inc'
FAULT='rtl/tb/stream27_r15_direct_cold_fault.inc'
CPP='rtl/tb/stream27_r15_direct_cold.cpp'
ID='s4-r15-direct-cold-aw8-normal-q1-v2'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,why):
    if not ok:raise ValueError('R15_DIRECT_NATIVE_'+why)
def once(text,old,new):
    need(text.count(old)==1,'ONE_ANCHOR:'+old[:55]);return text.replace(old,new,1)
def dump(path,obj):
    with Path(path).open('x') as f:json.dump(obj,f,indent=2);f.write('\n')

def role(mode='normal'):
    need(mode in ('normal','fault'),'MODE')
    need(sha((ROOT/BINDER).read_bytes())==PIN and sha((ROOT/LOADER).read_bytes())==LOADER_PIN,'FROZEN_BINDER_LOADER')
    m=json.loads((DONOR/'manifest.json').read_bytes());parent=json.loads((DONOR/'production-bundle.json').read_bytes())
    source=Path(m['source_root']);files={p:(source/p).read_bytes() for p in m['sources']}
    need(all(sha(raw)==m['sources'][p] for p,raw in files.items()),'EXACT_DONOR_CAPTURE')
    production=binder.bind(parent,direct_cold=1,pcie_shell=0)
    need(len(production['files'])==63 and production['geometry']==parent['geometry'],'OWN_63_GEOMETRY')
    need(binder.bind(parent,direct_cold=0,pcie_shell=0)==parent,'DEFAULT_LITERAL')
    for n in parent['files']:files.pop('rtl/'+n)
    files.update({'rtl/'+n:t.encode() for n,t in production['files'].items()})
    header='rtl/tb/s4_host_contexts_config_v1.h';text=files[header].decode()
    need(text.count(parent['top'])==2,'DONOR_HEADER_TOP');files[header]=text.replace(parent['top'],production['top']).encode()
    oldcpp=m['build']['cpp_source'];text=files.pop(oldcpp).decode()
    text=once(text,'#include <array>','#include <array>\n#include <filesystem>')
    text=once(text,'static void clear(DUT& d){','static void clear(DUT& d){d.dc_begin=d.dc_cancel=d.dc_commit=d.dc_word_valid=0;')
    text=once(text,'static void run(DUT& d){',(ROOT/INC).read_text()+'\nstatic void run(DUT& d){')
    text=once(text,'    clear(d);d.clk=0;d.rst_n=0;',
        '    clear(d);d.dc_link_drained=0;d.dc_current_session=77;d.dc_transport_empty=1;d.clk=0;d.rst_n=0;')
    load='    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned address=0;address<N;address++){clear(d);d.host_context=ctx;d.host_addr=address;d.load_we=1;d.write_data=INITIAL[ctx][address];edge(d);need(!d.error&&!d.read_valid&&!d.canonical_ready,"S4_HOST_CONTEXT_COLD_LOAD");}'
    text=once(text,load,'    direct_load(d);')
    text=text.replace('S4_HOST_CONTEXTS_PASS','R15_DIRECT_COLD_HOST_PASS')
    text=once(text,'DUT d(&context);','DUT d(&context);unsigned os_threads=0;for(auto const& t:std::filesystem::directory_iterator("/proc/self/task")){(void)t;os_threads++;}need(os_threads==1,"R15_RUNTIME_OS_THREADS");')
    if mode=='fault':
        text=once(text,'static void run(DUT& d){',(ROOT/FAULT).read_text()+'\nstatic void run(DUT& d){')
        text=once(text,'run(d);return 0;','direct_faults(d);run(d);return 0;')
    files[CPP]=text.encode()
    for name,pin in production['source_sha256'].items():
        raw=(ROOT/name).read_bytes();need(sha(raw)==pin,'LINEAGE:'+name);files['lineage/'+name]=raw
    for name in (SELF,INC)+((FAULT,) if mode=='fault' else ()):files[name]=(ROOT/name).read_bytes()
    files['lineage/FIELD100-normal-manifest.json']=(DONOR/'manifest.json').read_bytes()
    files['lineage/FIELD100-production-bundle.json']=(DONOR/'production-bundle.json').read_bytes()
    m['build'].update(top=production['top'],sv_sources=['rtl/'+n for n in production['rtl_sources']],cpp_source=CPP,
                      parameters=dict(production['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),runtime_threads=1)
    m['steps'][0]['expected_stdout']=m['steps'][0]['expected_stdout'].replace('S4_HOST_CONTEXTS_PASS','R15_DIRECT_COLD_HOST_PASS')
    m['steps'][0]['name']='direct-lease-commit-original-start-canonical96'
    if mode=='fault':
        m['steps'][0]['name']='direct-wrapper-fault-reset-then-reference-recovery'
        m['steps'][0]['expected_stdout']='R15_DIRECT_COLD_FAULT_PASS cases=10 reset_pending_ack=1 recovery_normal_follows=1\n'+m['steps'][0]['expected_stdout']
    m.update(source_root='UNBOUND',output_parent='UNBOUND',sources={p:sha(b) for p,b in files.items()},test_role='normal' if mode=='normal' else 'deliberate_fault')
    snap={p:sha(raw) for p,raw in files.items() if p.startswith('rtl/') and p.endswith('.sv')}
    m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-r15-direct-cold-aw8-v1',source_snapshot=snap,
         candidate_source_sha256=sha(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    m['r15_direct_native']=dict(production_top=production['top'],production_generated_sha256=production['generated_sha256'],
        binder_sha256=PIN,loader_sha256=LOADER_PIN,body_words_per_context=256,correction_words_per_context=32,
        actual_lease_guard_commit=True,legacy_load_bypass=False,profile_setup_after_start=True,canonical96_readback=True,
        reference_vectors='exact captured FIELD100 N256 independent-reference values, not inherited native PASS',
        pcie=False,cdc=False,host_GL=False,whole_physical=False,author='ram27_recovery',independent_review=False,
        fixture_version=2,prior_fixture='v1 retained: incorrect 32-bit observation of packed16-bit epochs; production unchanged')
    return m,files,production

def prepare(output,mode='normal'):
    out=Path(output).resolve();need(out.is_relative_to(BASE) and not out.exists(),'FRESH_OUTPUT')
    m,files,b=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    m['source_root']=str(source);dump(out/'manifest.json',m);dump(out/'production-bundle.json',b)
    return dict(id=ID if mode=='normal' else ID.replace('-normal-','-fault-'),manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_NATIVE')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=('normal','fault'),default='normal');a=p.parse_args()
    print(json.dumps(prepare(a.output,a.mode),indent=2))
