"""Finite, pinned native-test queue with verified worker-side evidence collection.

Only two handlers: frozen source gate, or independently admitted existing ELF.
No shell/SSH/service/provisioning/deletion/retry/promotion functionality exists.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time

sys.dont_write_bytecode = True
POLICY_SHA = '5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd'
WORKER_FILES = ('native_test_queue_v1.py', 'native_source_gate_v1.py', 'build_identity_v1.py')
SCHEMA = 'finite-native-test-queue-v1'
GIB, MIB = 1 << 30, 1 << 20


class QueuePaused(RuntimeError): pass


def pause_check(ticket):
    # The remote worker cannot see the Mac's live canonical brief switch.
    # Main checks that file before dispatch; these two remote flags are local
    # to this worker and stop NEW jobs, without interrupting an active command.
    for name in ('remote_flag', 'host_flag'):
        if Path(ticket['pause_policy'][name]).exists(): raise QueuePaused('remote queue PAUSE: '+ticket['pause_policy'][name])


def need(ok, why):
    if not ok: raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def identifier(value):
    need(type(value) is str and re.fullmatch('[a-z][a-z0-9-]{0,79}', value), 'bounded identifier')
    return value


def canonical_path(path):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'canonical unredirected write path')
    return path


def fresh_path(path):
    path = canonical_path(path)
    need(not path.exists(), 'fresh write destination')
    canonical_path(path.parent)
    return path


def safe(root, name):
    need(type(name) is str and str(Path(name)) == name and name not in ('', '.') and not Path(name).is_absolute()
         and '..' not in Path(name).parts, 'safe relative file name')
    path = root/name
    need(not path.is_symlink() and path.is_file() and path.stat().st_nlink == 1
         and path.resolve().is_relative_to(root.resolve()), 'regular unlinked input file: '+name)
    return path


def pinned_json(root, entry):
    need(set(entry) >= {'path', 'sha256'} and re.fullmatch('[0-9a-f]{64}', entry['sha256']), 'pinned JSON descriptor')
    path = safe(root, entry['path']); need(sha(path) == entry['sha256'], 'pinned JSON identity')
    return json.loads(path.read_text())


def modules(directory, pins):
    need(set(pins) == set(WORKER_FILES) and pins['native_source_gate_v1.py'] == POLICY_SHA, 'exact worker/policy closure')
    result = []
    for name in WORKER_FILES:
        need(sha(safe(directory, name)) == pins[name], 'worker source hash')
        if name == 'native_test_queue_v1.py': continue
        spec = importlib.util.spec_from_file_location('_queue_'+Path(name).stem, directory/name)
        value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); result.append(value)
    return tuple(result)


def receipt_gate(bundle, gate):
    need(gate['layer'] == 'independent_review' and type(gate['expected_status']) is str
         and type(gate['bindings']) is dict and gate['bindings'], 'explicit independently reviewed dependency layer')
    receipt = pinned_json(bundle, gate)
    need(receipt['status'] == gate['expected_status'] and all(receipt.get(key) == value for key, value in gate['bindings'].items()),
         'required independent receipt status/bindings')
    return receipt


def stderr_matches(contract, text):
    if 'expected_stderr' in contract:
        return type(contract['expected_stderr']) is str and text == contract['expected_stderr']
    argv = contract['argv']
    if len(argv) != 4 or argv[-2] != '--expect-negative': return False
    kind = argv[-1]
    if kind not in ('FIELD_PHYSICAL_DATA_MISMATCH', 'FIELD_SLOT_MISMATCH'): return False
    if contract.get('expected_returncode', 0) != 0 or contract['expected_stdout'] != 'FIELD_SQUARE_NEGATIVE_PASS kind='+kind+'\n': return False
    return re.fullmatch(re.escape(kind)+r' tick=[0-9]+ port=[0-9]+\n?', text) is not None


def manifest_contract(manifest, host):
    need(manifest['schema'] == 'native-source-gate-v1' and manifest['status'] == 'prepared_not_executed'
         and manifest['host'] == host and manifest['sources'].get('tools/native_source_gate_v1.py') == POLICY_SHA,
         'frozen component source-gate manifest/profile')
    need(manifest['probe'] == dict(argv=['{exe}', '--runtime-probe'],
         expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)), 'one-thread runtime probe')
    need(type(manifest['steps']) is list and 1 <= len(manifest['steps']) <= 64, 'finite native case list')
    names = []
    for step in manifest['steps']:
        name = identifier(step['name']); need(name not in ('build', 'probe', 'verilator-version', 'compiler-version'), 'reserved native step')
        names.append(name)
        need(type(step['argv']) is list and 1 <= len(step['argv']) <= 16 and step['argv'][0] == '{exe}'
             and all(type(arg) is str and len(arg) <= 512 for arg in step['argv']), 'only pinned executable arguments')
        need(type(step.get('expected_returncode', 0)) is int and step.get('expected_returncode', 0) in (-6, 0, 1), 'typed normal/negative result')
        need(type(step['expected_stdout']) is str and ('expected_stderr' in step and type(step['expected_stderr']) is str
             or stderr_matches(step, step['argv'][-1]+' tick=0 port=0\n')), 'exact stdout and exact/typed stderr contract')
    need(len(names) == len(set(names)), 'unique native steps')


def validate_plan(ticket, bundle, policy, identity):
    need(set(ticket) == {'schema', 'status', 'id', 'host', 'bundle_root', 'worker_root', 'worker_sources', 'inputs',
                        'failure_policy', 'promotion_allowed', 'max_seconds', 'resources', 'jobs', 'pause_policy'}, 'exact finite ticket fields')
    need(ticket['schema'] == SCHEMA and ticket['status'] == 'prepared_not_executed', 'finite queue schema/status')
    identifier(ticket['id']); need(ticket['host'] in policy.PROFILES, 'fixed approved host profile')
    profile = policy.PROFILES[ticket['host']]
    native_bundle = Path(profile['base'])/'native-test-queue'/ticket['id']
    need(ticket['bundle_root'] == str(native_bundle) and ticket['worker_root'] == str(native_bundle/'worker'), 'fixed queue placement')
    need(ticket['pause_policy'] == dict(remote_flag=str(native_bundle/'PAUSE'),
         host_flag=str(Path(profile['base'])/'native-test-queue/PAUSE'), local_brief_gate='fpga/docs/briefs/PAUSE',
         local_gate_owner='main_dispatcher_before_dispatch', check='before_claim_and_each_new_job'), 'explicit local/remote PAUSE boundary')
    need(ticket['failure_policy'] == 'stop' and ticket['promotion_allowed'] is False and ticket['max_seconds'] <= 14400
         and type(ticket['max_seconds']) is int and ticket['max_seconds'] > 0, 'finite fail-fast non-promotion policy')
    need(ticket['resources'] == dict(cpus=profile['cpus'], memory_bytes=4*GIB, cpu_quota_percent=200, max_active_jobs=1),
         'fixed serial resource profile')
    need(type(ticket['jobs']) is list and 1 <= len(ticket['jobs']) <= 16, 'finite at-most-sixteen jobs')
    for name, digest in ticket['inputs'].items(): need(sha(safe(bundle, name)) == digest, 'queue input hash')
    ids, run_keys, outputs, result = set(), set(), set(), []
    for job in ticket['jobs']:
        need(set(job) == {'id', 'trial_id', 'owner', 'track', 'evidence_class', 'handler', 'manifest', 'snapshot',
             'build_key', 'dependencies', 'review_required', 'review_gates', 'reuse', 'output', 'collection',
             'max_seconds', 'command_seconds', 'failure_policy', 'promotion_allowed', 'run_key', 'native_output'}, 'exact job fields; no free-form commands')
        name = identifier(job['id']); need(name not in ids, 'duplicate job id')
        need(type(job['owner']) is str and job['owner'] and job['track'] in ('A', 'S', 'workflow'), 'explicit owner and track')
        need(job['handler'] in ('source-gate-v1', 'qualified-executable-v1') and job['failure_policy'] == 'stop', 'fixed execution handler')
        need(job['evidence_class'] in ('component_native_commands', 'negative_control_native_commands', 'qualified_executable_new_commands'), 'explicit evidence layer')
        need(job['max_seconds'] == 3600 and job['command_seconds'] == 1800 and job['promotion_allowed'] is False, 'bounded non-promoting job')
        need(job['output'] == 'results/'+name and job['collection'] == 'collected/'+name, 'fixed fresh worker/collection directories')
        need(job['output'] not in outputs and job['collection'] not in outputs, 'duplicate output path')
        outputs.update((job['output'], job['collection']))
        for dependency in job['dependencies']:
            need(set(dependency) == {'job_id', 'required_status', 'layer'} and dependency['job_id'] in ids and
                 dependency['required_status'] == 'needs_independent_review' and dependency['layer'] == 'execution_and_collection',
                 'ordered acyclic explicit exploratory dependency; reviewed requirements need receipt gates')
        need(type(job['review_required']) is bool and bool(job['review_gates']) == job['review_required'], 'explicit mandatory review gates')
        for gate in job['review_gates']: receipt_gate(bundle, gate)
        manifest = pinned_json(bundle, job['manifest']); manifest_contract(manifest, ticket['host'])
        source_relative = Path(job['snapshot'])
        source_native = Path(manifest['source_root'])
        need(str(source_relative).startswith('snapshots/') and source_relative.name == 'fpga' and
             not source_relative.is_absolute() and '..' not in source_relative.parts and
             source_native.is_absolute() and source_native.name == 'fpga' and source_native.is_relative_to(profile['base'])
             and '..' not in source_native.parts, 'explicit admitted component snapshot')
        output_parent = Path(manifest['output_parent'])
        need(output_parent.is_absolute() and output_parent.is_relative_to(profile['base']) and output_parent != Path(profile['base'])
             and '..' not in output_parent.parts, 'explicit native output parent')
        expected_output = output_parent/name if job['handler'] == 'source-gate-v1' else native_bundle/job['output']
        need(job['native_output'] == str(expected_output) and not expected_output.is_relative_to(source_native), 'fixed fresh native output')
        policy.check_sources((bundle/source_relative).resolve(), manifest['sources'])
        for step in [manifest['probe']]+manifest['steps']:
            policy.expand(step['argv'], Path('/approved-model'), Path('/approved-source'))
        key = identity.build_identity(manifest, profile)['build_key']
        need(job['build_key'] == key, 'complete source/config/tool/environment build identity')
        trial = identifier(job['trial_id'])
        run_key = hashlib.sha256(canonical(dict(build_key=key, probe=manifest['probe'], steps=manifest['steps'], trial_id=trial))).hexdigest()
        need(job['run_key'] == run_key and run_key not in run_keys, 'duplicate execution trial/command identity')
        run_keys.add(run_key)
        if job['handler'] == 'qualified-executable-v1':
            donor = job['reuse']
            need(donor['directory'].startswith('evidence/') and job['review_required'], 'independent qualified ELF admission required')
            admitted = identity.admit_cached_elf(manifest, profile, bundle/donor['directory'], donor['report_sha256'],
                safe(bundle, donor['review']['path']), donor['review']['sha256'])
            need(admitted['build_key'] == key, 'qualified ELF exact cache identity')
        else: need(job['reuse'] is None, 'no implicit cache for source builds')
        ids.add(name); result.append((job, manifest, bundle/source_relative))
    return profile, result


def claim(registry, run_key, payload):
    need(re.fullmatch('[0-9a-f]{64}', run_key), 'claim key')
    need(registry.is_dir() and registry.resolve() == registry, 'canonical pre-existing claim registry')
    path = registry/(run_key+'.json')
    # O_EXCL is the persistent cross-process/cross-queue duplicate barrier.
    # Claims are never erased or automatically retried, including after failure.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream: json.dump(payload, stream, indent=2); stream.write('\n')
    return path


def archive_inventory(path, expected):
    actual = {}
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            need(member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                 and member.name not in actual, 'safe unique regular archive members')
            actual[member.name] = hashlib.file_digest(archive.extractfile(member), 'sha256').hexdigest()
    need(actual == expected, 'exact archive closure')


def verify_worker(directory, manifest, manifest_sha, profile, handler):
    report = json.loads(safe(directory, 'report.json').read_text())
    need(report['status'] == 'completed_native_commands_unreviewed' and report['manifest_sha256'] == manifest_sha
         and report['sources'] == manifest['sources'] and report['host'] == manifest['host'], 'completed source-bound worker evidence only')
    for name, digest in report['artifacts'].items(): need(sha(safe(directory, name)) == digest, 'worker artifact identity')
    need(sha(directory/'approved-manifest.json') == manifest_sha, 'worker copied manifest')
    archive_inventory(directory/'sources.tar.gz', manifest['sources'])
    with gzip.open(directory/'model.gz', 'rb') as stream:
        need(hashlib.file_digest(stream, 'sha256').hexdigest() == report['executable_sha256'], 'worker compressed executable identity')
    if handler == 'source-gate-v1': archive_inventory(directory/'generated-sources.tar.gz', report['generated_source_sha256'])
    names = (['verilator-version', 'compiler-version', 'build'] if handler == 'source-gate-v1' else [])+['probe']+[x['name'] for x in manifest['steps']]
    need([step['name'] for step in report['steps']] == names, 'exact native step sequence')
    by_name = {step['name']:step for step in report['steps']}
    toolpaths = dict(verilator=Path(profile['verilator_dir'])/'verilator', verilator_bin=Path(profile['verilator_dir'])/'verilator_bin',
        compiler=Path('/usr/bin/x86_64-linux-gnu-g++-15'), python=Path('/usr/bin/python3.14'), make=Path('/usr/bin/make'), taskset=Path('/usr/bin/taskset'))
    need(report['tool_sha256'] == {str(path):profile['hashes'][name] for name,path in toolpaths.items()}, 'exact worker toolchain')
    prefix = [str(toolpaths['taskset']), '-c', ','.join(map(str, profile['cpus']))]
    model = Path(report['scratch'])/'build'/('V'+manifest['build']['top']) if handler == 'source-gate-v1' else Path(report['model_path'])
    if handler == 'source-gate-v1':
        config = manifest['build']; root = Path(manifest['source_root'])
        build_command = prefix+[str(toolpaths['verilator']), '--cc', '--exe', '--build', '-j', '2', '--threads', '1',
            '--top-module', config['top'], *[f'-G{k}={v}' for k,v in config['parameters'].items()], '-CFLAGS', ' '.join(config['cflags']),
            '--Mdir', str(Path(report['scratch'])/'build'), *[str(root/name) for name in config['sv_sources']], str(root/config['cpp_source'])]
        need(by_name['build']['command'] == build_command, 'source-bound exact build argv')
        need(by_name['verilator-version']['command'] == prefix+[str(toolpaths['verilator']), '--version'] and
             by_name['compiler-version']['command'] == prefix+[str(toolpaths['compiler']), '--version'], 'exact tool version argv')
        need(all(by_name[name]['returncode'] == 0 for name in ('build', 'verilator-version', 'compiler-version')), 'successful build/tool steps')
    for contract in [dict(manifest['probe'], name='probe')]+manifest['steps']:
        expected = prefix+[arg.replace('{exe}', str(model)).replace('{root}', manifest['source_root']) for arg in contract['argv']]
        need(by_name[contract['name']]['command'] == expected, 'exact probe/case command identity')
    for step in report['steps']:
        need(step['error'] is None and sha(directory/step['log']) == step['sha256']
             and sha(directory/step['stderr_log']) == step['stderr_sha256'], 'native step/log evidence')
    need(json.loads((directory/by_name['probe']['log']).read_text()) == manifest['probe']['expected_json']
         and by_name['probe']['returncode'] == 0, 'actual one-thread runtime probe')
    for contract in manifest['steps']:
        step = by_name[contract['name']]
        need(step['returncode'] == contract.get('expected_returncode', 0)
             and (directory/step['log']).read_text() == contract['expected_stdout']
             and stderr_matches(contract, (directory/step['stderr_log']).read_text()), 'native exact/typed output/return contract')
    quota, period = map(int, report['limits']['cpu_max'])
    need(report['limits']['affinity'] == profile['cpus'] and 0 < report['limits']['memory_max_bytes'] <= 4*GIB
         and 0 < quota <= 2*period and len({tuple(x) for x in report['limits']['physical_cores']}) == 2
         and report['model_threads'] == 1, 'worker resource/thread profile')
    return report


def collect_evidence(directory, destination, manifest, manifest_sha, profile, handler):
    report = verify_worker(directory, manifest, manifest_sha, profile, handler)
    need(not destination.exists(), 'fresh collection output'); fresh_path(destination).mkdir()
    pins = dict(report['artifacts'], **{'report.json':sha(directory/'report.json')})
    for name, digest in pins.items():
        target = destination/name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe(directory, name), target); need(sha(target) == digest, 'collected artifact hash')
    verify_worker(destination, manifest, manifest_sha, profile, handler)
    receipt = dict(status='needs_independent_review', report_sha256=pins['report.json'], manifest_sha256=manifest_sha,
                   files=pins, promotion_allowed=False, scope='local worker evidence copied and hash-verified; not correctness promotion')
    (destination/'collection.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def collect_failed_evidence(directory, destination, launcher=None):
    """Preserve bounded known worker artifacts without turning failure into pass."""
    need(not destination.exists(), 'fresh failed-evidence collection'); fresh_path(destination).mkdir(parents=True)
    files, errors = {}, []
    candidates = {}
    if (directory/'report.json').is_file():
        candidates['report.json'] = (directory, 'report.json', None)
        try:
            report = json.loads(safe(directory, 'report.json').read_text())
            for name, digest in report.get('artifacts', {}).items(): candidates['worker/'+name] = (directory, name, digest)
        except (ValueError, KeyError, OSError) as error: errors.append(repr(error))
    if launcher and launcher.is_dir():
        for name in ('launcher.log', 'launcher.stderr.log'):
            if (launcher/name).is_file(): candidates[name] = (launcher, name, None)
    for target_name, (root, name, expected) in candidates.items():
        try:
            source = safe(root, name); digest = sha(source)
            need(expected is None or digest == expected, 'failed artifact hash mismatch: '+name)
            target = destination/target_name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target); need(sha(target) == digest, 'failed collection copy drift')
            files[target_name] = digest
        except (ValueError, KeyError, OSError) as error: errors.append(repr(error))
    receipt = dict(status='failed_or_incomplete', files=files, collection_errors=errors, raw_worker_output=str(directory),
                   raw_launcher_output=str(launcher) if launcher else None, promotion_allowed=False)
    (destination/'collection.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def checked_process(command, root, env, output, name, timeout, guard):
    canonical_path(output)
    log, error_log = output/(name+'.log'), output/(name+'.stderr.log')
    started = time.monotonic(); failure = None
    with log.open('x') as stream, error_log.open('x') as error_stream:
        child = subprocess.Popen(command, cwd=root, env=env, stdout=stream, stderr=error_stream, start_new_session=True)
        try:
            while child.poll() is None:
                guard(); need(time.monotonic()-started < timeout, 'bounded native command timeout'); time.sleep(.2)
        except BaseException as error:
            failure = error
            try: os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                child.wait()
    entry = dict(name=name, command=command, returncode=child.returncode, seconds=time.monotonic()-started,
                 error=repr(failure) if failure else None, log=log.name, sha256=sha(log),
                 stderr_log=error_log.name, stderr_sha256=sha(error_log))
    return entry, failure


def qualified_run(job, manifest, root, bundle, output, policy, identity, profile, tools, limits, guard):
    donor = job['reuse']
    admission = identity.admit_cached_elf(manifest, profile, bundle/donor['directory'], donor['report_sha256'],
        safe(bundle, donor['review']['path']), donor['review']['sha256'])
    need(admission['build_key'] == job['build_key'], 'same admitted ELF identity')
    fresh_path(output).mkdir()
    report = dict(status='running', host=manifest['host'], source_root=str(root), sources=manifest['sources'],
        manifest_sha256=job['manifest']['sha256'], tool_sha256={str(p):sha(p) for p in tools.values()}, limits=limits,
        build_key=job['build_key'], admission={k:str(v) if isinstance(v, Path) else v for k,v in admission.items()},
        compile_workers=0, model_threads=1, steps=[], artifacts={}, executable_sha256=admission['executable_sha256'],
        scope='fresh commands using independently admitted exact ELF; needs independent review')
    def remember(path): report['artifacts'][str(path.relative_to(output))] = sha(path)
    def save(): (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    try:
        shutil.copyfile(bundle/job['manifest']['path'], output/'approved-manifest.json'); remember(output/'approved-manifest.json')
        with tarfile.open(output/'sources.tar.gz', 'x:gz') as archive:
            for name in sorted(manifest['sources']): archive.add(root/name, arcname=name, recursive=False)
        remember(output/'sources.tar.gz')
        shutil.copyfile(admission['archive_path'], output/'model.gz'); remember(output/'model.gz')
        model = output/'model'
        with gzip.open(output/'model.gz', 'rb') as source, model.open('xb') as target: shutil.copyfileobj(source, target)
        model.chmod(0o500); remember(model); need(sha(model) == report['executable_sha256'], 'restored ELF hash')
        report['model_path'] = str(model)
        env = policy.clean_env(root, output, profile)
        for contract in [dict(manifest['probe'], name='probe')]+manifest['steps']:
            guard(); need(sha(model) == report['executable_sha256'], 'model drift')
            command = [str(tools['taskset']), '-c', ','.join(map(str, profile['cpus'])), *policy.expand(contract['argv'], model, root)]
            step, failure = checked_process(command, root, env, output, contract['name'], 1800, guard)
            report['steps'].append(step); remember(output/step['log']); remember(output/step['stderr_log']); save()
            if failure: raise failure
            need(step['returncode'] == contract.get('expected_returncode', 0), 'native contract return code')
            text = (output/step['log']).read_text()
            if contract['name'] == 'probe': need(json.loads(text) == contract['expected_json'], 'runtime probe')
            else:
                need(text == contract['expected_stdout'] and stderr_matches(contract, (output/step['stderr_log']).read_text()),
                     'exact qualified-model output contract')
        guard(); need(all(sha(output/name) == value for name,value in report['artifacts'].items()), 'qualified-run artifacts')
        report['status'] = 'completed_native_commands_unreviewed'
    except BaseException as error: report.update(status='failed_native_commands', error=repr(error)); raise
    finally: save()


def execute(ticket_path, digest):
    need(__debug__ and re.fullmatch('[0-9a-f]{64}', digest) and sha(ticket_path) == digest, 'exact approved ticket hash')
    ticket = json.loads(ticket_path.read_text())
    need(socket.gethostname() == ticket['host'] and ticket['host'] in ('aethia', 'gfn16-pilot-c4'), 'native approved host only')
    bundle = Path(ticket['bundle_root']); worker = bundle/'worker'
    need(bundle.resolve() == bundle and Path(__file__).resolve() == worker/'native_test_queue_v1.py', 'pinned native worker location')
    policy, identity = modules(worker, ticket['worker_sources'])
    profile, jobs = validate_plan(ticket, bundle, policy, identity)
    # Reused models retain their original source-root-bound identity. The bundle
    # source copy is review evidence; native commands read the admitted original.
    jobs = [(job, manifest, Path(manifest['source_root'])) for job, manifest, _ in jobs]
    for _, manifest, root in jobs: policy.check_sources(root, manifest['sources'])
    tools = policy.tools_for(profile); limits = policy.execution_limits(profile['cpus'])
    need(not (bundle/'queue-report.json').exists(), 'queue already attempted')
    registry = Path(profile['base'])/'native-test-claims'
    need(registry.is_dir() and registry.resolve() == registry, 'claim registry must be pre-existing and canonical')
    for job, _, _ in jobs:
        need(not Path(job['native_output']).exists() and not (bundle/job['collection']).exists(), 'job/collection already exists')
        fresh_path(Path(job['native_output'])); fresh_path(bundle/job['collection']); fresh_path(bundle/('launch-'+job['id']))
        fresh_path(bundle/'failed-collected'/job['id'])
    pause_check(ticket)
    queue_key = hashlib.sha256(canonical(dict(queue_id=ticket['id'], host=ticket['host'], schema=SCHEMA))).hexdigest()
    queue_claim = claim(registry, queue_key, dict(status='queue_claimed_no_automatic_retry', ticket_sha256=digest,
        queue_id=ticket['id'], pid=os.getpid(), bundle_root=str(bundle)))
    canonical_path(bundle/'results').mkdir(exist_ok=True); canonical_path(bundle/'collected').mkdir(exist_ok=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); resource.setrlimit(resource.RLIMIT_AS, (4*GIB, 4*GIB))
    started = time.monotonic()
    report = dict(schema=SCHEMA, status='running', ticket_sha256=digest, host=ticket['host'], limits=limits, claim=str(queue_claim),
        jobs=[], promotion_allowed=False, scope='finite native execution and verified worker-side collection')
    def save(): canonical_path(bundle/'queue-report.json').write_text(json.dumps(report, indent=2)+'\n')
    def guard():
        need(time.monotonic()-started < ticket['max_seconds'] and sha(ticket_path) == digest, 'finite queue time/ticket identity')
        need(shutil.disk_usage(bundle).free >= 10*GIB+256*MIB, 'queue durable floor/reservation')
        for name, value in ticket['worker_sources'].items(): need(sha(worker/name) == value, 'worker drift')
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        need(int(mem['MemAvailable'].split()[0])*1024 >= 4*GIB, 'host memory floor')
    def interrupted(number, frame): raise RuntimeError('termination signal '+str(number))
    previous = signal.signal(signal.SIGTERM, interrupted)
    completed = {}
    try:
        save(); guard()
        for job, manifest, root in jobs:
            pause_check(ticket)
            entry = dict(id=job['id'], owner=job['owner'], track=job['track'], status='running', handler=job['handler'],
                evidence_class=job['evidence_class'], build_key=job['build_key'], run_key=job['run_key'], promotion_allowed=False,
                raw_worker_output=job['native_output'], raw_launcher_output=str(bundle/('launch-'+job['id'])))
            report['jobs'].append(entry); save()
            for dependency in job['dependencies']:
                need(completed.get(dependency['job_id']) == dependency['required_status'], 'dependency execution/collection gate')
            for gate in job['review_gates']: receipt_gate(bundle, gate)
            need(sha(bundle/job['manifest']['path']) == job['manifest']['sha256'], 'manifest drift')
            policy.check_sources(root, manifest['sources']); policy.tools_for(profile)
            pause_check(ticket)
            claim_path = claim(registry, job['run_key'], dict(status='claimed_no_automatic_retry', job_id=job['id'],
                ticket_sha256=digest, build_key=job['build_key'], output=job['native_output'], pid=os.getpid()))
            entry['claim'] = str(claim_path); save()
            job_started = time.monotonic()
            def job_guard():
                guard(); need(time.monotonic()-job_started < job['max_seconds'], 'per-job time budget')
                policy.check_sources(root, manifest['sources'])
            output = Path(job['native_output'])
            if job['handler'] == 'source-gate-v1':
                logdir = bundle/('launch-'+job['id']); fresh_path(logdir).mkdir()
                command = [str(tools['taskset']), '-c', ','.join(map(str, profile['cpus'])), str(tools['python']), '-B',
                    str(root/'tools/native_source_gate_v1.py'), '--manifest', str(bundle/job['manifest']['path']),
                    '--manifest-sha256', job['manifest']['sha256'], '--output', str(output)]
                step, failure = checked_process(command, root, policy.clean_env(root, logdir, profile), logdir, 'launcher', 3600, job_guard)
                entry['launcher'] = step; save()
                if failure: raise failure
                need(step['returncode'] == 0, 'source-gate launcher completed')
            else: qualified_run(job, manifest, root, bundle, output, policy, identity, profile, tools, limits, job_guard)
            job_guard()
            collection = collect_evidence(output, bundle/job['collection'], manifest, job['manifest']['sha256'], profile, job['handler'])
            job_guard()
            entry.update(status='needs_independent_review', report_sha256=collection['report_sha256'],
                         collection=str(bundle/job['collection']), seconds=time.monotonic()-job_started)
            completed[job['id']] = entry['status']; save()
        guard(); policy.tools_for(profile)
        report['status'] = 'needs_independent_review'
    except BaseException as error:
        report.update(status='paused_no_new_jobs' if isinstance(error, QueuePaused) else 'failed_or_incomplete', error=repr(error))
        if report['jobs'] and report['jobs'][-1]['status'] == 'running':
            entry = report['jobs'][-1]
            entry.update(status='not_started_paused' if isinstance(error, QueuePaused) else 'failed_or_incomplete', error=repr(error))
            if not isinstance(error, QueuePaused):
                try:
                    failed_directory = bundle/'failed-collected'/entry['id']
                    failed = collect_failed_evidence(Path(entry['raw_worker_output']), failed_directory, Path(entry['raw_launcher_output']))
                    entry['failed_collection'] = str(failed_directory); entry['failed_files'] = failed['files']
                except BaseException as collection_error: entry['failed_collection_error'] = repr(collection_error)
        attempted = {entry['id'] for entry in report['jobs'] if entry['status'] != 'not_started_paused'}
        report['not_started'] = [job['id'] for job, _, _ in jobs if job['id'] not in attempted]
        raise
    finally:
        report['seconds'] = time.monotonic()-started; save(); signal.signal(signal.SIGTERM, previous)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ticket', type=Path, required=True); parser.add_argument('--ticket-sha256', required=True)
    args = parser.parse_args(); print(json.dumps(execute(args.ticket, args.ticket_sha256), indent=2))


if __name__ == '__main__': main()
