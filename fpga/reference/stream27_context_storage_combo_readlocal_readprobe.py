"""Private R4 old/new canonical read-local paired native contracts, N256 only.

Uses the actual frozen AW8 capture's canonical leaf and exact parent bytes.
No local HDL, full-N arithmetic, new runner or whole-host qualification.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_storage_combo_readlocal_readprobe.py'
CPP = 'rtl/tb/stream27_canonical_readlocal_pair_v1.cpp'
TOP = 'genefer_stream27_canonical_readlocal_pair_v1'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-readlocal-native-v1'
CAPTURE = BASE / 'aw8-normal/production-bundle.json'
PARENT = 'genefer_stream27_canonical_image_pipe_v1'
LOCAL = 'genefer_stream27_canonical_image_readlocal_v1'
RAM = 'genefer_sdp_ram32'
GATE = 's4-p16-c2-combo-r4-aw8-normal-q1-v1'
NORMAL_ID = 's4-p16-c2-combo-r4-readpair-normal-q1-v1'
IDS = dict(normal=NORMAL_ID, faults='s4-p16-c2-combo-r4-readpair-faults-q1-v1',
           oracle='s4-p16-c2-combo-r4-readpair-oracle-q1-v1')


def need(ok, why):
    if not ok:
        raise ValueError('C2_R4_READPAIR_' + why)


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
        outputs += [f'output logic {label}_busy,{label}_done,{label}_error,{label}_image_valid',
            f'output logic [7:0] {label}_error_code', f'output logic [63:0] {label}_cycles',
            f'output logic {label}_read_valid', f'output logic [7:0] {label}_read_address_out',
            f'output logic signed [95:0] {label}_read_data']
        signals = ('busy', 'done', 'error', 'image_valid', 'error_code', 'cycles',
                   'read_valid', 'read_address_out', 'read_data')
        instances.append(f'{module} #(.AW(8),.P(16)) {label}_dut (\n'
            ' .clk,.rst_n,.load_valid,.begin_canonical,.read_req,.load_row,.load_data,.c0,.c1,.base,.read_address,\n ' +
            ','.join(f'.{name}({label}_{name})' for name in signals) + '\n);\n')
    return '// State-free native observer: independent old/new payload RAMs.\nmodule ' + TOP + ' (\n' + inputs + ',\n ' + ',\n '.join(outputs) + '\n);\n' + ''.join(instances) + 'endmodule\n'


def role(mode='normal'):
    from fpga.reference import stream27_context_storage_combo_readlocal_bind as core
    need(mode in IDS, 'MODE')
    need(sha((ROOT / core.SELF).read_bytes()) == '639b05599ba8294e3035ea66298ef216ec2382ca0e506fdb3df910691bd8470d', 'FROZEN_CORE')
    bundle = json.loads(CAPTURE.read_bytes())
    manifest = json.loads((BASE / 'aw8-normal/manifest.json').read_bytes())
    need(sha((BASE / 'aw8-normal/manifest.json').read_bytes()) ==
         '41979ae342709cc7950b47f1b6f265df2438268369d958fef02cc638b6ae7811', 'FROZEN_CAPTURE')
    files = {name + '.sv': bundle['files'][name + '.sv'].encode() for name in (LOCAL, RAM)}
    parent = (ROOT / 'rtl/kernel' / (PARENT + '.sv')).read_bytes()
    need(sha(parent) == core.LEAF_PIN and core.reverse_leaf(files[LOCAL + '.sv'].decode()).encode() == parent,
         'COMPLETE_CANONICAL_REVERSE')
    need(all(sha(raw) == manifest['sources']['rtl/' + name] for name, raw in files.items()), 'CAPTURED_RTL_PINS')
    files[PARENT + '.sv'] = parent
    files[TOP + '.sv'] = wrapper().encode()
    files = {'rtl/' + name: raw for name, raw in files.items()}
    files[CPP] = (ROOT / CPP).read_bytes()
    files[SELF] = (ROOT / SELF).read_bytes()
    files['lineage/' + core.SELF] = (ROOT / core.SELF).read_bytes()
    step = dict(name='r4-readpair-' + mode, argv=['{exe}'] + ([] if mode == 'normal' else ['--faults' if mode == 'faults' else '--wrong-word']),
        expected_returncode=1 if mode == 'oracle' else 0,
        expected_stdout={'normal':'R4_READLOCAL_NORMAL_PASS aw=8 p=16 images=2 signed96_reads=516 dirty_read=1 consecutive_reads=3 special_sentinel=1 paired_edges=1\n',
          'faults':'R4_READLOCAL_FAULT_PASS aw=8 p=16 cases=12 pending_conflicts=2 pending_reset=1 recovery_reads=256 paired_edges=1\n',
          'oracle':''}[mode], expected_stderr='R4_READLOCAL_WRONG_WORD\n' if mode == 'oracle' else '')
    result = dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
        sources={n:sha(raw) for n,raw in files.items()},
        build=dict(top=TOP,sv_sources=['rtl/'+n+'.sv' for n in (RAM,PARENT,LOCAL,TOP)],cpp_source=CPP,
            parameters={},cflags=['-std=c++17','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[step],test_role='normal' if mode=='normal' else 'deliberate_fault',
        readpair=dict(aw=8,p=16,parent_leaf_sha256=core.LEAF_PIN,
            local_leaf_sha256=sha(files['rtl/'+LOCAL+'.sv']),captured_bundle_sha256=sha(CAPTURE.read_bytes()),
            default_fault_priority_and_latency_unchanged=True,independent_payload_RAMS=True,
            full_owner_host_qualification_not_inferred=True,unknown_input_equivalence_claim=False,promotion_allowed=False))
    snapshot={n:sha(raw) for n,raw in files.items() if n.endswith('.sv')}
    result['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-p16-c2-combo-r4-readpair-v1',
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc='2026-10-02T11:24:07Z')
    return result,files


def dump(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')


def prepare(output,mode='normal'):
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
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-combo-r4-readpair-'+mode+'-'+pair+'-v1';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes())) for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=IDS[mode],owner='independent-review',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        allowed_hosts=['gfn16-pilot-c4d','aethia'],resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Four-module N256 paired canonical component, bounded4GiB exploratory trial; no whole memory inference.',
        est_minutes=5,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],packages=variants,
        after=[GATE if mode=='normal' else NORMAL_ID],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical)
    return dict(id=logical['id'],ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE')
