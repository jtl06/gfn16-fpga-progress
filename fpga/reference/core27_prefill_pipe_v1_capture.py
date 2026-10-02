"""Materialize a reviewed T5b manifest's selected inputs, then immutable capture.

Data/source copying only: no HDL/compiler/cloud action and no existing output
replacement. The original source tree may contain unrelated files; the staged
tree may contain ONLY the manifest members. All pre/post hashes must agree.
"""
import hashlib
import json
from pathlib import Path,PurePosixPath
import shutil


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(manifest,root,draft,destination):
    raw=manifest.read_bytes();m=json.loads(raw);pins=m['sources']
    if m['schema']!='native-source-gate-v1' or m['status']!='prepared_not_executed':raise ValueError('schema/status')
    if draft.exists() or destination.exists():raise ValueError('fresh outputs only')
    if root.resolve()!=root or not root.is_dir():raise ValueError('canonical root')
    for name,digest in pins.items():
        p=PurePosixPath(name);path=root/name
        if p.is_absolute() or '..' in p.parts or str(p)!=name or not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file() or sha(path)!=digest:
            raise ValueError('input drift: '+name)
    draft.mkdir()
    report=dict(status='stage_started',manifest_sha256=hashlib.sha256(raw).hexdigest(),
        capture_helper_sha256=sha(Path(__file__)),files=len(pins))
    try:
        source=draft/'fpga';source.mkdir()
        for name,digest in sorted(pins.items()):
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(root/name,target)
            if sha(target)!=digest:raise ValueError('copy drift: '+name)
        if manifest.read_bytes()!=raw or any(sha(root/name)!=digest for name,digest in pins.items()):raise ValueError('mid-stage drift')
        tool=source/'tools/snapshot_native_sources_v2.py'
        # Execute the pinned stdlib-only helper without an import cache side
        # effect inside the exact source closure.
        namespace={'__file__':str(tool),'__name__':'pinned_snapshot_capture'}
        exec(compile(tool.read_bytes(),str(tool),'exec'),namespace)
        report['capture']=namespace['capture'](manifest,source,destination)
        report['status']='staged_and_captured_not_executed'
    except BaseException as error:
        report.update(status='failed_stage_preserved',error=repr(error));raise
    finally:
        with (draft/'stage.json').open('x') as output:json.dump(report,output,indent=2);output.write('\n')
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','source-root','draft','destination'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(stage(args.manifest.resolve(),args.source_root.resolve(),args.draft.resolve(),args.destination.resolve()),indent=2))
