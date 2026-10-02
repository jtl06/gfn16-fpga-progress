"""Normal-first source-specific P16 ROM/BF co-retiming field roles."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from . import stream27_shared_field_flags as fields
from . import stream27_root_outputreg_bind as binding
from . import stream27_comm_packed_bind as packed
from .stream27_shared_warm_full_native_v1 import compile_bench
from .stream27_p8_warm_native_v2 import lease_ledger

ROOT = binding.ROOT
SELF = 'reference/stream27_root_outputreg_native.py'


def prepare_fit(normal, output):
    """Measure one qualified field against the exact completed parent."""
    normal, output = Path(normal).resolve(), Path(output).resolve()
    binding.need(not output.exists(), 'S4_ROOTREG_FRESH_FIT_OUTPUT')
    binding.need(not (ROOT / 'docs/briefs/PAUSE').exists() and not (ROOT / 'queue/PAUSE').exists(), 'S4_ROOTREG_PAUSE')
    # The collected QSF is vendor-mutated (LAST_QUARTUS_VERSION). Use the
    # original pre-vendor source controls, never feed reports back as input.
    base = ROOT / 'artifacts/s4-diet-warm-p16-f0-v1/project'
    parent_manifest = json.loads((base / 'manifest.json').read_text())
    parent = json.loads((normal / 'parent-bundle.json').read_text())
    bundle = json.loads((normal / 'bundle.json').read_text())
    manifest = json.loads((normal / 'manifest.json').read_text())
    binding.need(bundle['parameters']['AW'] == 16 and bundle['parameters']['P'] == 16 and
                 bundle['parameters']['FIELD'] == 0, 'S4_ROOTREG_MATCHED_F0_FULL_ONLY')
    binding.need(parent['generated_sha256'] == parent_manifest['source_sha256'], 'S4_ROOTREG_EXACT_MEASURED_PARENT')
    binding.need(bundle['top'] == parent['top'] and bundle['geometry'] == parent['geometry'] and
                 bundle['parameters'] == parent['parameters'], 'S4_ROOTREG_MATCHED_PORT_CALENDAR')
    binding.need(all(manifest['sources']['rtl/' + name] == pin
                     for name, pin in bundle['generated_sha256'].items()), 'S4_ROOTREG_EXACT_NATIVE_RTL_JOIN')
    binding.need(all(hashlib.sha256((base / 'rtl' / name).read_bytes()).hexdigest() == pin
                     for name, pin in parent_manifest['source_sha256'].items()), 'S4_ROOTREG_PARENT_PROJECT_BYTES')
    binding.need(all(hashlib.sha256((base / name).read_bytes()).hexdigest() == pin
                     for name, pin in parent_manifest['control_sha256'].items()), 'S4_ROOTREG_ORIGINAL_PARENT_CONTROL_PINS')
    project = output / 'project'
    (project / 'rtl').mkdir(parents=True)
    for name, text in bundle['files'].items():
        (project / 'rtl' / name).write_text(text)
    qsf = (base / 'probe.qsf').read_text()
    binding.need('LAST_QUARTUS_VERSION' not in qsf, 'S4_ROOTREG_NO_VENDOR_INPUT_METADATA')
    old, new = binding.OLD_BF + '.sv', binding.NEW_BF + '.sv'
    binding.need(qsf.count('rtl/' + old) == 1 and old not in bundle['files'], 'S4_ROOTREG_QSF_LEAF_REPLACEMENT')
    controls = {name: (base / name).read_text() for name in ('probe.qpf', 'probe.sdc', 'run.tcl')}
    controls['probe.qsf'] = qsf.replace('rtl/' + old, 'rtl/' + new)
    if 'comm_delay_packed' in bundle:
        old_delay, new_delay = packed.OLD + '.sv', packed.NEW + '.sv'
        binding.need(qsf.count('rtl/' + old_delay) == 1 and old_delay not in bundle['files'], 'S4_ROOTREG_PACKED_QSF_JOIN')
        controls['probe.qsf'] = controls['probe.qsf'].replace('rtl/' + old_delay, 'rtl/' + new_delay)
    restored = controls['probe.qsf'].replace('rtl/' + new, 'rtl/' + old)
    if 'comm_delay_packed' in bundle:
        restored = restored.replace('rtl/' + new_delay, 'rtl/' + old_delay)
    binding.need(restored == qsf, 'S4_ROOTREG_ONLY_SOURCE_LIST_CONTROL_DELTA')
    for name, text in controls.items():
        (project / name).write_text(text)
    fit_manifest = dict(parent_manifest)
    fit_manifest.update(schema='s4-root-outputreg-field-sizing-v1', source_sha256=bundle['generated_sha256'],
        control_sha256={name: hashlib.sha256(text.encode()).hexdigest() for name, text in controls.items()},
        source_dependencies_sha256=bundle['source_sha256'], geometry=bundle['geometry'],
        root_weight_outputreg=bundle['root_weight_outputreg'],
        qualified_native_manifest=dict(path=str(normal / 'manifest.json'),
            sha256=hashlib.sha256((normal / 'manifest.json').read_bytes()).hexdigest()),
        native_prerequisite=json.loads((normal / 'global-ticket-v1.json').read_text())['id'],
        scope='One P16 CORR2/COMM1/MONT1 field: paired root-ROM output/BF weight co-retiming, exact parent10ns/seed1/Azure4. Measure actual RAM output-register inference, LAB/register/resources and setup; no whole GO or clock claim.',
        promotion_allowed=False)
    if 'comm_delay_packed' in bundle:
        fit_manifest.update(comm_delay_packed=bundle['comm_delay_packed'],
            scope='Source-specific packed+root co-retiming field, exact composed parent10ns/seed1/Azure4. Separate ingredient wins do not establish additive savings; own full native/physical measurement required. No whole GO.')
    (project / 'manifest.json').write_text(json.dumps(fit_manifest, indent=2) + '\n')
    matched = dict(status='EXACT_FROZEN_PARENT_REUSED_NOT_RERUN', project=str(base),
        receipt='queue/standing-fit-state/terminal/s4-diet-warm-p16-f0-v1/receipt.json',
        parent_sources_exact=True, controls_only_source_list_changed=True, clock_period_ns=10, seed=1,
        known_parent=dict(needed_ALM=97045, placed_ALM=118744, registers=168747, LAB=15774,
                          MLAB=272, M20K=551, DSP=314, setup_ns=-0.509),
        source_delta=bundle['root_weight_outputreg']['changes'],
        scope='Resource/timing comparison requires actual candidate measurement; ROM output-register absorption is not established by source or native simulation.')
    (output / 'matched-parent.json').write_text(json.dumps(matched, indent=2) + '\n')
    return dict(project=str(project), native_source_gate=fit_manifest['native_prerequisite'],
                rtl=len(bundle['rtl_sources']), parent_map_exact=True)


def prepare(output, aw, field, budget, after=(), packed_delay=0):
    output = Path(output).resolve()
    binding.need(not output.exists(), 'S4_ROOTREG_FRESH_OUTPUT')
    binding.need(not (ROOT / 'docs/briefs/PAUSE').exists() and not (ROOT / 'queue/PAUSE').exists(), 'S4_ROOTREG_PAUSE')
    binding.need(aw in (8, 16) and field in (0, 1, 2), 'S4_ROOTREG_NATIVE_GEOMETRY')
    binding.need(type(packed_delay) is int and packed_delay in (0, 1), 'S4_ROOTREG_PACKED_LITERAL_FLAG')
    parent = fields.prepare(1 << aw, 16, field, mode='warm', allow_full_constants=aw == 16,
                            corr_serial_bfs=2, comm_stage_shared_mlab=1, mont_factored=1)
    bundle = binding.bind(packed.bind(parent) if packed_delay else parent)
    geometry = bundle['geometry']
    interval = geometry['warm_interval']
    rows = geometry['rows']
    ledgers = [lease_ledger(starts, geometry['sink_accept'], rows)
               for starts in ([0], [0, interval], [0, interval + 16])]
    binding.need(all(not ledger['rejected'] for ledger in ledgers), 'S4_ROOTREG_LEASE_CALENDAR')
    cpp, header = compile_bench(bundle, field)
    marker = f'{"S4_PACKED_ROOT_FIELD_PASS" if packed_delay else "S4_ROOT_OUTPUTREG_FIELD_PASS"} aw={aw} p=16 field={field}'
    binding.need(cpp.count('S4_SHARED_AW16_PASS') == 1, 'S4_ROOTREG_NORMAL_FOOTER')
    cpp = cpp.replace('S4_SHARED_AW16_PASS', marker)
    counts = dict(cases=9, frames=9, physical_rows=9 * rows, physical_words=9 * (1 << aw),
                  eligible_rows=7 * rows, commits=7 * rows,
                  peak_owners=max(ledger['peak'] for ledger in ledgers))
    cpp_name = 'rtl/tb/root_outputreg_field.cpp'
    files = {'rtl/' + name: text.encode() for name, text in bundle['files'].items()}
    files.update({cpp_name: cpp.encode(), 'rtl/tb/s4_full_config_v1.h': header.encode(),
                  'rtl/tb/stream27_shared_reference_ntt_v1.h':
                      (ROOT / 'rtl/tb/stream27_shared_reference_ntt_v1.h').read_bytes()})
    for path in bundle['source_dependencies']:
        files['lineage/' + path] = (ROOT / path).read_bytes()
    files['lineage/' + SELF] = Path(__file__).read_bytes()
    source = output / 'source/fpga'
    for name, raw in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    stamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    # Each geometry is a separately emitted design; this is its actual freeze.
    pins = {name: binding.sha(raw.decode()) for name, raw in files.items()}
    manifest = dict(schema='native-source-gate-v1', status='prepared_not_executed', host='UNBOUND',
        source_root=str(source), output_parent=str(output / 'UNBOUND_OUTPUT'), sources=pins,
        build=dict(top=bundle['top'], sv_sources=['rtl/' + name for name in bundle['rtl_sources']],
                   cpp_source=cpp_name, parameters={key: value for key, value in bundle['parameters'].items() if key != 'FIELD'},
                   cflags=['-std=c++17', '-O2', '-Werror=return-type'], runtime_threads=1),
        probe=dict(argv=['{exe}', '--runtime-probe'], expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)),
        steps=[dict(name='root-outputreg-field-normal', argv=['{exe}'], expected_returncode=0,
                    expected_stdout=marker + ' ' + ' '.join(f'{key}={value}' for key, value in counts.items()) + '\n', expected_stderr='')],
        scope='Own P16 CORR2/COMM1/MONT1 field; transform ROM+1 and removed BF weight register preserve E5/field calendars. Nine original independent-NTT cases, all tags/values/leases; no physical mapping or area claim.', promotion_allowed=False)
    manifest_path = output / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'bundle.json').write_text(json.dumps(bundle, indent=2) + '\n')
    (output / 'parent-bundle.json').write_text(json.dumps(parent, indent=2) + '\n')
    sys.path.insert(0, str(ROOT))
    from tools import native_class_package_v2 as package
    family = 'packed-root' if packed_delay else 'root-outreg'
    worker = f's4-{family}-aw{aw}-p16-f{field}-normal-01-v1'
    job = f's4-{family}-aw{aw}-p16-f{field}-normal-q1-v1'
    packet = output / 'packet-01'
    package.prepare(manifest_path, source, 'gcp-c4d-static01-v1', worker, 'run', packet, Path(budget).resolve())
    native = json.loads((packet / 'ticket.json').read_text())
    template_path = ROOT / 'results/throughput-20260929/trackS-p16-packed-delay-v1/normal-ready-v1/global-ticket-v1.json'
    ticket = json.loads(template_path.read_text())
    item = ticket['packages'][0]
    item.update(archive=str(packet / 'package.tar.gz'), sha256=binding.sha((packet / 'package.tar.gz').read_bytes().hex()),
                ticket_sha256=binding.sha((packet / 'ticket.json').read_text()), manifest_sha256=native['manifest_sha256'],
                worker_id=worker, native_root=native['native_root'])
    # Binary archive hashing is ordinary SHA256, not a hex-text digest.
    import hashlib
    item['sha256'] = hashlib.sha256((packet / 'package.tar.gz').read_bytes()).hexdigest()
    candidate = f's4-{family}-aw{aw}-p16-f{field}-v1'
    ticket.update(id=job, candidate_id=candidate, created=stamp, est_minutes=10,
                  source_gate=dict(scope=manifest['scope'], promotion_allowed=False))
    snapshot = {name: pin for name, pin in pins.items() if name.endswith('.sv')}
    ticket['rtl_readiness'] = dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=candidate,
        source_snapshot=snapshot, candidate_source_sha256=binding.sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':'))),
        rtl_ready_at_utc=stamp)
    if after:
        ticket['after'] = list(after)
    path = output / 'global-ticket-v1.json'
    path.write_text(json.dumps(ticket, indent=2) + '\n')
    return dict(id=job, input=str(path), rtl_ready_at_utc=stamp, counts=counts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--aw', type=int, choices=(8, 16), required=True)
    parser.add_argument('--field', type=int, choices=(0, 1, 2), default=0)
    parser.add_argument('--budget', required=True)
    parser.add_argument('--after', action='append', default=[])
    parser.add_argument('--packed-delay', type=int, choices=(0, 1), default=0)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.aw, args.field, args.budget, args.after, args.packed_delay), indent=2))
