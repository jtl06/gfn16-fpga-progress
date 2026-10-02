"""Consume retained serial1000 native evidence; never generates or runs a case.

Pure source/artifact/log/array comparison on the coordinator. The full-N GMP
arithmetic remains the recorded pinned Linux worker validation, not a Mac
recalculation. Only six frozen metadata/log functions are compiled for replay.
"""
import argparse
import ast
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
ID = 'soak-t5b-aw16-continuous1000-q3-v4'
CASE = '2730e05de298ecbf5d7125acb7d6859b581b21ed8c84fb1bbfd7d3aaccd007ba'
PARENT_SHA = '1a1a67980f1744be70c0b089dcdf7e20c4cdd8714cbac26bd5798c28abbcc011'
AUDIT_SHA = 'bdc8295fc1dac155b28635b915c39c80b24e121001de9c6a8cba595de327bec2'
BASE = 'reference/core27_crtmont_soak_v1.py'
BASE_SHA = '8075e2033a01b09b9bbc344b72f23df4ebbc90b8489caadfbd0546e6f3bcfe3a'
CORE = 'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv'
CORE_SHA = '704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7'
BENCH = 'rtl/tb/core27_t5b_soak_v1.cpp'
BENCH_SHA = 'c4972670a55bbb0c7b039e7a0175ee6918e5a95f3e0dd4a5a96c7dbc7175fab7'
HEADER = 'rtl/tb/native_runtime_context_v1.h'
HEADER_SHA = 'afd27444d1b4c991d11c84482db08f2fcef62757968e96ac83c5d44e55622f90'
GATE = 'tools/native_gate_receipt_v1.py'
GATE_SHA = '131d4e6b9cafd424935094c3ec50ef81d7c2e8024efae6a5d37ce20d0c5a29d3'
CHUNK_GATE = 'results/throughput-20260929/soak-t5b-dependent-sequence-v1/chunk-coverage-gate-v1.json'
CHUNK_GATE_SHA = '630d1414fa7d29f5b5d6ee0cc849ec222af73d1a9071b8a814b050678ef203f9'
RUNTIME_SHA = '84fb40c8e6452d4b660d9302e83584dd3c4761aa6219495e57f2df582401cf0b'
GENERATION_SHA = '51bf3a1c72d278eca68ceb21deedae5dc430369e9c556c90d018aad3e611e62b'
TERMINAL_SHA = '15784cf8b17ef056e97fdb09cfb6cad9ee329a8860c24f316d2a802a9f35ba1e'
PACKAGE_SHA = '9be4568b6927ae3b8c5d3dc7ea7e67ce2ebcc68440eaa12673d06d1bc8317d4a'
MANIFEST_SHA = '4ad40cd89663aee07557aacdbf3bcc92e451d667cf8447e76b215b72c83212b0'
CONTROL_SHA = '520394db470da23043cdf36644da8efc3b0ec4acd4f9dc69ead5cf0a049f19bb'
REPORT_SHA = '67eed0e87de7d9880dc10aa6c198536b13e2e25f0a1ba8080d45c7535f9209f2'
MACHINE_GATE_SHA = '36ef28ca2db03196ebbfedc9690cbe9751fef97fcf2cb45d471f8aeb92d55d47'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def no_gmp():
    need(not any(k == 'gmpy2' or k.startswith('gmpy2.') for k in sys.modules), 'metadata-only process: no GMP import')


def load_gate():
    need(sha(ROOT / GATE) == GATE_SHA, 'frozen raw-artifact gate helper')
    spec = importlib.util.spec_from_file_location('_serial1000_artifact_gate', ROOT / GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_log_parser():
    need(sha(ROOT / BASE) == BASE_SHA, 'frozen pure log parser source')
    raw = (ROOT / BASE).read_text()
    anchor = "lineage='promoted-crtmont'"
    need(raw.count(anchor) == 1, 'unchanged sole T5b metadata lineage substitution')
    raw = raw.replace(anchor, "lineage='promoted-t5b'", 1)
    names = {'require', 'canonical', 'make_plan', 'check_plan', 'check_oracle', 'validate_rows'}
    nodes = [node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name in names]
    need({n.name for n in nodes} == names, 'six exact metadata/log functions')
    namespace = dict(hashlib=hashlib, json=json, PARENT_SHA=PARENT_SHA, AUDIT_SHA=AUDIT_SHA)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '[frozen-metadata-log-replay-only]', 'exec'), namespace)
    return namespace['validate_rows']


