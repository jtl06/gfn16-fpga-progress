"""Read-only single-sample matched2/4/8 T5b comparison, no numeric rerun.

Reuse the frozen raw-artifact/source/output/build/resource/wait4 replay. Only
closed accounting freshness snapshots may differ; every actual sample uses the
same eight-core affinity/quota/RAM/j2/compiler/runtime/short case. This is not
a full-campaign speed guarantee or production/arbitrary-profile admission.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import types

HERE = Path(__file__).resolve().parent
BASE_SHA = 'e9b2f1eb8f1d8c52f17f4356f3c0112597bf373c5740aede9c2f80a66b5f6905'
RUNTIME_SHA = '75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1'
ROLE_SOURCE = 'results/throughput-20260929/core27-t5b-thread-wide-source-v1/t5b-cold-warm-threads2-manifest.json'
ROLE_SHA = '90ddef810a9ed387c91a1924b20469d4e29613eeeb7bcce5e355d0a476bff3e3'
PROVIDER = re.compile(r'results/throughput-20260929/core27-t5b-thread-wide-source-v1/execution-inputs-v[1-9][0-9]*/provider\.json')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(name, pin):
    path = HERE / name
    need(path.is_file() and not path.is_symlink() and sha(path) == pin, 'exact wide comparison dependency')
    spec = importlib.util.spec_from_file_location('_wide_compare_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def role_equal(a, b):
    role_path = HERE.parent / ROLE_SOURCE
    need(sha(role_path) == ROLE_SHA, 'exact61-member fixed-wide role')
    role = json.loads(role_path.read_text())['sources']
    runtime = load('native_threaded_wide_v1.py', RUNTIME_SHA)
    need(a.get('budget_source_members') == b.get('budget_source_members') == role, 'unchanged original61-role identity')
    expected = dict(role, **runtime.PINS, **{runtime.SELF: RUNTIME_SHA})
    for name, pin in expected.items():
        need(a['sources'].get(name) == b['sources'].get(name) == pin, 'unchanged role/runtime/profile source: ' + name)
    differences = {name for name in set(a['sources']) | set(b['sources']) if a['sources'].get(name) != b['sources'].get(name)}
    need(all(PROVIDER.fullmatch(name) for name in differences), 'only authenticated accounting freshness variation')
    for manifest in (a, b):
        need(sum(bool(PROVIDER.fullmatch(name)) for name in manifest['sources']) == 1, 'one closed provider snapshot per sample')
        need(all(name in role for name in manifest['build']['sv_sources'] + [manifest['build']['cpp_source']]), 'all compiled sources in immutable role')
    return True


def sample(manifest_path, report_path, count):
    frozen = load('native_thread_pilot_compare_v1.py', BASE_SHA)
    runtime = load('native_threaded_wide_v1.py', RUNTIME_SHA)
    inherited = runtime.base()
    facade = types.SimpleNamespace(validate_threaded=runtime.validate_threaded, profile=runtime.profile,
        load=inherited.load, IDENTITY_SHA=inherited.IDENTITY_SHA)
    def dependency(name):
        return facade if name == 'native_threaded_class_v1.py' else frozen.load(name)
    namespace = dict(frozen.sample.__globals__, load=dependency)
    replay = types.FunctionType(frozen.sample.__code__, namespace, frozen.sample.__name__)
    manifest, selected, report, measured = replay(manifest_path, report_path, count)
    need(count in (2, 4, 8) and report['compile_workers'] == 2, 'measured fixed-wide counts and compilerworkers')
    build = next(row for row in report['steps'] if row['name'] == 'build')
    usage = build['native_child_usage']
    need(usage['schema'] == 'native-wait4-child-usage-v1' and usage['returncode'] == 0
         and type(usage['pid']) is int and usage['pid'] > 0, 'recorded Linux build child usage')
    user = frozen.finite(usage['user_seconds'], 'compile user CPU')
    system = frozen.finite(usage['system_seconds'], 'compile system CPU')
    measured.update(compile_cpu_seconds=frozen.finite(user + system, 'compile CPU', True),
        compile_child_peak_rss_kib=frozen.finite(usage['peak_rss_kib'], 'compile peak RSS', True),
        allocated_physical_cores=8, compile_workers=2, memory_cap_bytes=selected['memory_bytes'],
        cpu_quota_percent=selected['cpu_quota_percent'], observed_l3=selected['observed_l3'])
    return manifest, selected, report, measured


def compare(two_manifest, two_report, four_manifest, four_report, eight_manifest, eight_report):
    samples = [sample(manifest, report, count) for manifest, report, count in
               ((two_manifest, two_report, 2), (four_manifest, four_report, 4), (eight_manifest, eight_report, 8))]
    first, first_profile, first_report, baseline = samples[0]
    builds = []
    for manifest, selected, report, measured in samples:
        role_equal(first, manifest)
        need(manifest['host'] == first['host'] and manifest['cpu_profile'] == first['cpu_profile']
             and manifest['steps'] == first['steps'] and report['tool_sha256'] == first_report['tool_sha256']
             and selected['runtime_allocation'] == first_profile['runtime_allocation']
             and selected['hashes'] == first_profile['hashes'], 'same actual host/values/cycles/tool/allocation')
        build = dict(manifest['build']); build.pop('runtime_threads')
        build['cflags'] = [flag for flag in build['cflags'] if not flag.startswith('-DGFN16_RUNTIME_THREADS=')]
        builds.append(build)
    need(all(build == builds[0] for build in builds), 'build delta only exact thread configuration')
    measured = [value[3] for value in samples]
    return dict(schema='gfn16-t5b-fixed-wide-native-comparison-v1', status='PASS_matched_native2_4_8_single_sample',
        core_sha256=first_report['sources'][load('native_thread_pilot_compare_v1.py', BASE_SHA).CORE],
        observed_samples=measured, cycle_counts=[41674, 28826],
        two_over_four_model_wall_ratio=baseline['wall_seconds'] / measured[1]['wall_seconds'],
        two_over_eight_model_wall_ratio=baseline['wall_seconds'] / measured[2]['wall_seconds'],
        four_over_two_model_cpu_ratio=measured[1]['cpu_seconds'] / baseline['cpu_seconds'],
        eight_over_two_model_cpu_ratio=measured[2]['cpu_seconds'] / baseline['cpu_seconds'],
        matched_allocation='one actual observed L3 domain, identical8physical/800percent/8GiB/j2 per sample',
        scope='one cold and one consecutive warm full-AW16 T5b square, both controls/fullreadbacks; not repeated benchmark',
        memory_scope='Linux wait4 per-child/descendant peaks; whole-unit/cgroup peak is separately collected',
        four_core_profile_admission=False, long_campaign_admission=False, promotion_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for count in ('two', 'four', 'eight'):
        parser.add_argument('--' + count + '-manifest', type=Path, required=True)
        parser.add_argument('--' + count + '-report', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.two_manifest, args.two_report, args.four_manifest, args.four_report, args.eight_manifest, args.eight_report), indent=2))
