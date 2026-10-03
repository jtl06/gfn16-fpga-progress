"""Fresh application-v4/endpoint-v8 normals on the literal DIRECT65.

Old failed application-v2 gates and cancelled full remain untouched. Reuses
only frozen healthy bus-driver/reference assertions, not native outcomes.
"""
import argparse
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump,runtime_before_model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_shell_application_v4_native.py'
BINDER='reference/stream27_r15_pcie_application_bind_v4.py'
BINDER_PIN='b540a3f28168054c1db1eb0e7624b2a5c9cd20b72859a205acbe1751122ade38'
READY='2026-10-03T12:12:31Z'
BASE=ROOT/'results/throughput-20260929'
ROLES={
 'aw8':dict(capture='trackS-r15-shell-application-native-v2/aw8-normal-v3',
   pin='6c4d230dfef7a08992e53739035e0297c14ed5cfbd40079e1d01341a6a9397fa',n=256,
   top='genefer_stream27_r15_application_aw8_observer_v4',header='rtl/tb/s4_host_contexts_config_v1.h',
   id='s4-p16-c2-r15-shell-application-aw8-normal-q1-v4'),
 'full':dict(capture='trackS-r15-shell-application-native-v2/full-normal-v5',
   pin='08bbe0aa038d117fd86a30ce72e54749ef129323417173dfde8e7d1e2838edc0',n=65536,
   top='genefer_stream27_r15_application_full_observer_v4',header='rtl/tb/s4_p16_two_context_full_config.h',
   id='s4-p16-c2-r15-shell-application-full-normal-q1-v6'),
}
FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=1,PCIE_SHELL=1)
FOOTERS={
 'aw8':'R15_APPLICATION_PASS aw=8 contexts=2 squares=17 signed96_words=1024 cold_records=576 interval=215 first=204/311 core_publication=1 live_core_cdc=1 mmio_data_a32=1 vendor_hip_simulated=0 host_gl=0\n',
 'full':'R15_APPLICATION_PASS aw=16 contexts=2 squares=4 signed96_words=262144 cold_records=131136 interval=8461 first=204/4434 core_publication=1 live_core_cdc=1 mmio_data_a32=1 vendor_hip_simulated=0 host_gl=0\n',
}


def config(stage):
    need(stage in ROLES,'R15_APP_V4_LITERAL_STAGE');full=stage=='full'
    return dict(stage=stage,aw=16 if full else 8,n=65536 if full else 256,p=16,contexts=2,
      counts=[2,2] if full else [3,14],epochs=[0,0] if full else [65534,42],
      interval=8461 if full else 215,first=[204,4434] if full else [204,311],
      r15_flags=FLAGS,application_version=4,endpoint_version=8,runtime_threads=1,
      pcie_core_clock_ratio=[3,1],external_fault_valid=0)


def validate(stdout,stderr,rc,config,assets):
    stage=config.get('stage');need(config==globals()['config'](stage) and assets=={},'R15_APP_V4_OWN_CONFIG')
    need(rc==0 and stderr=='' and stdout==FOOTERS[stage],'R15_APP_V4_OWN_ACTUAL_TERMINAL')
    full=stage=='full'
    return dict(status='PASS_expected_contracts',measurements=dict(squares=4 if full else 17,
      signed96_words=262144 if full else 1024,cold_records=131136 if full else 576,
      interval=config['interval'],first=config['first'],runtime_threads=1,actual_application_core_cdc=True,
      actual_mmio_data_a32=True,independent_reference=True),promotion_allowed=False,
      scope='Own application-v4/endpoint-v8 functional healthy normal. Lean build; host GL assumed (unimplemented). External pre-router fault pin driven0, so no guard/fault coverage; ideal clocks, not vendor HIP/PLL, metastability, board, clock or prior native credit. FULL explicitly matches physical epoch defaults0/0, transport costs not zero.')


