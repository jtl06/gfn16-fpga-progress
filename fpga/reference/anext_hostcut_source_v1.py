"""Only the qualified host payload/cancel shell is rebound on frozen upper."""
import json,shutil
from pathlib import Path
from fpga.reference import anext_upper_source_v1 as upper
from fpga.reference import anext_cancel_distribution_v1 as component
ROOT=upper.ROOT
GEN='reference/anext_cancel_distribution_v1.py';GEN_SHA='77537400a19764fdecb6fec4b7fe04e6c02e247d35cb8c4449b1830399fa51e7'
CHILDREN={component.TARGETS['word']:'6f2e705eb8e039e6a7b1b614223d58bc836d9ccd5ca9221cd4e3628d30202cb6',component.TARGETS['image']:'ab3c84b08d522ebcd8e1b882f20c51f35e3ae817918f70299b4a0f1bc66ada09',component.TARGETS['shell']:'1f5d878f6ffbdb9d745b36ed5926a7ee1a4d417ea8b9dee418b8991c70e220c7'}
ROLES={5:('anext-upper-whole-aw5-role-v1','74cc883d85fef7d696a8ae62e26378b7719e5079b28d0b791cda605435b14351'),8:('anext-upper-whole-aw8-role-v1','66996fbc7c4f9d712e66b5c8119a1373df637a1f5d199d907465837bc049b9bb'),16:('anext-upper-representative-aw16-role-v1','734b33e574f38d227bfbadff0c0beaeecc9891c078672ff69024ba76d32aeae4')}
NAMES={'genefer_anext_upper_core_v1':'genefer_anext_hostcut_core_v1','genefer_track_a4_host_shell_v2':'genefer_anext_cancel_host_shell_v1','genefer_track_a4_host_word_v1':'genefer_anext_cancel_host_word_v1','genefer_track_a4_digit_image_v1':'genefer_anext_cancel_digit_image_v1','track_anext_upper_core_v1':'track_anext_hostcut_core_v1','track_anext_upper_representative_v1':'track_anext_hostcut_representative_v1','anext_upper_output_v1':'anext_hostcut_output_v1','anext_upper_representative_output_v1':'anext_hostcut_representative_output_v1'}
def need(ok,why):
    if not ok:raise ValueError(why)
def rename(t):
    for a,b in NAMES.items():t=t.replace(a,b)
    return t.replace("candidate='A-next-upper-v1'","candidate='A-next-hostcut-v1'")
def expected():
    upper.verify();need(upper.point.sha(ROOT/GEN)==GEN_SHA,'frozen qualified component generator');component.guard()
    for kind,n in component.TARGETS.items():need(upper.point.sha(ROOT/n)==CHILDREN[n] and (ROOT/n).read_text()==component.source(kind),'exact qualified host child')
    names=['rtl/kernel/genefer_anext_upper_core_v1.sv','rtl/tb/track_anext_upper_core_v1.cpp','reference/anext_upper_output_v1.py','rtl/tb/track_anext_upper_representative_v1.cpp','reference/anext_upper_representative_output_v1.py']
    result={rename(n):rename((ROOT/n).read_text()) for n in names}
    old=(ROOT/names[0]).read_text();new=result[rename(names[0])]
    need(new.replace('genefer_anext_hostcut_core_v1','genefer_anext_upper_core_v1').replace('genefer_anext_cancel_host_shell_v1','genefer_track_a4_host_shell_v2')==old,'only top and host binding delta')
    return result
def verify():
    out=expected()
    for n,t in out.items():need((ROOT/n).read_text()==t,'exact hostcut whole source '+n)
    return {n:upper.point.sha(ROOT/n) for n in out}
def prepare(aw,output):
    output=Path(output).resolve();need(aw in ROLES and not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'finite fresh hostcut role')
    generated=verify();role,pin=ROLES[aw];base=ROOT/'artifacts'/role;need(upper.point.sha(base/'manifest.json')==pin,'upper role pin');m=json.loads((base/'manifest.json').read_text())
    for n,h in m['sources'].items():need(upper.point.sha(base/'source/fpga'/n)==h,'frozen source closure')
    shutil.copytree(base/'source',output/'source')
    extras=[*generated,*CHILDREN,GEN,'reference/anext_hostcut_source_v1.py','tests/test_anext_hostcut_v1.py','rtl/tb/track_anext_upper_representative_v1.cpp','reference/anext_upper_representative_output_v1.py',component.MEASURED+'/receipt.json',component.MEASURED+'/evidence/project/output_files/probe.sta.rpt']
    for n in extras:
        d=output/'source/fpga'/n;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,d);m['sources'][n]=upper.point.sha(d)
    m['build'].update(top='genefer_anext_hostcut_core_v1',cpp_source=rename(m['build']['cpp_source']),sv_sources=[rename(n) for n in m['build']['sv_sources']])
    for s in m['steps']:s['name']=f'anext-hostcut-aw{aw}';s['validator']['source']=rename(s['validator']['source'])
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(manifest_sha256=upper.point.sha(output/'manifest.json'),sources=len(m['sources']),compiled_sv=30,expected_cycle_delta=0,recovery_remedy=False,native_executed=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--aw',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.aw,a.output),indent=2))
