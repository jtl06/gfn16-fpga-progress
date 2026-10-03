"""Private B measurement input over the existing finite-reference queue.

No transport, native execution, scheduler, HDL, or arithmetic in preparation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = 'r93-b-host-conversion-aethia-v1'
EXECUTOR_SHA = '4ddf0f4e289b64547a78efeeeb09331b4adb690a6d3f55671ea3894745d24295'


def prepare(output):
    from fpga.tools import native_reference_command_v2 as executor
    from fpga.tools import global_queue_v1 as queue
    output = Path(output).resolve()
    executor.need(output.is_relative_to(ROOT) and not output.exists(), 'fresh private B measurement input')
    executor.need(hashlib.sha256(Path(executor.__file__).read_bytes()).hexdigest() == EXECUTOR_SHA,
                  'tested finite reference recipe source')
    host = json.loads((ROOT / 'queue/hosts/aethia-light-q1.json').read_text())
    executor.need(host['name'] == 'aethia' and host['enabled'] is True, 'actual enabled aethia descriptor')
    package = executor.prepare_host_measurement(IDENTITY, 'aethia-static02-v1', output, repetitions=3)
    logical = dict(schema='gfn16-global-ticket-v1', id=IDENTITY, owner='independent-review',
                   created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                   priority='P3', kind='reference', needs='verilator',
                   tool_identity=host['tool_identity'], allowed_hosts=['aethia'], promotion_bound=False,
                   resources=dict(cores=2, threads=1, ram_gib=4, scratch_gib=4), est_minutes=2,
                   package=package)
    queue.validate(logical)
    with (output / 'global-ticket.json').open('x') as stream:
        json.dump(logical, stream, indent=2); stream.write('\n')
    return dict(id=IDENTITY, ticket=str(output / 'global-ticket.json'),
                status='source_prepared_not_submitted', native_measurement=False,
                scope='One synthetic host conversion/finalization timing recipe, no HDL or B-core equivalence')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
