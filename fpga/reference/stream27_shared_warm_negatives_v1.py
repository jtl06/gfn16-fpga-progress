"""Matched S4 negatives with precomputed typed nonzero contracts."""
import json
from pathlib import Path
import shutil
from .stream27_shared_warm_native_v1 import ROOT,sha

PARENT=ROOT/'artifacts/stream27-s4-aw8-shared-warm-inputs-v3'
PIN='906452b0421b8c73ff4babb0616584cfebf1c52d91b8737d584f7d32dfa8500e'
TOP='rtl/genefer_stream27_shared_warm_aw8_p16_f0_v1.sv'
MUTANTS={
    'missing-c0':('.generation_in(fwd_generation),.lhs(canonical_spectrum),.rhs(addA_rhs),',
        ".generation_in(fwd_generation),.lhs(canonical_spectrum),.rhs(432'd0),",
        'S4_DATA case=2 tick=143 lane=0 expected=19887389 actual=4356194\n'),
    'stale-eligibility':('assign out_eligible=protocol_commit;',
        'assign out_eligible=out_slot_valid && context_enabled;',
        'S4_ELIGIBLE tick=143\n'),
}


def prepare(destination,kind):
    destination=Path(destination).resolve()
    if kind not in MUTANTS or destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_MUTANT_KIND_FRESH_PAUSE')
    if sha(PARENT/'manifest.json')!=PIN:raise ValueError('S4_MUTANT_PARENT')
    original=json.loads((PARENT/'manifest.json').read_text());source=destination/'inputs/fpga'
    for name,pin in original['sources'].items():
        incoming=PARENT/'inputs/fpga'/name
        if sha(incoming)!=pin:raise ValueError('S4_MUTANT_SOURCE')
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(incoming,target)
    old,new,failure=MUTANTS[kind];path=source/TOP;s=path.read_text()
    if s.count(old)!=1 or new in s:raise ValueError('S4_MUTANT_SINGLE_ANCHOR')
    path.write_text(s.replace(old,new))
    m=dict(original);m.update(source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),
        sources={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()},
        steps=[dict(name='s4-aw8-'+kind+'-negative',argv=['{exe}'],expected_returncode=1,expected_stdout='',expected_stderr=failure)])
    changed=[name for name,pin in original['sources'].items() if m['sources'][name]!=pin]
    if changed!=[TOP]:raise ValueError('S4_MUTANT_RTL_ONLY_DELTA')
    (destination/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    r=dict(status='prepared_not_executed',kind=kind,parent_manifest_sha256=PIN,manifest_sha256=sha(destination/'manifest.json'),
        changed_sources=changed,preserved_sources=len(original['sources'])-1,old=old,new=new,expected_stderr=failure,
        expected_returncode=1,typed_negative=True,promotion_allowed=False,
        prediction='missing-c0 coefficient0 independently calculated as x0^2-sum(xi*x256-i), no NTT; stale outputeligible must fail last stale-live control before any stale commit.')
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_MUTANT_USAGE')
    print(json.dumps(prepare(sys.argv[1],sys.argv[2]),indent=2))