def verify_phases(steps):
    need(len(steps) == 1000, 'all1000 phase records')
    for index, row in enumerate(steps):
        expected = dict(cycles=41674 if index == 0 else 28826,
            conversion=4105 if index == 0 else 0, roots=8743 if index == 0 else 0,
            ntt=20558, crt=4113, carry=4155, profile_loads=1 if index == 0 else 0,
            profile_hits=0 if index == 0 else 1)
        need(row['step'] == index + 1 and all(type(row[k]) is int and row[k] == v for k, v in expected.items()),
             'exact cold/warm/cycle/cache phase record')
    return dict(cold_cycles=41674, warm_cycles=28826, total_cycles=sum(s['cycles'] for s in steps),
                cache_load_events=sum(s['profile_loads'] for s in steps), warm_cache_hits=sum(s['profile_hits'] for s in steps))


def verify_terminal(props, report):
    expected = dict(Result='success', ExecMainStatus='0', MainPID='0', ControlGroup='',
        InvocationID='4606dc14059b42b0b2e90fbfe3a648c4', AllowedCPUs='0-1',
        CPUQuotaPerSecUSec='2s', MemoryMax='8589934592', MemorySwapMax='0',
        RuntimeMaxUSec='3h', TimeoutStopUSec='15s')
    need(all(props.get(k) == v for k, v in expected.items()) and bool(props['ExecMainExitTimestamp']),
         'exact successful invocation, terminal cgroup and resource caps')
    limits = report['limits']
    need(report['host'] == 'gfn16-pilot-c4d' and limits['affinity'] == [0, 1]
         and limits['physical_cores'] == [[0, 0], [0, 1]]
         and limits['cpu_max'] == ['200000', '100000']
         and limits['memory_max_bytes'] == 8589934592 and limits['swap_max_bytes'] == 0,
         'observed worker physical pair and memory/CPU limits')
    expected_bounds = dict(command_seconds=10450, ancillary_command_seconds=1800,
        overall_seconds=10700, outer_seconds=10800, stop_grace_seconds=15,
        lock_wait_seconds=1800, memory_bytes=8589934592)
    need(all(type(report['bounds'].get(k)) is int and report['bounds'][k] == v
             for k, v in expected_bounds.items()), 'source-bound finite duration shape')


def verify_worker_validation(validation, parsed, oracle_sha):
    fields = ('case_id', 'segment', 'operations', 'doubles', 'readbacks', 'cycles',
              'evidence_class', 'continuous_chain_log_contract', 'checkpoint_residue_sha256')
    need(all(validation.get(k) == parsed[k] for k in fields), 'worker and raw log exact typed contract')
    runtime = validation['auxiliary_reference_runtime']
    need(validation['status'] == 'passed_soak_segment_boundary_replay'
         and validation['uninterrupted_1000_square_rtl'] is True
         and validation['independent_gmpy2_boundary_replay'] is True
         and validation['native_qualification_allowed'] is True
         and validation['lineage'] == 'promoted-t5b'
         and validation['parent_manifest_sha256'] == PARENT_SHA
         and validation['oracle_sha256'] == oracle_sha
         and runtime['status'] == 'passed_exact_auxiliary_reference_runtime'
         and runtime['runtime_manifest_sha256'] == RUNTIME_SHA
         and runtime['files'] == 21 and runtime['package_version'] == '2.3.1'
         and runtime['python_sha256'] == 'be9a2a5eada8c89c1c399fdfb8397179e877c20d8db0739c802f726d4d0e69fd',
         'recorded native independent GMP qualification')


