"""Private R8 parent/direct live-bound paired native contracts, N256 only.

Uses the actual frozen AW8 capture's canonical leaf and exact parent bytes.
No local HDL, full-N arithmetic, new runner or whole-host qualification.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_storage_combo_directbound_liveprobe.py'
CPP = 'rtl/tb/stream27_canonical_directbound_pair_v1.cpp'
TOP = 'genefer_stream27_canonical_directbound_pair_v1'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-directbound-native-v1'
CAPTURE = BASE / 'aw8-normal/production-bundle.json'
PARENT = 'genefer_stream27_canonical_image_loadlocal_v1'
LOCAL = 'genefer_stream27_canonical_image_directbound_v1'
RAM = 'genefer_sdp_ram32'
GATE = 's4-p16-c2-combo-r8-aw8-normal-q1-v1'
IDS = dict(bounds='s4-p16-c2-combo-r8-livebound-fault-q1-v1')


def need(ok, why):
    if not ok:
        raise ValueError('C2_R8_DIRECTPAIR_' + why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wrapper():
    inputs = '''input logic clk,rst_n,load_valid,begin_canonical,read_req,
 input logic [3:0] load_row,
 input logic [511:0] load_data,c0,c1,
 input logic [31:0] base,
 input logic [7:0] read_address'''
    outputs = []
    instances = []
    for label, module in (('parent', PARENT), ('local', LOCAL)):
        outputs += [f'output logic {label}_bound_bad', f'output logic {label}_busy,{label}_done,{label}_error,{label}_image_valid',
            f'output logic [7:0] {label}_error_code', f'output logic [63:0] {label}_cycles',
            f'output logic {label}_read_valid', f'output logic [7:0] {label}_read_address_out',
            f'output logic signed [95:0] {label}_read_data']
        signals = ('busy', 'done', 'error', 'image_valid', 'error_code', 'cycles',
                   'read_valid', 'read_address_out', 'read_data')
        instances.append(f'{module} #(.AW(8),.P(16)) {label}_dut (\n'
            ' .clk,.rst_n,.load_valid,.begin_canonical,.read_req,.load_row,.load_data,.c0,.c1,.base,.read_address,\n ' +
            ','.join(f'.{name}({label}_{name})' for name in signals) + '\n);\n' + f'assign {label}_bound_bad={label}_dut.correction_bad;\n')
    return '// State-free native observer: independent old/new payload RAMs.\nmodule ' + TOP + ' (\n' + inputs + ',\n ' + ',\n '.join(outputs) + '\n);\n' + ''.join(instances) + 'endmodule\n'


def role(mode='bounds'):
    from fpga.reference import stream27_context_storage_combo_directbound_native as n
    from fpga.reference import stream27_context_storage_combo_directbound_bind as core
    need(mode == 'bounds', 'BOUNDS_ONLY')
    need(sha((ROOT / core.SELF).read_bytes()) == n.BINDER_PIN, 'FROZEN_CORE')
    bundle = json.loads(CAPTURE.read_bytes())
    manifest = json.loads((BASE / 'aw8-normal/manifest.json').read_bytes())
    need(bundle['context_storage_combo_directbound']['reverse_to_parent_exact'] and
         bundle['geometry']['n']==256 and len(bundle['files'])==55, 'OWN_AW8_PRODUCTION')
    old_manifest, old_files, old_bundle = n.capture('aw8')
    files = {name+'.sv': bundle['files'][name+'.sv'].encode() for name in (LOCAL,RAM)}
    parent = old_bundle['files'][PARENT+'.sv'].encode()
    need(sha(parent)==core.LEAF_PIN and core.reverse_leaf(files[LOCAL+'.sv'].decode()).encode()==parent,
         'COMPLETE_CANONICAL_REVERSE')
    need(all(sha(raw)==manifest['sources']['rtl/'+name] for name,raw in files.items()), 'CAPTURE_PINS')
    files[PARENT+'.sv']=parent
    files[TOP+'.sv']=wrapper().encode()
    files={'rtl/'+name:raw for name,raw in files.items()}
    files[CPP]=(ROOT/CPP).read_bytes()
    files[SELF]=(ROOT/SELF).read_bytes()
    files['lineage/'+core.SELF]=(ROOT/core.SELF).read_bytes()
    step=dict(name='r8-livebound',argv=['{exe}','--bounds'],expected_returncode=0,
      expected_stdout='R8_DIRECTBOUND_BOUND_PASS aw=8 p=16 live_checks=23024 u32_base=1 signed_extrema=1 zero_always_bad=1 c1_priority=1 origin_faults=4 paired_edges=1\n',expected_stderr='')
    result=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
      sources={name:sha(raw) for name,raw in files.items()},
      build=dict(top=TOP,sv_sources=['rtl/'+name+'.sv' for name in (RAM,PARENT,LOCAL,TOP)],cpp_source=CPP,
        parameters={},cflags=['-std=c++17','-Werror=return-type']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[step],test_role='deliberate_fault',
      livebound=dict(aw=8,p=16,source_bundle_sha256=sha(CAPTURE.read_bytes()),parent_leaf_sha256=core.LEAF_PIN,
        own_normal_dependency=GATE,all_unsigned32_base_signed32_c0_domain_model=True,
        actual_signed_extrema_live_no_clock_observations=True,actual_BEGIN_origin_faults=4,
        c1_conflict_reset_read_priority_paired=True,no_whole_fault_or_clock_inheritance=True,promotion_allowed=False))
    snapshot={name:sha(raw) for name,raw in files.items() if name.endswith('.sv')}
    result['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-p16-c2-combo-r8-livebound-v1',
      source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
      rtl_ready_at_utc=n.READY)
    return result,files


def dump(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')


def prepare(output,mode='bounds'):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve()
    need(out.is_relative_to(BASE) and not out.exists(),'FRESH_CONTAINED_OUTPUT')
    need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'PAUSE')
    manifest,files=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest)
    dump(out/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-combo-r8-livebound-'+mode+'-'+pair+'-v1';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes())) for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=IDS[mode],owner='p16-mlab',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P2',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        allowed_hosts=['gfn16-pilot-c4d','aethia'],resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Four-module N256 paired canonical component, bounded4GiB exploratory trial; no whole memory inference.',
        est_minutes=5,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],packages=variants,
        after=[GATE],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical)
    return dict(id=logical['id'],ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE')
