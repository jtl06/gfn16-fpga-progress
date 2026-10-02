"""Source-only matched six-worker F2 variants; no transfer or vendor launch."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import types

from fpga.tools import prefit_structural_guard_v1 as structural


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'artifacts/f2-registered-aw16-f0-plain-v1'
PINS = {
    'parent': '01d309d05aeef25c115ad716af18e9e92f67a69d2f55d77869e22986e1501165',
    'candidate': '134a15bd5b793d7d49d9693c2d0f60e1f831ae9083a8bb1e293caed002456544',
}
REFS = {
    'registered_AW5': ('results/throughput-20260929/f2-registered-native-independent-v1.json',
        'edc6bea7c2308b841bc643c5e94e85fb38aa267e35fd3b500d776f09e2fba23e'),
    'raw_AW16_F0': ('results/throughput-20260929/f2-aw16-native-independent-v1.json',
        '6c5daaefd237cd43b352c6bda31ab6cd699f493e5233282d10c212cc8f72d1fe'),
}
V6 = ROOT/'cloud/aws_fit_v6.py'
V6_PIN = 'ef66b020cf4317492c43a6baba6aea85f186e32dfdef6e7de7fa150a854e47a4'
PLAIN = ROOT/'cloud/plain_fit_v2.py'
PLAIN_PIN = '6ae141be72ccfdc77b2035d9b7347e5f555b37e94b4d7a7476ccfb3530d9883e'
WORKER_OLD = b'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4\n'
WORKER_NEW = b'set_global_assignment -name NUM_PARALLEL_PROCESSORS 6\n'
CONTROLS = {'probe.qsf', 'probe.qpf', 'probe.sdc', 'run.tcl'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def six_worker_verifier():
    """Reuse the two exact in-memory worker anchors used by plain_fit_v2."""
    structural.need(sha(V6) == V6_PIN and sha(PLAIN) == PLAIN_PIN,
                    'frozen v6/plain source verifier pins')
    text = V6.read_text()
    anchors = {
        "manifest['compile_processors']==4": "manifest['compile_processors']==6",
        "assignment('NUM_PARALLEL_PROCESSORS')==['4']":
            "assignment('NUM_PARALLEL_PROCESSORS')==['6']",
    }
    for old, new in anchors.items():
        structural.need(text.count(old) == 1, 'unique six-worker verifier anchor')
        text = text.replace(old, new)
    module = types.ModuleType('_f2_source_only_six_worker_v6')
    exec(compile(text, 'aws_fit_v6.py[source-only-workers6]', 'exec'), module.__dict__)
    return module


def prepare(output):
    structural.need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    output = Path(output)
    structural.need(output.is_absolute() and output.parent.resolve() == output.parent
                    and output.parent.is_dir() and not output.exists() and not output.is_symlink(),
                    'fresh canonical six-worker output')
    verifier = six_worker_verifier()
    for path, pin in REFS.values():
        structural.need(sha(ROOT/path) == pin, 'independent native context reference')

    # Admit BOTH frozen role closures before creating any output.
    admitted = {}
    for role, pin in PINS.items():
        source = SOURCE/role
        structural.need(sha(source/'manifest.json') == pin, 'plain-v1 parent manifest')
        manifest = json.loads((source/'manifest.json').read_text())
        structural.need(manifest['compile_processors'] == 4
                        and manifest['clock_period_ns'] == 8.0 and manifest['seed'] == 1
                        and manifest['core_parameters'] == dict(AW=16, LANES=64, HOST_LANES=16,
                                                               P=104857601, Q=4190109697)
                        and len(manifest['source_sha256']) == 8
                        and set(manifest['control_sha256']) == CONTROLS,
                        'matched frozen AW16 F0 L64 seed1 8ns four-worker source')
        files = {**{'rtl/'+name: digest for name, digest in manifest['source_sha256'].items()},
                 **manifest['control_sha256']}
        for name, digest in files.items():
            structural.need(sha(source/name) == digest, 'immutable source/control parent')
        qsf = (source/'probe.qsf').read_bytes()
        structural.need(qsf.count(WORKER_OLD) == 1 and WORKER_NEW not in qsf,
                        'unique four-to-six QSF worker anchor')
        structural.need(b'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on\n' in qsf,
                        'retained intermediate snapshots ON')
        spec = json.loads((source/'structural-spec.json').read_text())
        structural.need(not structural.source_inventory(source, spec)['findings'],
                        'frozen declared component inventory')
        admitted[role] = manifest, files, spec

    output.mkdir()
    projects = {}
    for role, (old, files, spec) in admitted.items():
        source, project = SOURCE/role, output/role
        for name, digest in files.items():
            target = project/name
            target.parent.mkdir(parents=True, exist_ok=True)
            if name == 'probe.qsf':
                with target.open('xb') as stream:
                    stream.write((source/name).read_bytes().replace(WORKER_OLD, WORKER_NEW))
            else:
                shutil.copyfile(source/name, target)
                structural.need(sha(target) == digest, 'unchanged six-worker source/control copy')
        manifest = dict(old)
        manifest.update(
            compile_processors=6,
            control_sha256={name: sha(project/name) for name in old['control_sha256']},
            status='source_ready_F2_registered_plain_workers6_v1_not_executed',
            matched_probe_group='F2_rootfused_registered_AW16_L64_F0_seed1_8ns_workers6_v1',
            actual_AW16_integration_pending=False,
            native_context_refs={name: dict(path=path, sha256=pin) for name, (path, pin) in REFS.items()},
            native_context_scope='Raw AW16 field0 and separate registered AW5; not registered-AW16 rerun or whole-core qualification.',
            workers6_source_only=True,
            source_preparer_sha256=sha(__file__),
            lineage=dict(parent_manifest_sha256=PINS[role], unchanged_rtl_files=8,
                unchanged_QPF_SDC_TCL=True,
                exact_QSF_delta='NUM_PARALLEL_PROCESSORS 4->6 only',
                manifest_control_metadata_only_delta=True),
            physical_timing_proven=False,
            promotion_allowed=False)
        save(project/'manifest.json', manifest)
        spec['settings'] = {**manifest['control_sha256'], 'manifest.json': sha(project/'manifest.json')}
        inventory = structural.source_inventory(project, spec)
        structural.need(not inventory['findings'], 'six-worker declared component source inventory')
        save(project/'structural-spec.json', spec)
        save(project/'structural-source-result.json', dict(
            status='PASS_source_only_matched_F2_workers6_component_inventory',
            source_inventory=inventory, exemption='component_sizing_probe',
            normal_source_Quartus_version_PAUSE_resource_budget_deadline_locks_required=True,
            DA_earlyplacement_graph_post_fit_only=True,
            physical_timing_proven=False, promotion_allowed=False))
        context = verifier.verify_project(project)
        structural.need(context['source_sha256'] == old['source_sha256'], 'identical eight RTL context pins')
        structural.need(context['control_sha256'] == {**manifest['control_sha256'],
                        'manifest.json': sha(project/'manifest.json')}, 'exact v6 five-control source context')
        context_file = output/(role+'-context.json')
        save(context_file, context)
        package = output/(role+'-plain-workers6-source-v1.tar.gz')
        with tarfile.open(package, 'x:gz') as stream:
            for path in sorted(project.rglob('*')):
                if path.is_file():
                    stream.add(path, arcname='project/'+path.relative_to(project).as_posix(), recursive=False)
        projects[role] = dict(project_root=str(project), manifest_sha256=sha(project/'manifest.json'),
            source_sha256=manifest['source_sha256'], control_sha256=manifest['control_sha256'],
            context_file=str(context_file), context_sha256=sha(context_file),
            archive=str(package), archive_sha256=sha(package), archive_bytes=package.stat().st_size)
    result = dict(status='source_ready_F2_matched_plain_workers6_no_remote_or_vendor_execution',
        projects=projects, source_verifier_sha256=V6_PIN, reused_plain_runner_sha256=PLAIN_PIN,
        preparer_sha256=sha(__file__), workers=6, normal_dispatch_checks_required=True,
        source_only=True, transfer_attempted=False, launch_attempted=False,
        physical_timing_proven=False, promotion_allowed=False)
    save(output/'preparation.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
