"""Prepare the three existing tiny-field mutants as a finite native queue.

Preserves each manifest and snapshot byte-for-byte. No native dispatch.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tarfile

sys.dont_write_bytecode = True
PREPARED = 'artifacts/stream27-field-square-aw5-gcp-prepared-v2'
CONTROL = 'results/throughput-20260929/stream27-field-square-aw5-gcp-control-v1'
CONTROL_SHA = 'ae395245ff70198535d5b5a3905dfe32401d2b343c04515a727c7e86cc77f95d'
SOURCE_REVIEW = 'docs/briefs/replies/2026-10-01-B20260930S-S3-field-square-aw5-source-independent-v1.json'
SOURCE_REVIEW_SHA = 'e34a02f8574d78542ec384e8be0e9d9e501dd4660a5efae9481d494ac095354f'
ROLES = ('wrong_final_domain', 'missing_c0', 'missing_c1')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


def prepare(out, root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    queue = load(root/'tools/native_test_queue_v1.py', '_field_finite_queue')
    worker_pins = {name:queue.sha(root/'tools'/name) for name in queue.WORKER_FILES}
    policy, identity = queue.modules(root/'tools', worker_pins)
    queue.need(not out.exists(), 'fresh field queue stage')
    queue.need(queue.sha(root/CONTROL/'report.json') == CONTROL_SHA and queue.sha(root/SOURCE_REVIEW) == SOURCE_REVIEW_SHA,
               'exact successful control/source-admission identities')
    source_review = json.loads((root/SOURCE_REVIEW).read_text())
    control_manifest_path = root/CONTROL/'approved-manifest.json'
    control_manifest = json.loads(control_manifest_path.read_text())
    profile = policy.PROFILES[control_manifest['host']]
    control = queue.verify_worker(root/CONTROL, control_manifest, queue.sha(control_manifest_path), profile, 'source-gate-v1')
    out.mkdir(parents=True); bundle = out/'bundle'; bundle.mkdir()
    worker = bundle/'worker'; worker.mkdir()
    for name in queue.WORKER_FILES: shutil.copyfile(root/'tools'/name, worker/name)
    evidence = bundle/'evidence'; evidence.mkdir()
    shutil.copyfile(root/SOURCE_REVIEW, evidence/'source-review.json')
    control_copy = evidence/'control-native'; control_copy.mkdir()
    for name in list(control['artifacts'])+['report.json']:
        target = control_copy/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(root/CONTROL/name, target)
    review_gates = [dict(path='evidence/source-review.json', sha256=SOURCE_REVIEW_SHA, layer='independent_review',
        expected_status=source_review['status'], bindings={key:source_review[key] for key in ('preparation_sha256', 'manifests')})]
    native_review_path = root/CONTROL/'independent-review-v1.json'
    native_review = None
    if native_review_path.is_file():
        native_review = json.loads(native_review_path.read_text())
        queue.need(native_review['status'].startswith('PASS_') and native_review['report_sha256'] == CONTROL_SHA
            and native_review['manifest_sha256'] == control['manifest_sha256'], 'control independent review binding')
        shutil.copyfile(native_review_path, evidence/'control-independent-review.json')
        review_gates.append(dict(path='evidence/control-independent-review.json', sha256=queue.sha(native_review_path), layer='independent_review',
            expected_status=native_review['status'], bindings={key:native_review[key] for key in ('report_sha256', 'manifest_sha256')}))
    queue_id = 'field-aw5-three-mutants-v2'
    native_bundle = Path(profile['base'])/'native-test-queue'/queue_id
    (bundle/'manifests').mkdir()
    jobs, staging = [], []
    for role in ROLES:
        source_manifest = root/PREPARED/(role+'-manifest.json')
        manifest = json.loads(source_manifest.read_text())
        queue.need(queue.sha(source_manifest) == source_review['manifests'][role], 'independently admitted unchanged mutant manifest')
        slug = role.replace('_', '-'); job_id = 'field-aw5-'+slug+'-queue-v2'
        snapshot_relative = 'snapshots/'+slug+'/fpga'
        snapshot = bundle/snapshot_relative; snapshot.mkdir(parents=True)
        source = root/PREPARED/role/'source/fpga'
        policy.check_sources(source.resolve(), manifest['sources'])
        for name, digest in manifest['sources'].items():
            target = snapshot/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source/name, target)
            queue.need(queue.sha(target) == digest, 'mutant snapshot copy hash')
        manifest_relative = 'manifests/'+slug+'.json'; shutil.copyfile(source_manifest, bundle/manifest_relative)
        key = identity.build_identity(manifest, profile)['build_key']
        dependencies = [dict(job_id=jobs[-1]['id'], required_status='needs_independent_review', layer='execution_and_collection')] if jobs else []
        trial = 'field-aw5-'+slug+'-v2'
        job = dict(id=job_id, trial_id=trial, owner='/root/stream_interface', track='S', evidence_class='negative_control_native_commands',
            handler='source-gate-v1', manifest=dict(path=manifest_relative, sha256=queue.sha(source_manifest)), snapshot=snapshot_relative,
            build_key=key, dependencies=dependencies, review_required=True, review_gates=review_gates, reuse=None,
            output='results/'+job_id, collection='collected/'+job_id, native_output=str(Path(manifest['output_parent'])/job_id),
            max_seconds=3600, command_seconds=1800, failure_policy='stop', promotion_allowed=False)
        job['run_key'] = hashlib.sha256(queue.canonical(dict(build_key=key, probe=manifest['probe'], steps=manifest['steps'], trial_id=trial))).hexdigest()
        jobs.append(job)
        staging.append(dict(role=role, bundle_snapshot=snapshot_relative, native_source_root=manifest['source_root'],
            require_fresh_destination=True, sources=manifest['sources'], manifest_sha256=job['manifest']['sha256'],
            native_output=job['native_output']))
    inputs = {str(path.relative_to(bundle)):queue.sha(path) for path in bundle.rglob('*') if path.is_file()}
    ticket = dict(schema=queue.SCHEMA, status='prepared_not_executed', id=queue_id, host=control_manifest['host'],
        bundle_root=str(native_bundle), worker_root=str(native_bundle/'worker'), worker_sources=worker_pins, inputs=inputs,
        failure_policy='stop', promotion_allowed=False, max_seconds=11400,
        pause_policy=dict(remote_flag=str(native_bundle/'PAUSE'), host_flag=str(Path(profile['base'])/'native-test-queue/PAUSE'),
            local_brief_gate='fpga/docs/briefs/PAUSE', local_gate_owner='main_dispatcher_before_dispatch', check='before_claim_and_each_new_job'),
        resources=dict(cpus=profile['cpus'], memory_bytes=4*queue.GIB, cpu_quota_percent=200, max_active_jobs=1), jobs=jobs)
    queue.validate_plan(ticket, bundle, policy, identity)
    (bundle/'queue.json').write_text(json.dumps(ticket, indent=2)+'\n')
    with tarfile.open(out/'source.tar.gz', 'x:gz') as archive:
        for path in sorted(bundle.rglob('*')):
            if path.is_file(): archive.add(path, arcname=str(path.relative_to(bundle)), recursive=False)
    result = dict(status='prepared_not_executed', queue_sha256=queue.sha(bundle/'queue.json'), archive_sha256=queue.sha(out/'source.tar.gz'),
        worker_sources=worker_pins, files=len(inputs)+1, jobs=[dict(id=job['id'], manifest_sha256=job['manifest']['sha256'],
            build_key=job['build_key'], run_key=job['run_key']) for job in jobs], native_bundle=str(native_bundle), staging=staging,
        control_evidence=dict(report_sha256=CONTROL_SHA, status=control['status'], artifacts_checked=len(control['artifacts']),
            layer='independent_native_review' if native_review else 'native_commands_and_archive_replay_only',
            independent_review_sha256=queue.sha(native_review_path) if native_review else None,
            limitation='All control report/artifact bytes are pinned queue inputs; native success alone does not promote correctness.'),
        source_review_sha256=SOURCE_REVIEW_SHA,
        limitation='Three independently compiled existing arithmetic mutants. No source/manifest changes, cache reuse, native dispatch or promotion.')
    (out/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('status', 'queue_sha256', 'archive_sha256', 'files', 'jobs', 'control_evidence')}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    prepare(parser.parse_args().output.resolve())