def role(stage):
    from fpga.reference import stream27_r15_all_io_bind as direct,stream27_r15_pcie_application_bind_v4 as app
    need(stage in ROLES and sha((ROOT/BINDER).read_bytes())==BINDER_PIN,'R15_APP_V4_FROZEN_ENTRY')
    r=ROLES[stage];capture=BASE/r['capture'];raw=(capture/'manifest.json').read_bytes()
    need(sha(raw)==r['pin'],'R15_APP_V4_FROZEN_DRIVER_CAPTURE')
    m=json.loads(raw);parent=json.loads((capture/'production-bundle.json').read_bytes())
    f={n:(capture/'source/fpga'/n).read_bytes() for n in m['sources']}
    need(all(sha(f[n])==h for n,h in m['sources'].items()),'R15_APP_V4_DRIVER_SOURCE_CLOSURE')
    component=direct.prepare(r['n'],p=16,contexts=2,**{k.lower():v for k,v in FLAGS.items() if k!='PCIE_SHELL'},pcie_shell=0)
    b=app.application(component)
    need(len(b['files'])==70 and all(b['files'][n]==t for n,t in component['files'].items()) and
      b['r15_shell_application']['application_version']==4 and b['r15_shell_application']['endpoint_version']==8 and
      b['r15_shell_application']['explicit_unsigned_export_span_width']==32,'R15_APP_V4_LITERAL65_AND_WIDTH_SOURCE')
    for n in parent['files']:f.pop('rtl/'+n)
    f.update({'rtl/'+n:t.encode() for n,t in b['files'].items()})
    oldobs='rtl/'+m['build']['top']+'.sv';obs=f.pop(oldobs).decode()
    need(obs.count(parent['top'])==1 and obs.count('module '+m['build']['top'])==1,'R15_APP_V4_PASSIVE_OBSERVER_ABI')
    obs=obs.replace(parent['top'],b['top'],1).replace('module '+m['build']['top'],'module '+r['top'],1)
    marker=' output wire probe_error,probe_link_ready,'
    need(obs.count(marker)==1,'R15_APP_V4_NEW_PIN_OBSERVER_ABI')
    obs=obs.replace(marker,' input logic external_fault_valid,output wire external_fault_ready,\n'+marker,1)
    f['rtl/'+r['top']+'.sv']=obs.encode()
    header=f[r['header']].decode();need(header.count(m['build']['top'])==2,'R15_APP_V4_HEADER_DUT_ONLY')
    f[r['header']]=header.replace(m['build']['top'],r['top']).encode()
    cpp=f[m['build']['cpp_source']].decode();marker='static void run(DUT&d){'
    need(cpp.count(marker)==1,'R15_APP_V4_NORMAL_FAULT_PIN_INIT')
    cpp=cpp.replace(marker,marker+'\n d.external_fault_valid=0;',1);runtime_before_model(cpp)
    f[m['build']['cpp_source']]=cpp.encode();f[SELF]=(ROOT/SELF).read_bytes()
    for p,h in b['source_sha256'].items():
        value=(ROOT/p).read_bytes();need(sha(value)==h,'R15_APP_V4_LINEAGE:'+p);f['lineage/'+p]=value
    epochs=(0,0) if stage=='full' else (65534,42)
    m['build'].update(top=r['top'],sv_sources=['rtl/'+n for n in b['rtl_sources']]+['rtl/'+r['top']+'.sv'],
      parameters=dict(b['parameters'],EPOCH_SEED0=epochs[0],EPOCH_SEED1=epochs[1]),runtime_threads=1)
    m['steps']=[dict(name='normal-'+stage+'-r15-application-v4-core-cdc',argv=['{exe}'],expected_returncode=0,
      validator=dict(source=SELF,function='validate',config=config(stage),assets={}))]
    m['r15_shell_application_native']=dict(application_entry=BINDER,application_entry_sha256=BINDER_PIN,
      production_top=b['top'],production_generated_sha256=b['generated_sha256'],source_sha256=b['source_sha256'],
      production_sv=70,compiled_sv=71,component65_literal=True,previous_source_capture_sha256=r['pin'],
      assertions_reused_only=True,no_previous_native_result_credit=True,fixture_epochs=list(epochs),
      physical_epochs_match=stage=='full',external_fault_valid=0,pre_router_guard_not_exercised=True,
      vendor_simulated=False,host_GL_implemented=False,promotion_allowed=False)
    m['sources']={n:sha(v) for n,v in f.items()};snapshot={n:p for n,p in m['sources'].items() if n.endswith('.sv')}
    m.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',rtl_readiness=dict(
      schema='gfn16-candidate-rtl-ready-v1',candidate_id=r['id'].rsplit('-q1-',1)[0],source_snapshot=snapshot,
      candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=READY))
    return m,f,b,r


def freeze(stage):
    m,f,b,r=role(stage);out=BASE/'trackS-r15-shell-application-native-v4'/(stage+'-normal')
    need(not out.exists(),'R15_APP_V4_FRESH_ROLE');s=out/'source/fpga';s.mkdir(parents=True)
    for n,v in f.items():
        p=s/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(v)
    m['source_root']=str(s);dump(out/'manifest.json',m);dump(out/'production-bundle.json',b)
    return dict(id=r['id'],manifest=str(out/'manifest.json'),production_sv=70,compiled_sv=71,status='SOURCE_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=tuple(ROLES),required=True);a=p.parse_args()
    print(json.dumps(freeze(a.stage),indent=2))
