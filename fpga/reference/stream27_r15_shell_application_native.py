"""Own application-v2 functional normal: real DIRECT65, adapter, executor/CDC.

This is not vendor HIP/PLL simulation or a board/host-GL qualification. The
observer adds only wires; the driver uses actual Avalon acceptance/responses.
"""
import json
import re
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump,runtime_before_model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_shell_application_native.py'
CPP='rtl/tb/stream27_r15_shell_application.cpp'
HEADER='rtl/tb/s4_host_contexts_config_v1.h'
BINDER='reference/stream27_r15_pcie_application_bind_v2.py'
BINDER_PIN='708fc8c25166a5a03c77c748d5336b178bd7e15f0726549bba2eac5d82623f67'
READY='2026-10-03T11:13:56Z'
CAPTURE=ROOT/'results/throughput-20260929/trackS-r15-direct-compute-native-v1/aw8-normal'
CAPTURE_PIN='927cdf1a784a444f482cf316e840f7b8ab69dad63d47160fec29023bbe18e1e2'
ID='s4-p16-c2-r15-shell-application-aw8-normal-q1-v2'
TOP='genefer_stream27_r15_application_aw8_observer_v2'
OUT=ROOT/'results/throughput-20260929/trackS-r15-shell-application-native-v2/aw8-normal'
FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=1,PCIE_SHELL=1)
FOOTER='R15_APPLICATION_PASS aw=8 contexts=2 squares=17 signed96_words=1024 cold_records=576 interval=215 first=204/311 core_publication=1 live_core_cdc=1 mmio_data_a32=1 vendor_hip_simulated=0 host_gl=0\n'


def config():
    return dict(aw=8,n=256,p=16,contexts=2,counts=[3,14],epochs=[65534,42],
      interval=215,first=[204,311],r15_flags=FLAGS,application_version=2,
      endpoint_version=6,runtime_threads=1,pcie_core_clock_ratio=[3,1])


def validate(stdout,stderr,rc,config,assets):
    need(config==globals()['config']() and assets=={},'R15_APPLICATION_OWN_CONFIG')
    need(rc==0 and stderr=='' and stdout==FOOTER,'R15_APPLICATION_ACTUAL_NORMAL_TERMINAL')
    return dict(status='PASS_expected_contracts',measurements=dict(squares=17,signed96_words=1024,
      cold_records=576,interval=215,first=[204,311],runtime_threads=1,core_publication=True,
      actual_mmio_data_a32=True,actual_application_core_cdc=True),promotion_allowed=False,
      scope='Own application v2/endpoint v6 functional normal with literal DIRECT65. Lean build; host GL assumed (unimplemented). Ideal separate clocks, no vendor HIP/PLL execution, CDC metastability, hardware, clock or physical parameter equivalence claim.')


def observer(bundle):
    from fpga.reference.stream27_r15_pcie_application_bind_v1 import PORTS
    text=bundle['files'][bundle['top']+'.sv'];end=text.index(') (')
    header=text[:end+3].replace('module '+bundle['top']+' #(','module '+TOP+' #(',1)
    params=re.findall(r'\b([A-Z][A-Z0-9_]*)=\d+',header)
    need(len(params)==len(set(params)) and {'EPOCH_SEED0','EPOCH_SEED1','PCIE_SHELL'}<=set(params),
         'R15_APPLICATION_OBSERVER_ALL_PARAMETERS')
    header+=PORTS.rstrip()+',\n'+''' output wire probe_error,probe_link_ready,
 output wire [1:0] probe_start,probe_warm,probe_done,probe_ready,probe_busy,probe_waiting,
 output wire [63:0] probe_started,probe_completed,probe_rows,
 output wire [127:0] probe_canonical,probe_copy
);\n'''
    header+=' '+bundle['top']+' #('+','.join('.'+p+'('+p+')' for p in params)+') candidate(.*);\n'
    for key,signal in dict(error='core_error || candidate.transport_error || candidate.protocol_error || candidate.session_exhausted',
      link_ready='core_ready',start='compute.direct_cold.admitted_start',
      started='compute.operations_started',completed='compute.completed_squares',rows='compute.final_image_rows',
      warm='compute.warm_done',done='compute.done',ready='compute.canonical_ready',busy='compute.busy',
      waiting='compute.waiting_final',canonical='compute.canonical_cycles',copy='compute.image_copy_cycles').items():
        header+=' assign probe_'+key+'=candidate.'+signal+';\n'
    header+='endmodule\n'
    need(not re.search(r'\b(always|always_ff|always_comb|initial)\b',header),
         'R15_APPLICATION_STATELESS_OBSERVER')
    return header


