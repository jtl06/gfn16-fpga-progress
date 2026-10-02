"""Prepare a fresh, single-role exact diagnostic-debt gate; no dispatch."""
import argparse
import json
from pathlib import Path
import shutil
import tarfile
from fpga.tools import native_root_lookahead_debt_v3 as gate

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT/'artifacts/root-lookahead-cpu02-wall-v2-prepared'
FAILED = ROOT/'results/throughput-20260929/root-lookahead-cpu02-wall-l16-f0-v1'


def prepare(output):
    gate.require(not (ROOT/'docs/briefs/PAUSE').exists(), 'PAUSE')
    gate.require(gate.digest((PACKET/'manifest.json').read_bytes()) == gate.BASELINE_SHA, 'parent manifest')
    old = json.loads((PACKET/'manifest.json').read_text())
    parent = PACKET/'source/fpga'
    gate.require({str(p.relative_to(parent)):gate.digest(p.read_bytes()) for p in parent.rglob('*') if p.is_file()}
                 == old['sources'], 'parent closure')
    gate.adapted_source((ROOT/gate.PARENT).read_bytes())
    output = Path(output).resolve()
    gate.require(not output.exists(), 'fresh output')
    source = output/'source/fpga'
    shutil.copytree(parent, source)
    additions = {gate.SELF: ROOT/gate.SELF,
                 'reference/root_lookahead_debt_prepare_v3.py': Path(__file__).resolve(),
                 'tests/test_root_lookahead_debt_v3.py': ROOT/'tests/test_root_lookahead_debt_v3.py',
                 gate.BASELINE: PACKET/'manifest.json',
                 gate.REVIEW: FAILED/'independent-failed-lint-review-v1.json',
                 gate.STDERR: FAILED/'lint.stderr.log'}
    for name, path in additions.items():
        target = source/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    manifest = dict(old)
    manifest.update(source_root=gate.ROOT, output_parent=str(Path(gate.ROOT).parents[1]),
                    sources={str(p.relative_to(source)):gate.digest(p.read_bytes())
                             for p in source.rglob('*') if p.is_file()})
    manifest['admission'] = dict(old['admission'], launcher=gate.SELF,
        lint_success_required_before_build=False, lint_diagnostic_admission_required_before_build=True,
        lint_warning_waivers=['exact-two-inherited-records-L16-F0-only'],
        limitation='Raw -Wall rc1 remains failed lint; exact source/tool/argv/diagnostics accepted as reviewed debt, never clean lint.')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    with tarfile.open(output/'source.tar.gz', 'x:gz') as archive:
        for name in sorted(manifest['sources']):
            archive.add(source/name, arcname='fpga/'+name, recursive=False)
    receipt = dict(status='prepared_NOT_dispatched', scope='L16/F0 component only',
        parent_manifest_sha256=gate.BASELINE_SHA,
        manifest_sha256=gate.digest((output/'manifest.json').read_bytes()),
        archive_sha256=gate.digest((output/'source.tar.gz').read_bytes()),
        launcher_sha256=gate.digest((source/gate.SELF).read_bytes()),
        source_members=len(manifest['sources']), unchanged_ancestor_sources=len(old['sources']))
    (output/'preparation.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    print(json.dumps(prepare(parser.parse_args().output), indent=2))
