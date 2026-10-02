"""Read-only matched promoted-T5b pilot receipt; no arithmetic or execution.

Both fresh source-built reports must pass the existing raw-artifact native gate,
share physical affinity/caps/tools/source bytes, and reproduce the qualified
cold/warm stdout exactly. Report one observed finite sample, not production
speedup, eight-thread admission, clock or FPGA throughput evidence.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = {'native_gate_receipt_v1.py': '131d4e6b9cafd424935094c3ec50ef81d7c2e8024efae6a5d37ce20d0c5a29d3',
        'native_threaded_class_v1.py': '4633c3ca20a6560fdeed35590922a01de8cd572b1bf127e3d2faa4a96734751f'}
STDOUT_SHA = '48b89f454ca5d5a1bcaa23dd4ae6815df55c3f01f062d3b3ecdc60aed174e0ee'
CORE = 'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv'
CORE_SHA = '704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(name):
    path = HERE/name
    need(sha(path) == PINS[name], 'exact pilot comparison dependency')
    spec = importlib.util.spec_from_file_location('_compare_'+path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finite(value, name, positive=False):
    need(type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0),
         'finite measured '+name)
    return value


def sample(manifest_path, report_path, count):
    manifest_path, report_path = Path(manifest_path), Path(report_path)
    manifest, report = (json.loads(path.read_text()) for path in (manifest_path, report_path))
    runtime = load('native_threaded_class_v1.py')
    need(runtime.validate_threaded(manifest) == count, 'ordered one/two pilot count')
    selected = runtime.profile(manifest['cpu_profile'])
    gate = load('native_gate_receipt_v1.py')
    contract = gate.make_contract('promoted-t5b-p3-threads'+str(count), manifest_path)
    receipt = gate.validate_result(contract, report_path, id='promoted-t5b-p3-threads'+str(count))
    need(receipt['status'] == 'PASS_expected_contracts', 'actual raw artifact native gate PASS')
    need(manifest['sources'].get(CORE) == CORE_SHA and report['model_threads'] == report['context_threads'] == count,
         'promoted T5b exact runtime identity')
    identity = runtime.load('build_identity_v2.py', runtime.IDENTITY_SHA).build_identity(manifest, selected)
    need(report['exact_build_identity'] == identity, 'report exact thread/source/tool/allocation build identity')
    need(report['limits']['affinity'] == selected['cpus'] and report['limits']['physical_cores'] == selected['runtime_allocation']['physical_cores']
         and report['limits']['memory_max_bytes'] == selected['memory_bytes'] and report['limits']['swap_max_bytes'] == 0
         and report['limits']['cpu_max'][0] == str(selected['cpu_quota_percent']*1000)
         and report['limits']['cpu_max'][1] == '100000', 'actual exact affinity/physical/cgroup caps')
    need(len(manifest['steps']) == 1 and manifest['steps'][0]['name'] == 't5b-cold-warm'
         and hashlib.sha256(manifest['steps'][0]['expected_stdout'].encode()).hexdigest() == STDOUT_SHA,
         'reviewed complete two-square cycle/readback expectation')
    step = next(row for row in report['steps'] if row['name'] == 't5b-cold-warm')
    need(step['returncode'] == 0 and step['error'] is None and step['sha256'] == STDOUT_SHA, 'exact measured matched stdout')
    usage = step['native_child_usage']
    need(usage['schema'] == 'native-wait4-child-usage-v1' and usage['returncode'] == 0
         and type(usage['pid']) is int and usage['pid'] > 0, 'reaped exact Linux child usage')
    user = finite(usage['user_seconds'], 'user CPU')
    system = finite(usage['system_seconds'], 'system CPU')
    measured = dict(threads=count, manifest_sha256=sha(manifest_path), report_sha256=sha(report_path),
        build_key=identity['build_key'], executable_sha256=report['executable_sha256'],
        host=manifest['host'], profile=manifest['cpu_profile'], affinity=report['limits']['affinity'],
        physical_cores=report['limits']['physical_cores'], wall_seconds=finite(step['seconds'], 'wall', True),
        user_seconds=user, system_seconds=system, cpu_seconds=finite(user+system, 'CPU', True),
        peak_rss_kib=finite(usage['peak_rss_kib'], 'Linux child peak RSS', True),
        compile_wall_seconds=finite(next(row for row in report['steps'] if row['name']=='build')['seconds'], 'build wall', True),
        stdout_sha256=step['sha256'])
    return manifest, selected, report, measured


def compare(one_manifest, one_report, two_manifest, two_report):
    a, ap, ar, am = sample(one_manifest, one_report, 1)
    b, bp, br, bm = sample(two_manifest, two_report, 2)
    need(a['sources'] == b['sources'] and a['host'] == b['host'] and a['cpu_profile'] == b['cpu_profile'],
         'same actual host/profile and byte-identical source closure')
    need(a['steps'] == b['steps'] and ar['tool_sha256'] == br['tool_sha256']
         and ap['runtime_allocation'] == bp['runtime_allocation'] and ap['hashes'] == bp['hashes'],
         'same values/cycles/compiler/tool/runtime allocation')
    builds = []
    for manifest in (a, b):
        build = dict(manifest['build'])
        build.pop('runtime_threads')
        build['cflags'] = [value for value in build['cflags'] if not value.startswith('-DGFN16_RUNTIME_THREADS=')]
        builds.append(build)
    need(builds[0] == builds[1], 'build differs only exact thread macro/model flag')
    return dict(schema='promoted-t5b-thread-pilot-comparison-v1', status='PASS_matched_native_one_two_sample',
        core_sha256=CORE_SHA, observed_samples=[am, bm], cycle_counts=[41674, 28826],
        stdout_sha256=STDOUT_SHA, one_over_two_wall_ratio=am['wall_seconds']/bm['wall_seconds'],
        two_over_one_cpu_ratio=bm['cpu_seconds']/am['cpu_seconds'],
        native_thread_counts_qualified=[1, 2], higher_thread_admission=False,
        scope='one cold and one warm full-AW16 T5b square with exact full readbacks; single observed matched sample',
        memory_scope='Linux wait4 per-child peak RSS, not aggregate cgroup peak',
        limits=['Not a repeated benchmark, full soak, FPGA timing or throughput claim.',
                'Four/eight-thread production requires separate actual physical-profile/runtime qualification.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--one-manifest', type=Path, required=True)
    parser.add_argument('--one-report', type=Path, required=True)
    parser.add_argument('--two-manifest', type=Path, required=True)
    parser.add_argument('--two-report', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.one_manifest, args.one_report, args.two_manifest, args.two_report), indent=2))