def role():
    from fpga.reference import stream27_r15_all_io_bind as direct,stream27_r15_pcie_application_bind_v2 as app
    need(sha((ROOT/BINDER).read_bytes())==BINDER_PIN,'R15_APPLICATION_FROZEN_V2_ENTRY')
    raw=(CAPTURE/'manifest.json').read_bytes();need(sha(raw)==CAPTURE_PIN,'R15_APPLICATION_OWN_DIRECT_CAPTURE')
    manifest=json.loads(raw);parent=json.loads((CAPTURE/'production-bundle.json').read_bytes())
    files={n:(CAPTURE/'source/fpga'/n).read_bytes() for n in manifest['sources']}
    need(all(sha(files[n])==h for n,h in manifest['sources'].items()),'R15_APPLICATION_CAPTURE_CLOSURE')
    component=direct.prepare(256,p=16,contexts=2,**{k.lower():v for k,v in FLAGS.items() if k!='PCIE_SHELL'},pcie_shell=0)
    need(component['generated_sha256']==parent['generated_sha256'],'R15_APPLICATION_LITERAL_DIRECT65')
    bundle=app.application(component)
    need(len(bundle['files'])==70 and bundle['parameters']['PCIE_SHELL']==1 and
      bundle['r15_shell_application']['domain_reset_release_synchronized'] and
      bundle['r15_shell_application']['endpoint_version']==6,'R15_APPLICATION_V2_REAL_SOURCE70')
    need(all(bundle['files'][n]==t for n,t in component['files'].items()),'R15_APPLICATION_LITERAL_COMPONENT')
    for name in parent['files']:files.pop('rtl/'+name)
    files.update({'rtl/'+n:t.encode() for n,t in bundle['files'].items()})
    obs='rtl/'+TOP+'.sv';files[obs]=observer(bundle).encode()
    header=files[HEADER].decode();need(header.count(parent['top'])==2,'R15_APPLICATION_HEADER_CORPUS_TOP')
    files[HEADER]=header.replace(parent['top'],TOP).encode()
    cpp=(ROOT/CPP).read_bytes();runtime_before_model(cpp.decode());files[CPP]=cpp
    files[SELF]=(ROOT/SELF).read_bytes()
    for name,pin in bundle['source_sha256'].items():
        value=(ROOT/name).read_bytes();need(sha(value)==pin,'R15_APPLICATION_LINEAGE:'+name)
        files['lineage/'+name]=value
    manifest['build'].update(top=TOP,cpp_source=CPP,sv_sources=['rtl/'+n for n in bundle['rtl_sources']]+[obs],
      parameters=dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),runtime_threads=1)
    manifest['steps']=[dict(name='normal-aw8-r15-real-application-core-cdc',argv=['{exe}'],
      expected_returncode=0,validator=dict(source=SELF,function='validate',config=config(),assets={}))]
    manifest['r15_shell_application_native']=dict(application_entry=BINDER,application_entry_sha256=BINDER_PIN,
      production_top=bundle['top'],production_generated_sha256=bundle['generated_sha256'],
      source_sha256=bundle['source_sha256'],component_source_literal=True,production_sv=70,compiled_sv=71,
      stateless_observer=True,near_wrap_fixture_epochs=[65534,42],physical_default_epochs=[0,0],
      native_parameters_not_identical_to_physical_epochs=True,actual_mmio_data_a32=True,
      ideal_separate_clock_ratio=[3,1],transport_cost_not_assumed_zero=True,
      START_relative_core_calendar_reused_only=True,peer_live_read_count_not_inherited=True,
      vendor_HIP_PLL_simulated=False,host_GL_implemented=False,protection_credit=False,promotion_allowed=False)
    manifest['sources']={n:sha(v) for n,v in files.items()}
    snapshot={n:p for n,p in manifest['sources'].items() if n.endswith('.sv')}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=ID.removesuffix('-q1-v2'),
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=READY))
    return manifest,files,bundle


def freeze():
    manifest,files,bundle=role();need(not OUT.exists(),'R15_APPLICATION_FRESH_OUTPUT')
    source=OUT/'source/fpga';source.mkdir(parents=True)
    for name,value in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(value)
    manifest['source_root']=str(source);dump(OUT/'manifest.json',manifest);dump(OUT/'production-bundle.json',bundle)
    return dict(id=ID,manifest=str(OUT/'manifest.json'),production_sv=70,compiled_sv=71,status='SOURCE_PREPARED_NOT_NATIVE')


if __name__=='__main__':print(json.dumps(freeze(),indent=2))
