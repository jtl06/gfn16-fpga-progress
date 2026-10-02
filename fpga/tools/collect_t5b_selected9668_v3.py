"""Collect exact completed STA evidence, never modify the original project."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
from datetime import datetime, timezone

WORKER = Path('/home/ubuntu/gfn16-worker')
NAME = 'core27-t5b-selected9668-audit-m8azn-v3'
OUT = WORKER / NAME
ORIGINAL = WORKER / 'core27-t5b-provisional64-cpu6-100-v1'
UNIT = 'gfn16-t5b-selected9668-audit-m8azn-v3.service'
INV = '4a27637ff79540978005d3767550c54b'
PROPOSAL = '8a14a814b813ec1f74afcf92672258ea042f709a9ef94aa83dd2c2a7d75420de'
RECEIPT = '9c80dbf37722d0f57395fff57b1da8e5fa42e6258d500746035934587b84b87b'
LIMIT = 512 * 1024 * 1024


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(path):
    need(path.is_file() and not path.is_symlink(), 'regular evidence file: ' + str(path))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return dict(sha256=h.hexdigest(), size=path.stat().st_size)


def inventory(root):
    files = {}
    for path in sorted(root.rglob('*')):
        need(not path.is_symlink(), 'symlink evidence rejected')
        if path.is_file():
            files[str(path.relative_to(root))] = pin(path)
    return files


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main():
    need(pin(OUT / 'receipt.json')['sha256'] == RECEIPT, 'frozen terminal receipt')
    r = json.loads((OUT / 'receipt.json').read_text())
    need(r['proposal_sha256'] == PROPOSAL and r['original_unchanged'] is True
         and not r['final_verification_errors'], 'terminal source/final guards')
    need(r['status'] == 'passed_scoped_T5b_selected9668_STA_pending_independent_archive_review', 'actual scoped terminal pass')
    for phase in ('baseline100', 'selected_clock'):
        need(len(r['timing'][phase]) == 4 and r['timing']['path_groups'][phase]['observed_paths'] == 4000
             and r['timing']['path_groups'][phase]['observed_failing_paths'] == 0, 'four-corner/path closure')
    raw = subprocess.check_output(['journalctl', '-u', UNIT, '-o', 'json', '--no-pager'], text=True)
    journal = [json.loads(line) for line in raw.splitlines()]
    exact = [row for row in journal if row.get('UNIT') == UNIT and row.get('INVOCATION_ID') == INV]
    start = [row for row in exact if row.get('JOB_TYPE') == 'start' and row.get('JOB_RESULT') == 'done']
    end = [row for row in exact if row.get('MESSAGE') == UNIT + ': Deactivated successfully.']
    need(len(start) == len(end) == 1 and len(exact) == len(journal), 'exact native invocation journal binding')
    need(PROPOSAL in start[0]['MESSAGE'] and 'aws_postfit_t5b_selected9668_m8azn_v3.py' in start[0]['MESSAGE'], 'native source command')
    current = subprocess.check_output(['systemctl', 'show', UNIT, '--property=MainPID,ActiveState,SubState,InvocationID,MemoryPeak,ExecMainStatus'], text=True)
    need('MainPID=0\n' in current and 'ActiveState=inactive\n' in current, 'no live unit at collection')
    elapsed = (int(end[0]['__MONOTONIC_TIMESTAMP']) - int(start[0]['__MONOTONIC_TIMESTAMP'])) / 1e6
    need(0 < elapsed < 2280, 'bounded native manager interval')
    unit = dict(schema='native-terminal-journal-proof-v1', unit=UNIT, invocation_id=INV,
                observed_at_utc=datetime.now(timezone.utc).isoformat(), terminal='deactivated_successfully',
                manager_start_realtime_us=start[0]['__REALTIME_TIMESTAMP'],
                manager_end_realtime_us=end[0]['__REALTIME_TIMESTAMP'],
                manager_elapsed_seconds=elapsed, current_systemctl_show=current,
                provenance='Exact native manager UNIT and INVOCATION_ID fields. Successful transient unit was garbage-collected; absent live properties are not reconstructed.',
                resource_journal=[row for row in exact if 'CPU_USAGE_NSEC' in row])
    save(OUT / 'native-unit-v1.json', unit)
    with (OUT / 'native-journal-v1.jsonl').open('x') as stream:
        stream.write(raw)
    post = inventory(ORIGINAL)
    need(post == r['original_before'] == r['original_after'], 'fresh original full-tree/QDB comparison')
    save(OUT / 'post-collection-original-v1.json', dict(status='unchanged',
         observed_at_utc=datetime.now(timezone.utc).isoformat(), files=post,
         original_count=len(post), qdb_count=sum(k.startswith('qdb/') for k in post)))
    files = {str(p.relative_to(OUT)): p for p in OUT.rglob('*')
             if p.is_file() and 'snapshot' not in p.relative_to(OUT).parts}
    need(len(r['snapshot_differences']) == 6, 'six allowed private-copy deltas')
    for rel in r['snapshot_differences']:
        p = OUT / 'snapshot' / rel
        need(pin(p) == r['snapshot_after'][rel], 'snapshot delta bytes')
        files['snapshot/' + rel] = p
    for rel, passed in r['cache_promotion_byte_comparisons'].items():
        need(passed is True and '/final/' in rel, 'explicit promoted cache proof')
        source = rel.replace('/final/', '/routed/')
        p = ORIGINAL / source
        need(pin(p) == r['original_before'][source] == pin(OUT / 'snapshot' / rel), 'routed/final exact cache bytes')
        files['cache-promotion-original/' + source] = p
    pins = {name: pin(path) for name, path in sorted(files.items())}
    need(sum(row['size'] for row in pins.values()) <= LIMIT, 'finite collected archive byte bound')
    save(OUT / 'collection-inventory-v1.json', dict(schema='native-collection-inventory-v1',
         files=pins, files_count=len(pins), total_bytes=sum(row['size'] for row in pins.values()),
         scope='All native audit outputs, changed private-copy reports/cache, original cache byte comparisons; unchanged original/full QDB remains preserved on worker and pinned before/after.'))
    files['collection-inventory-v1.json'] = OUT / 'collection-inventory-v1.json'
    archive = WORKER / (NAME + '-native.tar.gz')
    need(not archive.exists(), 'write-once archive')
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        for name, path in sorted(files.items()):
            tar.add(path, arcname=NAME + '/' + name, recursive=False)
    print(json.dumps(dict(archive=str(archive), archive_pin=pin(archive),
          inventory_pin=pin(OUT / 'collection-inventory-v1.json'), receipt_sha256=RECEIPT,
          files=len(pins), bytes=sum(row['size'] for row in pins.values()), elapsed_seconds=elapsed)))


if __name__ == '__main__':
    main()
