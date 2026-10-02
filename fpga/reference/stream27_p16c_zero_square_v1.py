"""Source-only matched arithmetic negative for native-admitted P16-c AW6.

Force only the pointwise multiplier RHS to zero. The unchanged direct-schoolbook
harness must detect image1 (x63=1) at coefficient62=-1, tick87/lane15.
"""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'artifacts/stream27-p16c-aw6-portable-inputs-v2'
PARENT_SHA = '31d74c57fc5d1b635bc930ab43fbeec7b6f555c347e3a220fadae394f8a7d1fa'
SOURCE = 'rtl/genefer_stream27_square_p16_f0_v1.sv'
OLD = ".rhs({5'b0,data_in[lane*27+:27]}),"
NEW = ".rhs(32'd0),"
FAILURE = 'P16C_DATA_MISMATCH tick=87 lane=15\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination):
    destination = Path(destination).resolve()
    assert not destination.exists() and not (ROOT/'docs/briefs/PAUSE').exists()
    assert sha(PARENT/'manifest.json') == PARENT_SHA
    original = json.loads((PARENT/'manifest.json').read_text())
    source = destination/'inputs/fpga'
    for name,pin in original['sources'].items():
        incoming=PARENT/'inputs/fpga'/name
        assert sha(incoming)==pin
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(incoming,target)
    text=(source/SOURCE).read_text()
    assert text.count(OLD)==1 and NEW not in text
    (source/SOURCE).write_text(text.replace(OLD,NEW,1))
    assert (source/SOURCE).read_text().replace(NEW,OLD,1)==text
    lineage=dict(schema='p16c-zero-square-negative-v1',parent_manifest_sha256=PARENT_SHA,
        matched_native_control_report_sha256='9821d28d1615e88b3bf41eebed3fef2165dfdc0c84266baaf855048bf29fdf66',
        source=SOURCE,old=OLD,new=NEW,expected_stderr=FAILURE,
        prediction='Zero image passes; image1 has x63=1. Direct x^64=-1 schoolbook gives only coefficient62=P-1. Output coefficient index reverse4(lane)*4+row reaches62 at row2/lane15, hence first mismatch87.')
    (source/'lineage/zero-square-negative-v1.json').write_text(json.dumps(lineage,indent=2)+'\n')
    manifest=dict(original)
    manifest.update(source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),
        sources={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()},
        steps=[dict(name='zero-square-negative',argv=['{exe}'],expected_returncode=1,
                    expected_stdout='',expected_stderr=FAILURE)],
        lint_baseline_policy='Fresh r38 class-gated lint/build; no functional warning waiver.')
    changed=[n for n,h in original['sources'].items() if manifest['sources'][n]!=h]
    assert changed==[SOURCE]
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result=dict(status='prepared_not_submitted',changed_sources=changed,preserved_sources=16,
                manifest_sha256=sha(destination/'manifest.json'),**lineage)
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    import sys
    assert len(sys.argv)==2
    print(json.dumps(prepare(sys.argv[1]),indent=2))
