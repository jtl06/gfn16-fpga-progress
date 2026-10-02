"""Read-only FL-r2 owner restore plan; stdout is a plan, not an executor.

Run from any directory: python3 /path/to/fpga/tools/owner_restore_plan_v1.py
Root checks collaboration.list_agents and invokes actual followup_task tools.
No shell command can invoke those agent tools. This command never starts jobs,
writes statuses, creates threads, changes permissions, or admits a candidate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


# Existing owner routing from FL-r2; not a scheduler or new ownership scheme.
PRIORITY = {
    'fit_queue_sol': 'now', 'root_timing_candidate': 'now',
    'azure_simulation': 'now', 'azure_burst_host': 'now',
    'quartus_prefit': 'now', 'block_carry': 'now', 'merged_ntt_model': 'now',
    'stream_interface': 'now', 'radix22_sol': 'now', 't5b_e2e': 'now',
    'soak_chunks': 'now', 'independent_review': 'now', 't5_qualification': 'now',
    'threaded_aw16': 'next', 'sim_compile_slots': 'next',
}
PARKED = {'dashboard', 'public_alpha', 'formal', 'formal_verification'}
INACTIVE = {'complete', 'completed', 'parked', 'later', 'deferred'}
NAME = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
FIELD = re.compile(r'^\s*(?:-\s*)?([A-Za-z][A-Za-z0-9 /_-]*):\s*(.+)$')


def fields(source):
    result = {}
    for line in source.splitlines():
        match = FIELD.match(line.replace('**', ''))
        if match:
            result.setdefault(match[1].strip().lower(), []).append(match[2].strip())
    return result


def first(data, *labels):
    for label in labels:
        if data.get(label):
            return data[label][0]
    return None


def owner_state(source):
    # Only an explicit whole-owner marker counts. A completed gate or receipt
    # in the body must not suppress an owner who has active follow-up work.
    header = source.split('\n## ', 1)[0]
    data = fields(header)
    value = first(data, 'restore', 'status')
    if value:
        token = re.split(r'[\s,;—:.()]+', value.lower(), maxsplit=1)[0]
        if token in INACTIVE | {'active', 'waiting', 'blocked'}:
            return token
    return 'not_explicitly_declared'


def build_plan(repo, *, only=(), ready=()):
    repo = Path(repo).resolve()
    folder = repo / 'fpga/docs/briefs/replies/status'
    if not folder.is_dir():
        raise ValueError('owner status directory is missing')
    only, ready = set(only), set(ready)
    for owner in only | ready:
        if not NAME.fullmatch(owner):
            raise ValueError('invalid owner name: ' + owner)
    records, followups, skipped, seen = [], [], [], set()
    for path in sorted(folder.glob('*.md')):
        owner = path.stem
        if not NAME.fullmatch(owner) or path.is_symlink():
            raise ValueError('unsafe owner status path: ' + str(path))
        seen.add(owner)
        if only and owner not in only:
            continue
        raw = path.read_bytes()
        if len(raw) > 65536:
            raise ValueError('owner status exceeds64KiB: ' + owner)
        source = raw.decode('utf-8')
        data = fields(source)
        state = owner_state(source)
        record = dict(owner=owner, status_path=str(path),
            status_sha256=hashlib.sha256(raw).hexdigest(), restore_state=state,
            priority=PRIORITY.get(owner, 'unranked'),
            current_candidate=first(data, 'current candidate', 'candidate', 'current work', 'now', 'current gate'),
            next_step=first(data, 'next step', 'next', 'next concrete result', 'next gates'),
            blocker=first(data, 'blockers', 'blocker', 'current blocker', 'current dependency'),
            last_receipt=first(data, 'last receipt'),
            status_context=[line.strip() for line in source.splitlines()
                if line.strip() and not line.lstrip().startswith('#')
                and not re.match(r'^\s*(?:-\s*)?(?:Owner|Updated|Restore):', line, re.I)][:4],
            receipt_context=[line.strip() for line in source.splitlines()
                if re.search(r'\breceipt\b|\bevidence\s*:', line, re.I)][:4])
        records.append(record)
        reason = None
        if owner == 'main':
            reason = 'root orchestrator; not an owner follow-up target'
        elif owner in PARKED and owner not in ready:
            reason = 'FL-r2 parked owner'
        elif state in INACTIVE and owner not in ready:
            reason = 'explicit whole-owner ' + state
        elif owner not in PRIORITY and owner not in ready:
            reason = 'unranked owner; root verifies current authorized priority first'
        if reason:
            skipped.append(dict(owner=owner, reason=reason))
            continue
        context = '\n'.join(label + ': ' + str(record[key]) for label, key in (
            ('Recorded current candidate/work', 'current_candidate'),
            ('Recorded next step', 'next_step'), ('Recorded blocker', 'blocker'),
            ('Explicit last receipt', 'last_receipt')) if record[key] is not None)
        if record['current_candidate'] is None or record['blocker'] is None or record['last_receipt'] is None:
            context += '\nUnlabeled status context (not inferred admission or newest receipt):\n' + '\n'.join(record['status_context'])
        if record['last_receipt'] is None and record['receipt_context']:
            context += '\nReceipt context; identify the actual latest receipt by reading the status:\n' + '\n'.join(record['receipt_context'])
        prompt = (
            'Resume your existing owned task, not a new candidate or framework. Read '
            'fpga/AGENTS.md, docs/briefs/README.md, latest FL-r2 priorities and your '
            'owner-relevant briefs. Then reread your sole-writer status at ' + str(path) +
            ' (snapshot SHA256 ' + record['status_sha256'] + ').\n' + context + '\n'
            'Status is context, not live host admission. Recheck any existing job/unit '
            'and predecessor terminal/release before acting; retain original sources, '
            'failures and evidence. Existing static serial lanes suffice: fresh '
            'source/tool/PAUSE/core/RAM/runtime/byte-and-inode-quota/budget guards '
            'remain mandatory, without main pre-job review or a dynamic-observer gate. '
            'One candidate in flight plus at most one queued. Continue the next bounded '
            'in-scope action, coordinate directly with its owner/dispatcher, update '
            'your status and milestone reply, and send main only needs-main or milestones. '
            'No new hosts, spend authority, protected deadline changes or broad cleanup. '
            'If this completed/deferred owner was explicitly marked dependency-ready, '
            'resume only that now-ready existing dependency; do not revive parked scope.')
        followups.append(dict(priority=record['priority'], dependency_ready=owner in ready,
            tool='collaboration.followup_task',
            arguments=dict(target='/root/' + owner, message=prompt)))
    followups.sort(key=lambda item: ({'now': 0, 'next': 1}.get(item['priority'], 2), item['arguments']['target']))
    expected = only if only else set(PRIORITY)
    return dict(schema='owner-restore-plan-v1', read_only=True, calls_are_drafts=True,
        instructions=[
            'Root reads this plan; it does not execute anything.',
            'Call the actual collaboration.list_agents tool and match existing owner paths before invoking actual collaboration.followup_task.',
            'Missing owner handles are not recreated by this command; root handles restart ownership using available collaboration tools and current authority.',
            'Do not follow up an already-running owner merely to duplicate its task. Send only a necessary new handoff; after restart resume idle existing owners.',
            'Not-declared receipt/blocker/state values are not evidence of completion or admission. Reread the exact status path and relevant receipt.',
            'Use --ready OWNER only for an explicitly now-ready existing dependency; it does not authorize parked scope.'],
        inventory=records, skipped=skipped, missing_status_owners=sorted(expected - seen),
        followup_tasks=followups)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--owner', action='append', default=[], help='focus on an existing owner; repeatable')
    parser.add_argument('--ready', action='append', default=[], help='explicitly ready existing dependency; repeatable')
    args = parser.parse_args()
    try:
        print(json.dumps(build_plan(args.repo, only=args.owner, ready=args.ready), indent=2))
    except (ValueError, UnicodeError, OSError) as error:
        parser.exit(2, 'restore plan refused: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
