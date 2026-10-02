"""F2 source-only reference data CLI for a finite admitted worker envelope.

No runner, HDL, remote transport, source mutation, or arithmetic replacement.
The v3 host wrapper reuses exact frozen v2 arithmetic code/defaults and rejects
Mac/unrecognized full-numeric contexts. Outputs are write-once artifacts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform

from fpga.reference import root_lookahead_field_host_v3 as field


HOST_SHA = '806849d97b5b3a28a7a80fe2ca789fe26f15f2346ba0df8189169e601dde13d3'


def generate(aw, index, profile, output, receipt):
    field.parent.need(field.sha(field.__file__) == HOST_SHA, 'pinned F2 host-only successor')
    output, receipt = Path(output), Path(receipt)
    field.parent.need(output != receipt and not output.exists() and not receipt.exists(),
                      'distinct fresh F2 vector and receipt')
    for path in (output, receipt):
        field.parent.need(path.is_absolute() and path.parent.is_dir() and
                          path.parent.resolve() == path.parent and not path.is_symlink(),
                          'canonical existing output parents')
    field.configure(profile)
    vectors, meta = field.corpus(aw, index)
    raw = vectors.encode()
    meta.update(schema='F2-field-vector-receipt-v3', vector_sha256=hashlib.sha256(raw).hexdigest(),
                vector_bytes=len(raw), generator_sha256=field.sha(__file__),
                hostname=platform.node(), platform=platform.system(), numeric_full_N=aw == 16,
                requires_linux_profile=aw > 8, native_RTL_executed=False,
                source_and_resource_envelope_required=True)
    with output.open('xb') as stream:
        stream.write(raw)
    with receipt.open('x') as stream:
        json.dump(meta, stream, indent=2)
        stream.write('\n')
    return meta


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw', type=int, required=True)
    parser.add_argument('--field', type=int, required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.aw, args.field, args.profile, args.output, args.receipt), indent=2))
