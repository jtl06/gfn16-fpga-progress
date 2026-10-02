"""Prepare exactly five source-identical GCP infrastructure successors.

Metadata/package construction only. Never launches, retries a worker namespace,
imports a numeric oracle, or treats the wrong-host attempt as arithmetic proof.
The public queue API independently rechecks the single-successor invariant.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'tools/native_class_package_v2.py'
PACKAGE_SHA = '03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
DURATION_SHA = 'ccd3602422b315d32806cfae44d6a526efd37a57791d8787135f9dc389373980'
HOST = 'gfn16-pilot-c4d'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def validate_original(ticket, index):
    need(type(index) is int and 3 <= index <= 7, 'only cancelled chunks03..07')
    need(ticket['id'] == f'soak-t5b-aw16-chunk-{index:02d}-q3-v1'
         and ticket['owner'] == 'soak-chunks'
         and ticket['tool_identity'] == 'gcp-c4d-verilator5032-gcc15-python314-v1'
         and not ticket.get('infra_retry_of'), 'exact original owner/tool/id')
    result = ticket['result']
    need(result['status'] == 'terminal_infrastructure_failure'
         and result['classification'] == 'verified_source_host_inadmission_cancelled_not_arithmetic'
         and result['one_fresh_original_host_successor_permitted'] is True
         and result['automatic_resource_retry'] is False, 'explicit infrastructure disposition')
    props = result['properties']
    need(props['MainPID'] == '0' and props['ControlGroup'] == ''
         and props['InvocationID'] == ticket['dispatch']['invocation']
         and bool(props['ExecMainExitTimestamp']), 'actual terminal invocation and empty cgroup')
    inadmission = ticket['source_host_inadmission']
    need(inadmission['host'] == ticket['dispatch']['host'] == 'gfn16-azure-sim-f32'
         and inadmission['invocation'] == ticket['dispatch']['invocation']
         and inadmission['promotion_allowed'] is False, 'preserved wrong-host evidence')


def prepare(manifests, activation, done, budget, output):
    need(sha(ROOT / PACKAGE) == PACKAGE_SHA, 'frozen shared packager')
    spec = importlib.util.spec_from_file_location('_soak_infra_packager', ROOT / PACKAGE)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    manifests, activation, done, budget, output = map(lambda p: Path(p).resolve(),
                                                    (manifests, activation, done, budget, output))
    need(not output.exists(), 'fresh successor batch')
    duration = activation / 'duration-admission.json'
    need(sha(duration) == DURATION_SHA, 'unchanged GCP measured duration proof')
    originals = []
    for index in range(3, 8):
        old = done / f'soak-t5b-aw16-chunk-{index:02d}-q3-v1.json'
        ticket = json.loads(old.read_text())
        validate_original(ticket, index)
        originals.append((index, old, ticket))
    output.mkdir(parents=True)
    prepared = []
    for index, old, original in originals:
        segment = f'chunk-{index:02d}'
        component = output / segment
        component.mkdir()
        ticket = json.loads((activation / (segment + '-global-ticket.json')).read_text())
        need(ticket['id'] == original['id'] and ticket['owner'] == original['owner']
             and ticket['tool_identity'] == original['tool_identity']
             and ticket['measured_runtime_admission']['sha256'] == DURATION_SHA,
             'unchanged admitted role')
        ticket['id'] = f'soak-t5b-aw16-{segment}-q3-v2'
        ticket['created'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        ticket['infra_retry_of'] = original['id']
        ticket['allowed_hosts'] = [HOST]
        ticket['infrastructure_disposition'] = dict(path=str(old), sha256=sha(old),
            classification=original['result']['classification'], arithmetic_failure_inferred=False)
        packages = []
        manifest_file = manifests / segment / 'serial-manifest.json'
        manifest = json.loads(manifest_file.read_text())
        need(manifest['soak']['case_id'] == '2730e05de298ecbf5d7125acb7d6859b581b21ed8c84fb1bbfd7d3aaccd007ba'
             and manifest['soak']['segment'] == segment and len(manifest['steps']) == 1
             and manifest['steps'][0]['validator']['config'] == {'negative': 'none'},
             'same normal-only full-case segment')
        for pair in ('01', '23'):
            template = next(p for p in ticket['packages'] if p['profile'] == f'gcp-c4d-static{pair}-v1')
            prior = json.loads((Path(template['archive']).parent / 'manifest.json').read_text())
            need(all(manifest[k] == prior[k] for k in ('build', 'probe', 'steps', 'soak'))
                 and all(prior['sources'].get(name) == pin for name, pin in manifest['sources'].items()),
                 'byte-pinned candidate sources/build/probe/steps unchanged')
            packet = component / ('p' + pair)
            job = ticket['id'] + '-p' + pair
            result = worker.prepare(manifest_file, manifests / segment / 'source/fpga',
                                    template['profile'], job, 'run', packet, budget)
            prepared_manifest = json.loads((packet / 'manifest.json').read_text())
            need(all(prepared_manifest[k] == prior[k] for k in ('sources', 'build', 'probe', 'steps', 'soak')),
                 'complete shared and candidate source closure remains identical')
            package = deepcopy(template)
            package.update(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
                           ticket_sha256=result['ticket_sha256'], manifest_sha256=sha(packet / 'manifest.json'),
                           worker_id=job, native_root=result['native_root'])
            packages.append(package)
        ticket['packages'] = packages
        path = component / 'global-ticket.json'
        dump(path, ticket)
        prepared.append(dict(id=ticket['id'], ticket=str(path), ticket_sha256=sha(path),
                             infra_retry_of=original['id'], original_sha256=sha(old)))
    receipt = dict(schema='T5b-soak-infrastructure-successors-v1',
                   status='prepared_five_GCP_only_successors_not_dispatched', tickets=prepared,
                   source_identical=True, arithmetic_executed=False, HDL_executed=False,
                   continuous_admitted=False, budget_sha256=sha(budget), duration_sha256=DURATION_SHA)
    dump(output / 'prepare-receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifests', 'activation', 'done', 'budget', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.manifests, args.activation, args.done, args.budget, args.output), indent=2))
