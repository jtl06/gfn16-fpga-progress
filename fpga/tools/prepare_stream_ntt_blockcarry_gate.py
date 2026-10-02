"""Prepare a fresh pinned CPU-only S1 bundle. Does not dispatch or modify RTL."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[2]
FILES=(
    'fpga/reference/stream_ntt_blockcarry_schedule.py',
    'fpga/reference/stream_ntt_schedule.py',
    'fpga/reference/stream_ntt_model.py',
    'fpga/reference/stream_ntt_blockwrap2_proposal.py',
    'fpga/synthesis/summarize.py',
    'fpga/tests/test_stream_ntt_blockcarry_schedule.py',
    'fpga/tests/test_stream_ntt_schedule.py',
    'fpga/tools/stream_ntt_blockcarry_model_gate.py',
    'fpga/tools/prepare_stream_ntt_blockcarry_gate.py',
)


def prepare(destination):
    destination=destination.resolve()
    if ROOT not in destination.parents:raise ValueError('destination must be fresh under this workspace')
    payloads={name:(ROOT/name).read_bytes() for name in FILES}
    inventory={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
               for name,data in payloads.items()}
    manifest=dict(schema='stream-ntt-blockcarry-schedule-stage-v1',source_only=True,
        scope='CPU Python model gate; no HDL/vendor/physical qualification',
        files=inventory,expected_file_count=len(FILES),
        proposed_command=['python3','-B','fpga/tools/stream_ntt_blockcarry_model_gate.py',
            '--n','65536','--parallel','8','--run-full-joined','--max-seconds','900'],
        proposed_limits=dict(CPU_threads=1,address_space_bytes=2*1024**3,wall_seconds=900),
        cases='P8 two dependent epochs, double0/1, at explicit minimum base and1e9',
        automatic_dispatch=False)
    manifest_bytes=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
    buffer=io.BytesIO()
    with gzip.GzipFile(fileobj=buffer,mode='wb',mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w') as archive:
            for name,data in sorted(payloads.items()):
                info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o444;info.mtime=0
                archive.addfile(info,io.BytesIO(data))
    archive_bytes=buffer.getvalue()
    destination.mkdir(parents=False,exist_ok=False)
    (destination/'manifest.json').write_bytes(manifest_bytes)
    (destination/'source.tar.gz').write_bytes(archive_bytes)
    return dict(path=str(destination),manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        archive_sha256=hashlib.sha256(archive_bytes).hexdigest(),archive_bytes=len(archive_bytes),files=len(FILES))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(parser.parse_args().output),sort_keys=True))
