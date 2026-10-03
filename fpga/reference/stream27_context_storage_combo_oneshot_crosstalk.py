"""R6 own full-size output-word detector; production RTL is unchanged."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_storage_combo_oneshot_crosstalk.py'
DONOR = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-oneshot-native-v1/full-normal'
DONOR_PIN = '57f33da990b668b127498f0525b4d367d4531c5297278906b9c64f38a122ec8f'
OUT = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-oneshot-ownlong-v1/full-crosstalk-v1'
CPP = 'rtl/tb/stream27_p16_two_context_crosstalk.cpp'
HEADER = 'rtl/tb/s4_p16_two_context_full_config.h'
TOP = 'genefer_stream27_combo_r6_crosstalk_observer_v1'
ID = 's4-p16-c2-combo-r6-crosstalk-q1-v1'
BASES = [604832956, 999999937]
def need(ok, why):
    if not ok: raise ValueError('R6_CROSSTALK_'+why)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def dump(path, value):
    with Path(path).open('x') as stream: json.dump(value, stream, indent=2); stream.write('\n')
def config(): return dict(aw=16,p=16,contexts=2,bases=BASES,address=17,mutation='native-output-word-bit0-context0')
def validate(stdout, stderr, rc, config, assets):
    need(config==globals()['config']() and assets=={}, 'CONFIG')
    need(type(rc) is int and rc==0 and stderr=='' and stdout.startswith('R84_C2_CROSSTALK_PASS '), 'TYPED_OUTPUT')
    values=json.loads(stdout.removeprefix('R84_C2_CROSSTALK_PASS '))
    expected=dict(aw=16,p=16,contexts=2,bases=BASES,squares=4,peer_verified_words=65536,
        mutated_context=0,mutated_address=17,typed_mismatches=1,signed96=True,peer_bit_identical=True,
        metadata_unchanged=True,native_output_word_only=True,model_threads=1)
    need(set(values)==set(expected)|{'seconds'} and all(values[k]==v and type(values[k]) is type(v) for k,v in expected.items()), 'EXACT_PEER_CONTRACT')
    need(stdout.endswith('\n') and '\n' not in stdout[:-1] and type(values['seconds']) in (int,float)
        and math.isfinite(values['seconds']) and 0<values['seconds']<3700, 'BOUNDED_ONE_FOOTER')
    return dict(status='PASS_expected_contracts',measurements=values,promotion_allowed=False,
        scope='Own R6 native-only one output-word mismatch with full peer image unchanged; not a production RAM/configuration fault.')
def role():
    raw=(DONOR/'manifest.json').read_bytes(); need(sha(raw)==DONOR_PIN, 'OWN_FULL_CAPTURE')
    manifest=json.loads(raw)
    files={n:(DONOR/'source/fpga'/n).read_bytes() for n in manifest['sources']}
    need(all(sha(files[n])==pin for n,pin in manifest['sources'].items()), 'CAPTURE_PINS')
    oldtop=manifest['build']['top']; old='rtl/'+oldtop+'.sv'; original=files.pop(old).decode()
    root=manifest['r84']['native_observer']['production_top']
    sites=[('module '+oldtop+' #(', 'module '+TOP+' #('),
        (' output logic dbg_setup_done,dbg_setup_context,', ' input logic mutant_enable,\n output logic dbg_setup_done,dbg_setup_context,'),
        ('\n '+root+' #(\n', '\n wire [95:0] native_read_data;\n '+root+' #(\n'),
        (' ) candidate (.*);', ' ) candidate (.read_data(native_read_data), .*);'),
        ('endmodule\n', " assign read_data=(mutant_enable && read_valid && !host_context && host_addr==16'd17) ? (native_read_data ^ 96'd1) : native_read_data;\nendmodule\n")]
    text=original
    for before,after in sites:
        need(text.count(before)==1, 'EXACT_OBSERVER_SITE'); text=text.replace(before,after,1)
    reverse=text
    for before,after in reversed(sites):
        need(reverse.count(after)==1, 'EXACT_REVERSE_SITE'); reverse=reverse.replace(after,before,1)
    need(reverse==original and not re.search(r'\b(always|always_ff|always_comb|initial)\b',text), 'TRANSPARENT_ZERO_EDGE_DELTA')
    new='rtl/'+TOP+'.sv'; files[new]=text.encode()
    header=files[HEADER].decode(); need(header.count(oldtop)==2, 'MODEL_HEADER')
    files[HEADER]=header.replace(oldtop,TOP).encode()
    files[CPP]=(ROOT/CPP).read_bytes(); files[SELF]=(ROOT/SELF).read_bytes()
    manifest['build'].update(top=TOP,cpp_source=CPP)
    manifest['build']['sv_sources']=[new if n==old else n for n in manifest['build']['sv_sources']]
    need(len(manifest['build']['sv_sources'])==56 and manifest['build']['parameters']['COLD_SECOND_ONESHOT']==1, 'R6_55_PLUS_OBSERVER')
    manifest['sources']={n:sha(value) for n,value in files.items()}
    manifest['steps']=[dict(name='r6-deliberate-full-single-word-crosstalk',argv=['{exe}'],expected_returncode=0,
        validator=dict(source=SELF,function='validate',config=config(),assets={}))]
    manifest.update(test_role='deliberate_fault', source_root='UNBOUND', output_parent='UNBOUND')
    manifest['r84']['native_observer'].update(mutation_added_edges=0, output_word_only=True)
    snapshot={n:sha(value) for n,value in files.items() if n.endswith('.sv')}
    manifest['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=ID.removesuffix('-q1-v1'),
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    manifest['r6_crosstalk']=dict(donor_manifest_sha256=DONOR_PIN, production55_exact=True,
        native_only_zero_edge_observer=True, output_word_only=True, no_RAM_or_configuration_fault_claim=True,
        own_normal_dependency='s4-p16-c2-combo-r6-full-normal-q1-v1', promotion_allowed=False)
    return manifest,files
def prepare():
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    need(not OUT.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')), 'FRESH_UNPAUSED')
    manifest,files=role(); source=OUT/'source/fpga'; source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name; path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    manifest['source_root']=str(source)
    dump(OUT/'manifest.json',manifest); dump(OUT/'host-hours.json',candidate_ladder.budget_from_hourly())
    variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1'; worker='s4-p16-c2-combo-r6-crosstalk-'+pair+'-v1'; packet=OUT/('packet-'+pair)
        result=package.prepare(OUT/'manifest.json',source,profile,worker,'run',packet,OUT/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=ID,owner='merged-ntt-model',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Bounded4GiB exploration after own full normal below3GiB; only stateless observer and same full driver/reference geometry. DesiredGCP8 retained; failures preserved.',
        est_minutes=20,promotion_bound=False,test_role='deliberate_fault',rtl_readiness=manifest['rtl_readiness'],packages=variants,
        allowed_hosts=['gfn16-pilot-c4d','aethia'],after=['s4-p16-c2-combo-r6-full-normal-q1-v1'],on='PASS_expected_contracts')
    dump(OUT/'global-ticket.json',logical)
    return dict(id=ID,ticket=str(OUT/'global-ticket.json'),status='PREPARED_NOT_NATIVE_NOT_SUBMITTED')
if __name__=='__main__': print(json.dumps(prepare(),indent=2))
