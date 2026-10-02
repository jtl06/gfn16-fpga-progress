"""Two exact single-expression negatives matched to native P8-b control940aabd6."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/stream27-p8b-aw5-native-inputs-v1'
PARENT_SHA='92b8a8e3dec7836db0a5ef590af410d07d31dec99fd40561d220d78e418a836b'
ROLES={
 'stale':dict(source='rtl/genefer_stream27_p8b_physical_aw5_p8_f0_v1.sv',
   old='assign out_eligible=out_slot_valid && context_enabled && inv_generation==live_generation && inv_generation==active_generation;',
   new='assign out_eligible=out_slot_valid && context_enabled && inv_generation==active_generation;',
   expected='P8B_ELIGIBLE_MISMATCH tick=73 current generation/enabled\n',
   prediction='First canceled frame owner7/live8 still has first physical row73; eligibility must be false.'),
 'zero-square':dict(source='rtl/genefer_stream27_square_p8_f0_v1.sv',
   old=".rhs({5'b0,data_in[lane*27+:27]}),",new=".rhs(32'd0),",
   expected='P8B_DATA_MISMATCH tick=75 lane=7\n',
   prediction='Zeroimage passes. Image1 x31=1 gives only coefficient30=-1; bit-reversedlane7,row2 is firstnonzero at75.')}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination,role):
    destination=Path(destination).resolve()
    assert role in ROLES and not destination.exists() and not (ROOT/'docs/briefs/PAUSE').exists()
    assert sha(PARENT/'manifest.json')==PARENT_SHA
    original=json.loads((PARENT/'manifest.json').read_text());spec=ROLES[role];source=destination/'inputs/fpga'
    for name,pin in original['sources'].items():
        incoming=PARENT/'inputs/fpga'/name;assert sha(incoming)==pin
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(incoming,target)
    text=(source/spec['source']).read_text();assert text.count(spec['old'])==1 and spec['new'] not in text
    (source/spec['source']).write_text(text.replace(spec['old'],spec['new'],1))
    assert (source/spec['source']).read_text().replace(spec['new'],spec['old'],1)==text
    lineage=dict(role=role,parent_manifest_sha256=PARENT_SHA,
        matched_control_report_sha256='940aabd6db016ee0a9768414ef1c137c22b45218a1db3e9d0bd77a67e3cae9be',**spec)
    (source/'lineage'/('negative-'+role+'-v1.json')).write_text(json.dumps(lineage,indent=2)+'\n')
    manifest=dict(original);manifest.update(source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),
        sources={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()},
        steps=[dict(name=role+'-negative',argv=['{exe}'],expected_returncode=1,expected_stdout='',expected_stderr=spec['expected'])])
    assert [n for n,h in original['sources'].items() if manifest['sources'][n]!=h]==[spec['source']]
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    receipt=dict(status='prepared_not_executed',preserved_parent_files=13,manifest_sha256=sha(destination/'manifest.json'),**lineage)
    (destination/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt


if __name__=='__main__':
    import sys
    assert len(sys.argv)==3
    print(json.dumps(prepare(sys.argv[1],sys.argv[2]),indent=2))
