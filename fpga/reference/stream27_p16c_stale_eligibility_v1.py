"""Single-delta AW6 P16-c negative: remove current-live-generation eligibility.

The native-admitted control and its schoolbook/cycle harness stay frozen. This
source-only preparer predicts a typed failure at the first canceled output.
"""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'artifacts/stream27-p16c-aw6-portable-inputs-v2'
PARENT_SHA = '31d74c57fc5d1b635bc930ab43fbeec7b6f555c347e3a220fadae394f8a7d1fa'
TOP = 'rtl/genefer_stream27_p16c_physical_aw6_p16_f0_v1.sv'
OLD = 'assign out_eligible=out_slot_valid && context_enabled && inv_generation==live_generation && inv_generation==active_generation;'
NEW = 'assign out_eligible=out_slot_valid && context_enabled && inv_generation==active_generation;'
FAILURE = 'P16C_ELIGIBLE_MISMATCH tick=85 current generation/enabled\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination):
    destination = Path(destination).resolve()
    assert not destination.exists() and not (ROOT / 'docs/briefs/PAUSE').exists()
    assert sha(PARENT / 'manifest.json') == PARENT_SHA
    original = json.loads((PARENT / 'manifest.json').read_text())
    source = destination / 'inputs/fpga'
    for name, pin in original['sources'].items():
        incoming = PARENT / 'inputs/fpga' / name
        assert sha(incoming) == pin
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(incoming, target)
    text = (source / TOP).read_text()
    assert text.count(OLD) == 1 and NEW not in text
    (source / TOP).write_text(text.replace(OLD, NEW, 1))
    assert (source / TOP).read_text().replace(NEW, OLD, 1) == text
    lineage = dict(schema='p16c-stale-eligibility-negative-v1', parent_manifest_sha256=PARENT_SHA,
        matched_native_control_report_sha256='9821d28d1615e88b3bf41eebed3fef2165dfdc0c84266baaf855048bf29fdf66',
        changed_source=TOP, old=OLD, new=NEW,
        expected_stderr=FAILURE, expected_returncode=1,
        prediction='Six legal images and reset-at-zero case pass first. Cancel-at-zero image4 retains physical output at85, but live8 must reject owner7 eligibility. Mutant asserts eligibility and fails before data comparison.')
    (source / 'lineage/stale-eligibility-negative-v1.json').write_text(json.dumps(lineage, indent=2)+'\n')
    manifest = dict(original)
    manifest.update(source_root=str(source), output_parent=str(destination/'UNBOUND_OUTPUT'),
        sources={str(p.relative_to(source)): sha(p) for p in sorted(source.rglob('*')) if p.is_file()},
        steps=[dict(name='stale-eligibility-negative', argv=['{exe}'], expected_returncode=1,
                    expected_stdout='', expected_stderr=FAILURE)],
        lint_baseline_policy='Fresh r38 class-gated lint/build; no per-line baseline or functional warning waiver.')
    changed = [n for n,h in original['sources'].items() if manifest['sources'][n] != h]
    assert changed == [TOP]
    (destination/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    result = dict(status='prepared_typed_negative_not_executed', changed_sources=changed,
                  preserved_sources=len(original['sources'])-1, manifest_sha256=sha(destination/'manifest.json'), **lineage)
    (destination/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    import sys
    assert len(sys.argv) == 2
    print(json.dumps(prepare(sys.argv[1]), indent=2))
