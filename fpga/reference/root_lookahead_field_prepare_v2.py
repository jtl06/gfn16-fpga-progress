"""Prepare F2 integration role data for the shared packager; no runner/dispatch."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from fpga.reference import root_lookahead_field_v2 as field

ROOT=field.ROOT
PARENT=ROOT/'artifacts/root-lookahead-v1-prepared'
MANIFEST='aethia-aw5-one-field.json'
MANIFEST_SHA='79f75584fda3e95730238f18e372496d749c9284a4b1429ecaae8a84630ffc06'
SELF='reference/root_lookahead_field_prepare_v2.py'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(output,aw=5,field_index=0):
    field.need(not(ROOT/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    field.need(aw in (5,8),'local preparation only AW5/AW8; AW16 assets come from admitted worker')
    parent=PARENT/MANIFEST;field.need(sha(parent)==MANIFEST_SHA,'parent role manifest')
    old=json.loads(parent.read_text());source=PARENT/'source/fpga'
    field.need({p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}==old['sources'],
               'frozen F2 source closure')
    output=Path(output).resolve();field.need(not output.exists(),'fresh F2 role data packet')
    target=output/'source/fpga';shutil.copytree(source,target)
    extra=[field.SELF,field.BENCH,field.THREAD_HEADER,SELF,'tests/test_root_lookahead_field_v2.py',
           'reference/merged_negacyclic27_model.py']
    for name in extra:
        destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,destination)
    vectors,oracle=field.corpus(aw,field_index)
    asset=f'field-aw{aw}-f{field_index}-vectors.txt';(target/asset).write_text(vectors)
    spec=field.integration_build(aw,field_index,1)
    manifest=dict(old)
    manifest['build']={k:spec[k] for k in ('top','sv_sources','cpp_source','parameters','cflags')}
    manifest['steps']=[dict(name='field-control',argv=['{exe}','{root}/'+asset],expected_returncode=0,
                            validator=spec['validator']),
                       dict(name='field-negative-oracle',**spec['negative_step'])]
    manifest['sources']={p.relative_to(target).as_posix():sha(p) for p in target.rglob('*') if p.is_file()}
    manifest['scope']='F2 one-field paired integration, source-only role data. Shared lint baseline and host guard required.'
    manifest['admission']=dict(old['admission'],prepared_by=SELF,promotion_allowed=False,
        limitation='Existing L16/F0 component lint debt does not admit this engine build. Use shared mandatory-Wall observation and exact reviewed role baseline.')
    path=output/'role-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    receipt=dict(status='prepared_source_only_shared_packager_role_data',aw=aw,field=field_index,
                 role_manifest_sha256=sha(path),source_root=str(target),source_files=len(manifest['sources']),
                 sources=manifest['sources'],oracle=oracle,source_only=True,
                 launcher_clones_created=0,command='shared prepare --manifest role-manifest.json --source-root source/fpga --profile <admitted> --id <fresh> --phase lint --output <fresh>')
    (output/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--aw',type=int,default=5);parser.add_argument('--field',type=int,default=0)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.field),indent=2))
