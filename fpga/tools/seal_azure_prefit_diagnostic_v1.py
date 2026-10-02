"""Seal a prepared diagnostic with its exact atomic budget reservation."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def seal(stage, reservation_path):
    payload_path = stage/'payload.json'
    payload = json.loads(payload_path.read_text())
    reservation_raw = reservation_path.read_bytes()
    reservation = json.loads(reservation_raw)
    row = reservation['reservation']
    if (reservation['status'] != 'reserved_budget_only' or row['job_id'] != payload['job_id'] or
            row['packet_sha256'] != payload['payload_sha256'] or row['host_id'] != 'azure-f16' or
            row['outer_runtime_max_seconds'] != 840 or row['stop_grace_seconds'] != 60):
        raise ValueError('exact diagnostic budget reservation required')
    remote = '/home/azureuser/gfn16-worker/quartus-prefit-qualification-tools-v1/'+payload['job_id']+'-budget.json'
    payload['budget_reservation_path'] = remote
    payload['budget_reservation_sha256'] = sha(reservation_raw)
    with (stage/'budget-reservation.json').open('xb') as stream:
        stream.write(reservation_raw)
    final = json.dumps(payload, indent=2).encode()+b'\n'
    with (stage/'dispatch-packet.json').open('xb') as stream:
        stream.write(final)
    receipt = dict(status='sealed_not_dispatched', packet_sha256=sha(final),
                   reservation_sha256=sha(reservation_raw), remote_reservation_path=remote,
                   remote_packet_path=remote.replace('-budget.json', '-packet.json'), unit=payload['unit'])
    with (stage/'seal-receipt.json').open('x') as stream:
        json.dump(receipt, stream, indent=2); stream.write('\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('stage', type=Path)
    p.add_argument('reservation', type=Path); a = p.parse_args(); seal(a.stage, a.reservation)
