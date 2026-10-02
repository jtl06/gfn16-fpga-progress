"""Source-only native role preparation for the incremental packed delay leaf."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from . import stream27_comm_packed_bind as binding

ROOT = binding.ROOT
DONOR = ROOT / ('results/throughput-20260929/trackS-p16-diet-analysis-v1/'
                'commutator-shared-mlab-v1')
TOP = 'genefer_stream27_comm_packed_normal_v1'
ID = 's4-p16-comm-packed-normal-q1-v1'
CANDIDATE = 's4-p16-comm-packed-v1'
# Genuine owner event after this exact leaf/source projection passed checks.
RTL_READY = '2026-10-02T00:08:45Z'
DEPTHS = (1, 2, 4, 8, 16, 32, 64, 2048)


def top_source():
    old = (DONOR / 'normal-role-v1/source/fpga/rtl/'
           'genefer_stream27_shared_comm_normal_v1.sv').read_text()
    header = old[:old.index('\n genefer_stream27_')]
    text = header.replace('genefer_stream27_shared_comm_normal_v1', TOP) + '\n'
    for g in range(16):
        depth = DEPTHS[g % 8]
        contexts = 1 + g // 8
        frame = max(128, 2 * depth)
        common = (f'.clk,.rst_n,.in_slot_valid(in_slot_valid[{g}]),.frame_start(frame_start[{g}]),'
                  f'.context_in(context_in[{g}]),.generation_in(generation_in[{g*8}+:8]),'
                  f'.context_enabled(context_enabled[{g*2}+:{contexts}]),'
                  f'.live_generations(live_generations[{g*16}+:{contexts*8}]),.quarantine(quarantine[{g}])')
        for side, module in [('new', binding.NEW), ('old', binding.OLD)]:
            if side == 'old':
                text += (f' wire old_slot_g{g},old_start_g{g},old_eligible_g{g},old_error_g{g},'
                         f'old_pending_g{g},old_context_g{g};\n wire [7:0] old_generation_g{g};\n')
                tail = lambda key: f'old_{key}_g{g}'
            else:
                tail = lambda key: f'new_{key}[{g}]' if key != 'generation' else f'new_generation[{g*8}+:8]'
            text += f''' {module} #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),.GEN_W(8),.DEPTH({depth}),.FRAME_T({frame}),.CONTEXTS({contexts})) {side}_g{g} (
 {common},.upper_in(upper_in[{g*224}+:224]),.lower_in(lower_in[{g*224}+:224]),
 .upper_payload(upper_payload[{g*8}+:8]),.lower_payload(lower_payload[{g*8}+:8]),
 .out_slot_valid({tail('slot')}),.out_frame_start({tail('start')}),.out_eligible({tail('eligible')}),
 .out_error({tail('error')}),.fault_pending({tail('pending')}),.context_out({tail('context')}),.generation_out({tail('generation')}),
 .upper_out({side}_upper[{g*224}+:224]),.lower_out({side}_lower[{g*224}+:224]),
 .upper_payload_out({side}_upper_payload[{g*8}+:8]),.lower_payload_out({side}_lower_payload[{g*8}+:8]));
'''
        for lane in range(8):
            at = g * 8 + lane
            for key in ('slot', 'start', 'eligible', 'error', 'pending', 'context'):
                text += f' assign old_{key}[{at}]=old_{key}_g{g};\n'
            text += f' assign old_generation[{at*8}+:8]=old_generation_g{g};\n'
    return text + 'endmodule\n'


def prepare(output, budget):
    output = Path(output).resolve()
    binding.need(not output.exists(), 'S4_PACKED_FRESH_OUTPUT')
    binding.need(not (ROOT / 'docs/briefs/PAUSE').exists() and not (ROOT / 'queue/PAUSE').exists(), 'S4_PACKED_PAUSE')
    files = {
        'rtl/' + TOP + '.sv': top_source(),
        'rtl/' + binding.NEW + '.sv': (ROOT / binding.LEAF).read_text(),
        'rtl/' + binding.OLD + '.sv': (ROOT / binding.PARENT).read_text(),
    }
    for name in ('genefer_stream27_delay_mlab_v1.sv', 'genefer_stream27_mdc_fifo_smallreg_v1.sv',
                 'genefer_stream27_mdc_commutator_sync.sv'):
        files['rtl/' + name] = (ROOT / 'rtl/kernel' / name).read_text()
    cpp = (DONOR / 'tb/shared_comm_normal_v1.cpp').read_text()
    cpp = cpp.replace('genefer_stream27_shared_comm_normal_v1', TOP)
    cpp = cpp.replace('SHARED_COMM_NORMAL_PASS', 'COMM_PACKED_NORMAL_PASS')
    files['rtl/tb/comm_packed_normal.cpp'] = cpp
    files['rtl/tb/native_runtime_context_v1.h'] = (ROOT / 'rtl/tb/native_runtime_context_v1.h').read_text()
    files['lineage/stream27_comm_packed_native.py'] = Path(__file__).read_text()
    files['lineage/stream27_comm_packed_bind.py'] = (ROOT / binding.SELF).read_text()
    source = output / 'source/fpga'
    for name, raw in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw)
    pins = {name: binding.sha(raw.encode()) for name, raw in files.items()}
    manifest = dict(schema='native-source-gate-v1', status='prepared_not_executed', host='UNBOUND',
                    source_root=str(source), output_parent=str(output / 'UNBOUND_OUTPUT'), sources=pins,
                    build=dict(top=TOP, sv_sources=[name for name in files if name.endswith('.sv')],
                               cpp_source='rtl/tb/comm_packed_normal.cpp', parameters={},
                               cflags=['-std=c++17', '-O2', '-Werror=return-type'], runtime_threads=1),
                    probe=dict(argv=['{exe}', '--runtime-probe'], expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)),
                    steps=[dict(name='comm-packed-normal', argv=['{exe}'], expected_returncode=0,
                                expected_stdout='COMM_PACKED_NORMAL_PASS geometries=16 cycles=18000 lane_checks=2304000\n', expected_stderr='')],
                    scope='P16 eight-pair packed vs qualified shared parent and independent deque;16 depth/context geometries,raw canceled payload,exact edge/tag/data control. No area/whole claim.', promotion_allowed=False)
    manifest_path = output / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    sys.path.insert(0, str(ROOT))
    from tools import native_class_package_v2 as package
    packet = output / 'packet-01'
    package.prepare(manifest_path, source, 'gcp-c4d-static01-v1', 's4-p16-comm-packed-normal-01-v1', 'run', packet, Path(budget).resolve())
    native = json.loads((packet / 'ticket.json').read_text())
    template = json.loads((DONOR / 'normal-role-v1/global-ticket.json').read_text())
    entry = template['packages'][0]
    entry.update(archive=str(packet / 'package.tar.gz'), sha256=binding.sha((packet / 'package.tar.gz').read_bytes()),
                 ticket_sha256=binding.sha((packet / 'ticket.json').read_bytes()), manifest_sha256=native['manifest_sha256'],
                 worker_id=native['id'], native_root=native['native_root'])
    for key in ('runner', 'stager'):
        path = ROOT / entry[key] if key == 'runner' else Path(entry[key])
        entry[key + '_sha256'] = binding.sha(path.read_bytes())
    for dep in entry['stager_dependencies']:
        dep['sha256'] = binding.sha(Path(dep['path']).read_bytes())
    snapshot = {name: pin for name, pin in pins.items() if name.endswith('.sv')}
    template.update(id=ID, candidate_id=CANDIDATE, owner='stream-core', created=datetime.now(timezone.utc).isoformat(),
                    test_role='normal', source_gate=dict(scope=manifest['scope'], promotion_allowed=False))
    template['rtl_readiness'] = dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=CANDIDATE, source_snapshot=snapshot,
                                    candidate_source_sha256=binding.sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()), rtl_ready_at_utc=RTL_READY)
    ticket = output / 'global-ticket-v1.json'
    ticket.write_text(json.dumps(template, indent=2) + '\n')
    return dict(manifest=str(manifest_path), global_ticket=str(ticket), rtl_ready_at_utc=RTL_READY)


def fault_source():
    cpp = (DONOR / 'tb/shared_comm_fault_v1.cpp').read_text()
    binding.need(cpp.count('#include "shared_comm_normal_v1.cpp"') == 1, 'S4_PACKED_FAULT_DONOR_INCLUDE')
    cpp = cpp.replace('#include "shared_comm_normal_v1.cpp"', '#include "comm_packed_normal.cpp"')
    cpp = cpp.replace('genefer_stream27_shared_comm_normal_v1', TOP)
    return cpp.replace('SHARED_COMM_FAULT_PASS', 'COMM_PACKED_FAULT_PASS')


def prepare_fault(output, budget, normal):
    """Independent registered-fault/reset scope; captured normal stays intact."""
    output = Path(output).resolve()
    normal = Path(normal).resolve()
    binding.need(not output.exists(), 'S4_PACKED_FRESH_FAULT_OUTPUT')
    binding.need(not (ROOT / 'docs/briefs/PAUSE').exists() and not (ROOT / 'queue/PAUSE').exists(), 'S4_PACKED_PAUSE')
    manifest = json.loads((normal / 'manifest.json').read_text())
    source = output / 'source/fpga'
    for name, pin in manifest['sources'].items():
        raw = (normal / 'source/fpga' / name).read_bytes()
        binding.need(binding.sha(raw) == pin, 'S4_PACKED_CAPTURED_NORMAL_PIN')
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    cpp_name = 'rtl/tb/comm_packed_fault.cpp'
    cpp = fault_source()
    binding.need('rtl/tb/comm_packed_normal.cpp' in manifest['sources'], 'S4_PACKED_FAULT_INCLUDE_CLOSED')
    (source / cpp_name).write_text(cpp)
    manifest['sources'][cpp_name] = binding.sha(cpp.encode())
    manifest['build']['cpp_source'] = cpp_name
    manifest.update(source_root=str(source), output_parent=str(output / 'UNBOUND_OUTPUT'),
                    scope='Separate paired packed/shared registered protocol faults, sticky/quarantine hold, occupied deep reset/recovery. Unchanged control authority and origin-edge accepted tails; not exhaustive fault proof.')
    manifest['steps'] = [dict(name='comm-packed-separate-faults', argv=['{exe}'], expected_returncode=0,
                              expected_stdout='COMM_PACKED_FAULT_PASS geometries=16 protocol_cases=6 quarantine_cases=1 reset_cases=1\n', expected_stderr='')]
    manifest_path = output / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    sys.path.insert(0, str(ROOT))
    from tools import native_class_package_v2 as package
    worker = 's4-p16-comm-packed-fault-01-v2'
    packet = output / 'packet-01'
    package.prepare(manifest_path, source, 'gcp-c4d-static01-v1', worker, 'run', packet, Path(budget).resolve())
    native = json.loads((packet / 'ticket.json').read_text())
    template = json.loads((normal / 'global-ticket-v1.json').read_text())
    entry = template['packages'][0]
    entry.update(archive=str(packet / 'package.tar.gz'), sha256=binding.sha((packet / 'package.tar.gz').read_bytes()),
                 ticket_sha256=binding.sha((packet / 'ticket.json').read_bytes()), manifest_sha256=native['manifest_sha256'],
                 worker_id=worker, native_root=native['native_root'])
    template.pop('rtl_readiness', None)
    template.update(id='s4-p16-comm-packed-fault-q1-v2', created=datetime.now(timezone.utc).isoformat(),
                    test_role='deliberate_fault', after=[ID], source_gate=dict(scope=manifest['scope'], promotion_allowed=False))
    template['preserved_failed_predecessor'] = dict(id='s4-p16-comm-packed-fault-q1-v1',
        reason='Pre-model build failed: renamed normal C++ include was not updated. Production RTL unchanged.')
    ticket = output / 'global-ticket-v1.json'
    ticket.write_text(json.dumps(template, indent=2) + '\n')
    return dict(manifest=str(manifest_path), global_ticket=str(ticket))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--budget', required=True)
    parser.add_argument('--normal-role')
    args = parser.parse_args()
    result = prepare_fault(args.output, args.budget, args.normal_role) if args.normal_role else prepare(args.output, args.budget)
    print(json.dumps(result, indent=2))
