"""A4b role data/snapshot builder for the shared native_package_v1 interface.

No launcher, cloud, shell command, tool-policy change or execution is defined.
The shared packager owns lint/run phase, host profile, budgets and native paths.
"""
import json
from pathlib import Path
import shutil
from fpga.reference.track_a4_core_source_v4 import verify
from fpga.reference.track_a4_admission_boundary_v1 import verify as boundary_verify,MUTATIONS,MUTANT_CASES
from fpga.reference.track_a4_representative_source_v2 import verify as representative_verify
from fpga.reference.track_a4_core_vectors_v1 import corpus
from fpga.tools.prefit_structural_guard_v1 import file_digest

ROOT=Path(__file__).resolve().parents[1]
TICKET='docs/briefs/replies/2026-10-01-B20260930A-A4-core-registered-admission-ticket-v4.json'
TICKET_PIN='e3ca5d1132ae238e4ec23a0404ecc4e0ec5c1901d6bfc2a01a3a8458f86cc7b5'
EXTRA=('reference/track_a4b_native_output_v1.py','tests/test_track_a4b_native_output_v1.py',
 'reference/track_a4_representative_source_v2.py','reference/track_a4_representative_output_v2.py',
 'reference/track_a4_representative_output_v1.py','reference/track_a4_representative_recipe_v1.py',
 'rtl/tb/track_a4_core_representative_v1.cpp','rtl/tb/track_a4_core_representative_v2.cpp',
 'rtl/tb/track_a4_representative_recipe_v1.hpp','tests/test_track_a4_representative_source_v2.py',
 'reference/track_a4b_native_spec_v1.py')

def prepare(output,role='normal-aw5'):
    output=Path(output).resolve();assert not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists()
    assert file_digest(ROOT/TICKET)==TICKET_PIN
    ticket=json.loads((ROOT/TICKET).read_text());pins=ticket['source_sha256'].copy();pins[TICKET]=TICKET_PIN
    verify();boundary_verify();representative_verify()
    for p in EXTRA:pins[p]=file_digest(ROOT/p)
    for p,h in pins.items():assert file_digest(ROOT/p)==h,p
    source=output/'source/fpga';source.mkdir(parents=True)
    for p,h in pins.items():
        target=source/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,target)
        assert file_digest(target)==h
    def validator(config,assets=None):
        return dict(source='reference/track_a4b_native_output_v1.py',function='validate',config=config,assets=assets or {})
    if role in ('normal-aw5','normal-aw8'):
        aw=int(role[-1]);text,metadata=corpus(aw);vector=f'vectors/aw{aw}.txt'
        (source/'vectors').mkdir();(source/vector).write_text(text);pins[vector]=metadata['sha256']
        top=ticket['native_top'];compiled=ticket['native_sources'];cpp='rtl/tb/track_a4_core_v4.cpp'
        cflags=['-std=c++17','-Werror=return-type',f'-DA4_CORE_AW={aw}']
        steps=[dict(name=role,argv=['{exe}','{root}/'+vector],expected_returncode=0,expected_stderr='',
            validator=validator(dict(mode='normal',aw=aw),dict(vectors=vector)))]
    elif role=='representative-aw16':
        aw=16;top=ticket['native_top'];compiled=ticket['native_sources'];cpp='rtl/tb/track_a4_core_representative_v2.cpp'
        cflags=['-std=c++17','-Werror=return-type','-DA4_CORE_AW=16']
        steps=[dict(name=role,argv=['{exe}','--representative'],expected_returncode=0,expected_stderr='',
            validator=validator(dict(mode='representative',aw=aw)))]
    elif role=='boundary-control' or role in MUTATIONS:
        aw=5;top=ticket['boundary']['top'];compiled=ticket['boundary']['native_sources'];cpp=ticket['boundary']['cpp'];cflags=ticket['boundary']['cflags']
        if role=='boundary-control':
            steps=[dict(name='boundary-'+case,argv=['{exe}',case],expected_returncode=0,expected_stderr='',
                validator=validator(dict(mode='boundary',case=case))) for case in ticket['boundary']['control_cases']]
        else:
            name=ticket['boundary']['mutation_source'];before,after=MUTATIONS[role];raw=(source/name).read_text()
            assert raw.count(before)==1;(source/name).write_text(raw.replace(before,after));pins[name]=file_digest(source/name)
            case,message=MUTANT_CASES[role]
            steps=[dict(name=role.replace('_','-'),argv=['{exe}',case],expected_returncode=1,expected_stdout='',expected_stderr=message+'\n',
                validator=validator(dict(mode='boundary',case=case,mutant=role)))]
    else:raise ValueError('unknown finite A4b role')
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='aethia',
        source_root='/home/jtl/gfn-fpga-lab/agent-work/track-a4b-role-data/'+role+'/source/fpga',
        output_parent='/home/jtl/gfn-fpga-lab/agent-work/track-a4b-role-data/'+role+'/output',sources=pins,
        build=dict(top=top,sv_sources=[p for p in compiled if p.endswith('.sv')],cpp_source=cpp,parameters=dict(AW=aw),cflags=cflags),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),steps=steps)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result=dict(status='source_role_data_only_not_dispatched',role=role,author_ticket_sha256=TICKET_PIN,
        manifest_sha256=file_digest(output/'manifest.json'),source_count=len(pins),
        mutated_source=ticket['boundary']['mutation_source'] if role in MUTATIONS else None,
        shared_packager='tools/native_package_v1.py',requires_lint_observation=True,promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--role',default='normal-aw5')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.role),indent=2))