def archive_pins(path):
    result = {}
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            need(member.isfile() and not member.issparse() and member.name not in result
                 and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts, 'safe unique regular archive member')
            with archive.extractfile(member) as stream:
                result[member.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return result


def consume(ticket_file):
    no_gmp()
    ticket_file = Path(ticket_file).resolve()
    need(sha(ticket_file) == TERMINAL_SHA, 'frozen selected terminal queue bytes')
    ticket = json.loads(ticket_file.read_text())
    need(ticket['id'] == ID and ticket['result']['status'] == 'needs_independent_review', 'exact terminal serial1000 ticket')
    props = ticket['result']['properties']
    need(props['Result'] == 'success' and props['ExecMainStatus'] == '0' and props['MainPID'] == '0'
         and props['ControlGroup'] == '' and props['InvocationID'] == '4606dc14059b42b0b2e90fbfe3a648c4'
         and bool(props['ExecMainExitTimestamp']), 'actual successful invocation, no live cgroup')
    package = ticket['package']; directory = Path(package['archive']).parent
    need(package['profile'] == 'gcp-c4d-static01-v1'
         and sha(package['archive']) == package['sha256'] == PACKAGE_SHA, 'selected immutable GCP01 package')
    manifest_file = directory / 'manifest.json'; native_ticket = directory / 'ticket.json'
    need(sha(manifest_file) == package['manifest_sha256'] == MANIFEST_SHA
         and sha(native_ticket) == package['ticket_sha256'] == CONTROL_SHA, 'prepared control identities')
    with tarfile.open(package['archive'], 'r:gz') as archive:
        for name, pin in (('manifest.json', package['manifest_sha256']), ('ticket.json', package['ticket_sha256'])):
            need(hashlib.sha256(archive.extractfile(name).read()).hexdigest() == pin, 'immutable archive control byte identity')
    manifest = json.loads(manifest_file.read_text()); control = json.loads(native_ticket.read_text())
    need(manifest['host'] == 'gfn16-pilot-c4d' and manifest['build']['parameters'] == dict(AW=16, NTT_LANES=64)
         and manifest['sources'][CORE] == CORE_SHA and manifest['sources'][BENCH] == BENCH_SHA
         and manifest['sources'][HEADER] == HEADER_SHA and manifest['sources'][BASE] == BASE_SHA
         and manifest['sources']['soak/runtime.json'] == RUNTIME_SHA
         and manifest['soak']['case_id'] == CASE and manifest['soak']['segment'] == 'continuous'
         and manifest['soak']['reference_generation_sha256'] == GENERATION_SHA
         and len(manifest['steps']) == 1 and manifest['steps'][0]['validator']['config'] == dict(negative='none'), 'unchanged normal-only T5b serial geometry/source')
    evidence = Path(ticket['result']['evidence']); output = evidence / 'output/native'
    report_file = output / 'report.json'; report = json.loads(report_file.read_text())
    verify_terminal(props, report)
    helper = load_gate(); replayed_gate = helper.validate_result(helper.make_contract(ID, manifest_file), report_file, id=ID)
    link = ticket['dependency_gate']; gate_file = Path(link['path'])
    need(link['status'] == 'PASS_expected_contracts' and sha(gate_file) == link['sha256'] == MACHINE_GATE_SHA
         and json.loads(gate_file.read_text()) == replayed_gate
         and sha(report_file) == ticket['result']['queue_report']['report_sha256'] == REPORT_SHA,
         'machine gate exact raw source/artifact replay')
    need(report['probe'] == dict(context_threads=1, model_threads=1, expected_threads=1), 'actual serial runtime probe')
    need(archive_pins(output / 'sources.tar.gz') == report['sources'], 'complete archived source replay')
    generated = archive_pins(output / 'generated-sources.tar.gz')
    need(generated == report['generated_source_sha256'], 'generated source archive replay')
    with gzip.open(output / 'model.gz', 'rb') as stream:
        executable = hashlib.file_digest(stream, 'sha256').hexdigest()
    need(executable == report['executable_sha256'], 'preserved actual native ELF replay, not execution')
    source = directory / 'capture/source/fpga'
    callback = manifest['steps'][0]['validator']; oracle_file = source / callback['assets']['oracle']
    oracle = json.loads(oracle_file.read_text())
    need(sha(oracle_file) == manifest['sources'][callback['assets']['oracle']] ==
         'f9091c7fb7943295312e7206c1a11dacfd03999d898f150115909a6d73359851', 'original full independent Linux oracle bytes')
    normal = next(s for s in report['steps'] if s['name'] == 'soak-normal')
    stdout = (output / normal['log']).read_text(); stderr = (output / normal['stderr_log']).read_text()
    parsed = frozen_log_parser()(stdout, stderr, normal['returncode'], {'negative': 'none'}, oracle)
    rows = [(s.split(' ', 1)[0], json.loads(s.split(' ', 1)[1])) for s in stdout.splitlines()]
    steps = [r for name, r in rows if name == 'SOAK_STEP']; checks = [r for name, r in rows if name == 'SOAK_CHECK']
    phases = verify_phases(steps); footer = rows[-1][1]
    need(parsed['continuous_chain_log_contract'] is True and footer['resets'] == 1 and footer['loaded_digits'] == 65536
         and footer['cold'] == 1 and footer['warm'] == 999 and footer['doubles'] == 488
         and phases['total_cycles'] == 28838848, 'complete retained-state footer')
    validation = report['validations']['soak-normal']
    verify_worker_validation(validation, parsed, sha(oracle_file))
    bench = (source / BENCH).read_text(); begin = bench.index('for (unsigned k = 0; k < bits.size(); ++k)')
    loop = bench[begin:bench.index('require(next_check == count', begin)]
    need(sha(source / BENCH) == BENCH_SHA and bench.count('Core d{&context}') == 1
         and 'd.rst_n' not in loop and 'd.load_we' not in loop, 'source-bound one model/no mid-loop reset or host reload')
    need(sha(ROOT / CHUNK_GATE) == CHUNK_GATE_SHA, 'separate completed ten-chunk receipt')
    chunks = json.loads((ROOT / CHUNK_GATE).read_text())
    need(chunks['combination']['boundary_residue_sha256'] == parsed['checkpoint_residue_sha256'], 'continuous and chunk boundaries agree without evidence conflation')
    no_gmp()
    return dict(schema='T5b-serial-continuous1000-native-consumption-v1',
        status='PASS_serial_retained_native1000_consumption_pending_independent_review', ticket_id=ID,
        host=report['host'], profile=package['profile'], invocation=props['InvocationID'],
        paths=dict(terminal_queue=str(ticket_file.relative_to(ROOT)), packet=str(directory.relative_to(ROOT)),
                   report=str(report_file.relative_to(ROOT)), gate=str(gate_file.relative_to(ROOT))),
        pins=dict(archive=package['sha256'], ticket=package['ticket_sha256'], manifest=sha(manifest_file),
            report=sha(report_file), machine_gate=link['sha256'], terminal_queue=sha(ticket_file),
            stdout=normal['sha256'], stderr=normal['stderr_sha256'], executable=executable,
            core=CORE_SHA, bench=BENCH_SHA, context_header=HEADER_SHA, oracle=sha(oracle_file),
            reference_generation=manifest['soak']['reference_generation_sha256'], runtime_manifest=RUNTIME_SHA,
            chunk_combination=CHUNK_GATE_SHA, consumer=sha(Path(__file__))),
        replay=dict(native_gate='PASS_expected_contracts', artifacts=len(report['artifacts']), sources=len(report['sources']),
            generated_members=len(generated), compiled_sv_members=len(manifest['build']['sv_sources']),
            all_artifacts_sources_generated_elf_rehashed=True, model_steps=len(steps), **phases,
            conditional_doubles=footer['doubles'], full_word_readbacks=[dict(step=c['step'], words=len(c['digits']),
                residue_sha256=parsed['checkpoint_residue_sha256'][str(c['step'])]) for c in checks],
            total_readback_words=sum(len(c['digits']) for c in checks), one_reset_one_load_no_mid_loop_reset_reload=True,
            reset_reload_evidence='Exact pinned c497 driver creates one context/model and resets/loads only before the square loop; all cold/warm/cache rows and footer corroborate it. No new waveform instrumentation.',
            probe=report['probe'], native_linux_gmp_boundary_replay=True, gmp_package_version='2.3.1',
            coordinator_GMP_imported=False, coordinator_numeric_generation=False),
        build_key=control['build_key'], tool_sha256=report['tool_sha256'], runtime_limits=report['limits'],
        duration_bounds=report['bounds'], terminal_properties=props, lint_class_counts=report['lint_admission']['class_counts'],
        metrics=dict(model_wall_seconds=normal['seconds'], model_user_seconds=normal['user_seconds'],
            model_system_seconds=normal['system_seconds'], worker_wall_seconds=report['seconds'],
            build_wall_seconds=next(s['seconds'] for s in report['steps'] if s['name'] == 'build'),
            unit_wall_seconds=(int(props['ExecMainExitTimestampMonotonic'])-int(props['ExecMainStartTimestampMonotonic']))/1e6,
            unit_cpu_seconds=int(props['CPUUsageNSec'])/1e9, unit_memory_peak_bytes=int(props['MemoryPeak']),
            cumulative_children_peak_rss_kib=normal['cumulative_children_peak_rss_kib'],
            isolated_model_peak_rss_measured=False, scratch_peak_allocated_bytes=report['scratch_peak_allocated_bytes'],
            scope='One GCP serial run; unit CPU/RAM include compile/reference. RUSAGE_CHILDREN RSS is cumulative, not an isolated model peak. No cross-host or serial/threaded speed ratio.'),
        separate_threaded_result_not_consumed=True, both_chunked_and_serial_uninterrupted_native_gates_passed=True,
        promotion_allowed=False, limitations=['Not FPGA-board or full-size PRP runtime evidence.',
            'Pending independent full evidence review and advisor acceptance; no clock or broader threading claim.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ticket', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(consume(args.ticket), indent=2))
