"""Build an immutable source-only A10 envelope; no staging/SSH/run/native work."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

from fpga.tools import run_merged_negacyclic27_software_gate as frozen
from fpga.tools import run_a10_software_aethia_v1 as envelope

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/a10_software_aethia_prepare_v1.py'
TEST = 'tests/test_a10_software_aethia_prepare_v1.py'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sources():
    original_path = ROOT / envelope.ORIGINAL_MANIFEST
    envelope.need(sha(original_path) == envelope.ORIGINAL_SHA, 'unchanged original A10 manifest')
    original = json.loads(original_path.read_text())
    envelope.need(original == frozen.prepare(ROOT), 'exact frozen A10 manifest/source replay')
    return {**original['sources'], **{name: sha(ROOT / name) for name in
            (envelope.ORIGINAL_MANIFEST, envelope.SELF, SELF, TEST)}}


def manifest(pins):
    return dict(schema='a10-aethia-software-envelope-v1', status='prepared_not_executed',
                host='aethia', source_root=str(envelope.SOURCE), output_parent=str(envelope.BASE),
                sources=pins, original_manifest=envelope.ORIGINAL_MANIFEST,
                original_manifest_sha256=envelope.ORIGINAL_SHA, cpus=[0, 2], cpu_quota_percent=200,
                memory_max_bytes=6 << 30, swap_max_bytes=0, timeout_seconds=1200,
                python_path=str(envelope.PYTHON), python_sha256=envelope.PYTHON_SHA,
                shared_compile_lock=False, HDL_or_native_compiler=False,
                promotion_allowed=False)


def prepare(output):
    envelope.need(not (ROOT / 'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    output = Path(output).resolve()
    envelope.need(not output.exists(), 'fresh stage only')
    pins = sources()
    source = output / 'source/fpga'
    source.mkdir(parents=True)
    for name in sorted(pins):
        dest = source / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    envelope.check_sources(source, pins)
    path = output / 'approved-manifest.json'
    path.write_text(json.dumps(manifest(pins), indent=2) + '\n')
    with tarfile.open(output / 'source.tar.gz', 'x:gz') as archive:
        for name in sorted(pins):
            archive.add(source / name, arcname='fpga/' + name, recursive=False)
    envelope.need(sources() == pins, 'post-prepare live source drift')
    result = dict(status='prepared_A10_AW16_aethia_Python_only_not_executed', sources=pins,
                  manifest_sha256=sha(path), source_archive_sha256=sha(output / 'source.tar.gz'),
                  source_root=str(envelope.SOURCE), output_parent=str(envelope.BASE),
                  command=[str(envelope.PYTHON), '-I', '-B', str(envelope.SOURCE / envelope.SELF),
                           '--manifest', str(envelope.BASE / 'approved-manifest-v1.json'),
                           '--manifest-sha', sha(path)],
                  external_service_bounds=dict(taskset='0,2', CPUQuota='200%', MemoryMax='6G',
                                               MemorySwapMax='0', RuntimeMaxSec=1230, TimeoutStopSec=10),
                  output_retention='Unique artifacts-aw16-v1 directory; stdout/stderr/context/result and gate receipt retained on failure.',
                  scope='Python arithmetic only; no source profile adoption, RTL, fit or native simulation.',
                  deployment_or_dispatch_performed=False, promotion_allowed=False)
    (output / 'preparation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
