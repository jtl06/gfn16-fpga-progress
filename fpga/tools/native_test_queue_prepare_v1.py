"""Prepare one finite qualified-component queue smoke; never execute/dispatch."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tarfile

sys.dont_write_bytecode = True
STAGE = 'results/throughput-20260929/track-a4-blocklane-portable-gcp-stage-v1'
DONOR = 'results/throughput-20260929/track-a4-blocklane-gcp-aw5-v1'
DONOR_SHA = 'd0827812b3a65daf377c7e8cf055c561a862598f6fda585fe08959c8cc83f94b'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def prepare(out, root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    queue = load(root/'tools/native_test_queue_v1.py', '_finite_queue_prepare')
    pins = {name:queue.sha(root/'tools'/name) for name in queue.WORKER_FILES}
    policy, identity = queue.modules(root/'tools', pins)
    queue.need(not out.exists(), 'fresh queue preparation directory')
    manifest = json.loads((root/STAGE/'aw5-manifest.json').read_text())
    profile = policy.PROFILES[manifest['host']]
    donor = root/DONOR; review_path = donor/'independent-review-v1.json'
    review = json.loads(review_path.read_text()); review_sha = queue.sha(review_path)
    admission = identity.admit_cached_elf(manifest, profile, donor, DONOR_SHA, review_path, review_sha)
    out.mkdir(parents=True); bundle = out/'bundle'; bundle.mkdir()
    worker = bundle/'worker'; worker.mkdir()
    for name in queue.WORKER_FILES: shutil.copyfile(root/'tools'/name, worker/name)
    snapshot = bundle/'snapshots/lane/fpga'; snapshot.mkdir(parents=True)
    for name, digest in manifest['sources'].items():
        source = root/STAGE/'source/fpga'/name; queue.need(queue.sha(source) == digest, 'known tiny-component source pin')
        target = snapshot/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
    evidence = bundle/'evidence/lane-aw5'; evidence.mkdir(parents=True)
    donor_report = json.loads((donor/'report.json').read_text())
    for name in list(donor_report['artifacts'])+['report.json', 'independent-review-v1.json']:
        target = evidence/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(donor/name, target)
    manifests = bundle/'manifests'; manifests.mkdir()
    shutil.copyfile(root/STAGE/'aw5-manifest.json', manifests/'lane-aw5.json')
    queue_id = 'a4-lane-qualified-smoke-v2'
    native_bundle = Path(profile['base'])/'native-test-queue'/queue_id
    review_descriptor = dict(path='evidence/lane-aw5/independent-review-v1.json', sha256=review_sha)
    job = dict(id='lane-aw5-qualified-smoke-v2', trial_id='a4-lane-qualified-queue-smoke-v2', owner='/root/t5_qualification',
        track='workflow', evidence_class='qualified_executable_new_commands', handler='qualified-executable-v1',
        manifest=dict(path='manifests/lane-aw5.json', sha256=queue.sha(manifests/'lane-aw5.json')),
        snapshot='snapshots/lane/fpga', build_key=admission['build_key'], dependencies=[], review_required=True,
        review_gates=[dict(review_descriptor, layer='independent_review', expected_status=review['status'],
            bindings={key:review[key] for key in ('report_sha256', 'manifest_sha256', 'executable_sha256')})],
        reuse=dict(directory='evidence/lane-aw5', report_sha256=DONOR_SHA, review=review_descriptor),
        output='results/lane-aw5-qualified-smoke-v2', collection='collected/lane-aw5-qualified-smoke-v2',
        native_output=str(native_bundle/'results/lane-aw5-qualified-smoke-v2'),
        max_seconds=3600, command_seconds=1800, failure_policy='stop', promotion_allowed=False)
    job['run_key'] = hashlib.sha256(queue.canonical(dict(build_key=job['build_key'], probe=manifest['probe'],
        steps=manifest['steps'], trial_id=job['trial_id']))).hexdigest()
    inputs = {str(path.relative_to(bundle)):queue.sha(path) for path in bundle.rglob('*') if path.is_file()}
    ticket = dict(schema=queue.SCHEMA, status='prepared_not_executed', id=queue_id, host=manifest['host'],
        bundle_root=str(native_bundle), worker_root=str(native_bundle/'worker'), worker_sources=pins, inputs=inputs,
        failure_policy='stop', promotion_allowed=False, max_seconds=4200,
        pause_policy=dict(remote_flag=str(native_bundle/'PAUSE'), host_flag=str(Path(profile['base'])/'native-test-queue/PAUSE'),
            local_brief_gate='fpga/docs/briefs/PAUSE', local_gate_owner='main_dispatcher_before_dispatch', check='before_claim_and_each_new_job'),
        resources=dict(cpus=profile['cpus'], memory_bytes=4*queue.GIB, cpu_quota_percent=200, max_active_jobs=1), jobs=[job])
    queue.validate_plan(ticket, bundle, policy, identity)
    (bundle/'queue.json').write_text(json.dumps(ticket, indent=2)+'\n')
    with tarfile.open(out/'source.tar.gz', 'x:gz') as archive:
        for path in sorted(bundle.rglob('*')):
            if path.is_file(): archive.add(path, arcname=str(path.relative_to(bundle)), recursive=False)
    result = dict(status='prepared_not_executed', queue_sha256=queue.sha(bundle/'queue.json'), archive_sha256=queue.sha(out/'source.tar.gz'),
        worker_sources=pins, build_key=job['build_key'], run_key=job['run_key'], files=len(inputs)+1,
        native_bundle=str(native_bundle), required_existing_source=manifest['source_root'],
        required_existing_claim_registry=str(Path(profile['base'])/'native-test-claims'),
        limitation='One fresh tiny-component invocation using independently qualified ELF. No native execution, dispatch, provisioning or promotion.')
    (out/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2)); return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    prepare(parser.parse_args().output.resolve())
