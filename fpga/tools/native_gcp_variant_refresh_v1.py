"""Fresh GCP accounting for an unclaimed immutable same-profile native variant.

No host moves, model/source changes, unit launch or claimed-attempt replay.
The dispatcher retains one logical claim and atomically adopts the fresh packet.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
RUNNERS = {
    'tools/native_class_package_v1.py': '61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932',
    'tools/native_class_package_v2.py': '03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604',
    'tools/native_class_package_gcp24_v1.py': '39a85fbde4a87b773fc51fb0fad65f7a21e7549c91bd6d13f7dd33b404ef1d32'}
METER_SHA = '6fd1904025f4d76557497dba2eac2a5514b419a799c8616b177bc696f051379a'
MATCHER_SHA = '8993b204cb4666a010c46d87b78c9c35d26f510aaca002ab2ac0095b7fb7fbdb'


def need(ok, why):
    if not ok: raise ValueError('GCP refresh: ' + why)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, pin):
    path = HERE.parent / name; need(sha(path) == pin and not path.is_symlink(), 'exact helper pin')
    spec = importlib.util.spec_from_file_location('_gcp_refresh_' + path.stem, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def dump(path, value):
    with path.open('x') as stream: json.dump(value, stream, indent=2); stream.write('\n')


def repackage_variant(existing_package_dir, runner, new_native_id, output):
    need(runner in RUNNERS, 'known serial GCP runner; no long/threaded conversion')
    old, out = Path(existing_package_dir), Path(output)
    need(old.is_absolute() and old.resolve() == old and old.is_dir(), 'canonical template')
    need(out.is_absolute() and out.resolve() == out and not out.exists(), 'fresh output')
    ticket = json.loads((old / 'ticket.json').read_text()); manifest = json.loads((old / 'manifest.json').read_text())
    need(sha(old / 'manifest.json') == ticket['manifest_sha256'], 'manifest/ticket identity')
    need(manifest['sources'].get(runner) == RUNNERS[runner], 'same pinned original runner')
    need(ticket['id'] != new_native_id and ticket['max_seconds'] == 3700 and ticket['phase'] == 'run', 'fresh finite3700 id')
    need(manifest['host'] == 'gfn16-pilot-c4d' and ticket['budget']['provider'] == 'gcp', 'GCP-only original variant')
    need(not (old / 'queue-report.json').exists() and not (old / 'output/native').exists(), 'unexecuted local template')
    root = old / 'capture/source/fpga'
    for name, pin in manifest['sources'].items():
        path = root / name; need(path.resolve() == path and path.is_file() and sha(path) == pin, 'complete immutable source closure')
    matcher = load('tools/native_profile_variants_v6.py', MATCHER_SHA)
    original_fingerprint = matcher.functional_fingerprint(manifest, ticket['budget'], root)['sha256']
    quote = load('cloud/host_hours_admit_v1.py', METER_SHA).admit('gcp-c4d', 3715)
    need(quote['status'] == 'PASS_budget_only_no_job_reservation' and quote['host_id'] == 'gcp-c4d'
         and quote['outer_runtime_plus_stop_seconds'] == 3715, 'fresh bounded host quote')
    role = json.loads(json.dumps(manifest)); role['sources'] = dict(manifest.get('budget_source_members', manifest['sources']))
    role.pop('budget_source_members', None)
    package = load(runner, RUNNERS[runner])
    out.mkdir(parents=True)
    try:
        dump(out / 'host-hours.json', quote)
        budget = dict(provider='gcp', observed_at=quote['observed_at_utc'], total_allowance_usd=100,
                      planning_usd_per_hour=quote['hourly_rate_usd'], remaining_after_reserves_usd=quote['remaining_total_after_storage_usd'],
                      actual_billing=False, source_receipt_sha256=sha(out / 'host-hours.json'))
        dump(out / 'budget.json', budget)
        source = out / 'role/fpga'; source.mkdir(parents=True)
        for name, pin in role['sources'].items():
            target = source / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target); need(sha(target) == pin, 'unchanged copied role')
        dump(out / 'role-manifest.json', role)
        prepared = package.prepare(out / 'role-manifest.json', source, ticket['profile'], new_native_id,
                                   'run', out / 'packet', out / 'budget.json')
        updated = json.loads((out / 'packet/manifest.json').read_text())
        need(matcher.functional_fingerprint(updated, budget, out / 'packet/capture/source/fpga')['sha256'] == original_fingerprint,
             'unchanged functional source/config/outputs')
        need(updated['build'] == manifest['build'] and updated['probe'] == manifest['probe'] and updated['steps'] == manifest['steps'],
             'exact build/probe/steps')
        need(all(sha(root / name) == pin for name, pin in manifest['sources'].items()), 'template stable after refresh')
        result = dict(prepared, status='refreshed_same_profile_not_executed', runner=runner, runner_sha256=RUNNERS[runner],
                      profile=ticket['profile'], max_seconds=3700, original_ticket_sha256=sha(old / 'ticket.json'),
                      functional_sha256=original_fingerprint, host_hours_sha256=sha(out / 'host-hours.json'),
                      same_logical_claim_required=True, old_inputs_preserved=True)
        dump(out / 'refresh-receipt.json', result); return result
    except BaseException as error:
        dump(out / 'failure.json', dict(status='failed_refresh_preserved', error=repr(error))); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('existing-package-dir', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--runner', required=True); parser.add_argument('--id', required=True)
    args = parser.parse_args()
    print(json.dumps(repackage_variant(args.existing_package_dir, args.runner, args.id, args.output), indent=2))
