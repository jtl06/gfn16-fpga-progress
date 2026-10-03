"""Own compute60 full normal plus accelerated HOST timestamp aliases only.

No datapath/protocol counter/time/owner changes; no billions of real edges,
arbitrary bank-corruption, protected-fault or real PCIe qualification.
"""
import json
from pathlib import Path
from fpga.reference import stream27_protected_field100_native_v2 as scalar
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump,runtime_before_model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_compute_full_wrap_native.py'
CPP='rtl/tb/stream27_r15_compute_full_wrap.cpp'
HEADER='rtl/tb/s4_p16_two_context_full_config.h'
CAPTURE=ROOT/'results/throughput-20260929/trackS-r15-compute-native-v1/full-normal-v2'
CAPTURE_PIN='022cd0ccceee77227e38a13f50584262da747ab60f187a459e265dbf711422d9'
RECIPE=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-wrap-v1/full-normal'
RECIPE_PIN='b57535498e6c4dec263e8f44f0f11661e65cc63139962130f62c2b1d35b1144b'
CPP_PIN='1f117f7a389cde5598a32dc9bb7f8971516dedb024b31153b7b016ae0ae54488'
FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=0,PCIE_SHELL=0)
ID='s4-p16-c2-r15-compute-full-wrap-normal-q1-v1'
FOOTER='R15_COMPUTE_FULL_WRAP_PASS aliases=3 cold_accepts=2 cache_events_per_field=4 reads=393216 masks=1/2/3 independent_reference=1 real_datapath_edges=1 simulation_only=1\n'


def validate(stdout,stderr,rc,config,assets):
    need(config==dict(scalar.config(),r15_flags=FLAGS) and assets=={},'R15_WRAP_CONFIG')
    need(stdout.endswith(FOOTER) and len(stdout.splitlines())==2,'R15_WRAP_SCOPED_FOOTERS')
    result=scalar.validate(stdout.removesuffix(FOOTER),stderr,rc,scalar.config(),{})
    result.update(r15_flags=FLAGS,promotion_allowed=False,
      wrap=dict(aliases=3,actual_external_cold_accepts=2,table_events_per_field=4,host_timestamp_only=True,
        protocol_time_forced=False,arithmetic_owner_payload_forced=False,billions_of_edges_simulated=False,
        expected_bank_oracle=False),scope='Own compute60 full independent-reference/context-alone-joint plus host timestamp aliases. Lean build; host GL assumed (unimplemented). No real protocol wrap, bank fault immunity, ancestor execution, protected-fault/clock/PCIe claim.')
    return result


def role():
    raw=(CAPTURE/'manifest.json').read_bytes();need(sha(raw)==CAPTURE_PIN,'R15_WRAP_OWN_CAPTURE')
    m=json.loads(raw);b=json.loads((CAPTURE/'production-bundle.json').read_bytes())
    f={n:(CAPTURE/'source/fpga'/n).read_bytes() for n in m['sources']}
    need(all(sha(f[n])==pin for n,pin in m['sources'].items()) and len(b['files'])==60 and
         b['r15_all']['flags']==FLAGS and m['build']['parameters']==dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
         'R15_WRAP_OWN_ALL60_COMPILED_SOURCE')
    raw=(RECIPE/'manifest.json').read_bytes();need(sha(raw)==RECIPE_PIN,'R15_WRAP_DIAGNOSTIC_RECIPE')
    rm=json.loads(raw);rp=RECIPE/'source/fpga';cpp=(rp/rm['build']['cpp_source']).read_bytes()
    need(sha(cpp)==CPP_PIN,'R15_WRAP_FROZEN_DRIVER')
    observer='rtl/'+m['build']['top']+'.sv';previous=(rp/observer).read_text();normal=f[observer].decode()
    marker=' output logic [2:0] dbg_field_fast'
    ports=previous[previous.index(marker):previous.index(');',previous.index(marker))+2]
    need(ports.endswith(');') and ports.count('probe_cold_accept')==1,'R15_WRAP_CONTINUOUS_PORTS')
    original_marker=marker+'\n);';need(normal.count(original_marker)==1,'R15_WRAP_OBSERVER_ANCHOR')
    monitor=previous[previous.index(' // Native-only continuous observation;'):previous.rindex('endmodule')]
    need('always' not in monitor and 'initial' not in monitor.replace('initial_correction_seen',''),
         'R15_WRAP_MONITOR_NO_STATE')
    changed=normal.replace(original_marker,ports,1).replace('endmodule\n',monitor+'endmodule\n',1)
    need(changed.replace(monitor,'',1).replace(ports,original_marker,1)==normal,'R15_WRAP_LITERAL_OBSERVER_REVERSE')
    f[observer]=changed.encode()
    host=b['files'][b['top']+'.sv'];second=int(host.split('SECOND_CORRECTION=',1)[1].split(';',1)[0])
    recipe_header=(rp/HEADER).read_text()
    need('constexpr unsigned SECOND_CORRECTION='+str(second)+';' in recipe_header and
         'constexpr bool OLD_PROPOSAL=false;' in recipe_header,'R15_WRAP_OWN_SECOND_EDGE')
    f[HEADER]+=f'constexpr unsigned SECOND_CORRECTION={second};\nconstexpr bool OLD_PROPOSAL=false;\n'.encode()
    before='FIELD100_PROTECTED_FULL_WRAP_PASS';need(cpp.decode().count(before)==1,'R15_WRAP_FOOTER_ONLY_DRIVER_DELTA')
    text=cpp.decode().replace(before,'R15_COMPUTE_FULL_WRAP_PASS',1);runtime_before_model(text)
    f[CPP]=text.encode();f[SELF]=(ROOT/SELF).read_bytes()
    m['build']['cpp_source']=CPP
    m['steps']=[dict(name='normal-full-r15-compute-three-host-aliases',argv=['{exe}'],expected_returncode=0,
      validator=dict(source=SELF,function='validate',config=dict(scalar.config(),r15_flags=FLAGS),assets={}))]
    m['r15_full_wrap']=dict(production_generated_sha256=b['generated_sha256'],production_top=b['top'],
      own_all60_production_unchanged=True,stateless_observer_reversible=True,
      recipe_cpp_sha256=CPP_PIN,recipe_execution_not_inherited=True,host_timestamp_only=True,
      real_protocol_payload_owner_time_unchanged=True,expected_bank_oracle=False,
      billions_of_edges=False,lean_build_label='host GL assumed (unimplemented)',promotion_allowed=False)
    m['sources']={n:sha(v) for n,v in f.items()};snapshot={n:p for n,p in m['sources'].items() if n.endswith('.sv')}
    m.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=ID.removesuffix('-q1-v1'),
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=m['rtl_readiness']['rtl_ready_at_utc']))
    return m,f,b


def freeze():
    m,f,b=role();out=ROOT/'results/throughput-20260929/trackS-r15-compute-wrap-native-v1/full-normal'
    need(not out.exists(),'R15_WRAP_FRESH_OUTPUT');source=out/'source/fpga';source.mkdir(parents=True)
    for n,v in f.items():
        p=source/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(v)
    m['source_root']=str(source);dump(out/'manifest.json',m);dump(out/'production-bundle.json',b)
    return dict(id=ID,manifest=str(out/'manifest.json'),status='SOURCE_NOT_NATIVE')


if __name__=='__main__':print(json.dumps(freeze(),indent=2))
