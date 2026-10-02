"""Close both source-only harness test branches in each role snapshot.

The v1 snapshots remain intact. No RTL, compile list or native steps change.
"""
import json,shutil
from pathlib import Path
from fpga.reference import track_a_trunk_command_prepare_v1 as parent

def prepare(output,mode):
    output=Path(output).resolve();parent.prepare(output,mode)
    path=output/'manifest.json';manifest=json.loads(path.read_text())
    names=['reference/track_a_trunk_command_prepare_v2.py']
    for branch in parent.PARENTS:names.extend((parent.cpp(branch),parent.PARENTS[branch][0]))
    for name in names:
        src=parent.ROOT/name;dest=output/'source/fpga'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dest);manifest['sources'][name]=parent.sha(src)
        if parent.sha(dest)!=manifest['sources'][name]:raise ValueError('closure copy drift')
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    return dict(status='prepared_not_executed',mode=mode,manifest_sha256=parent.sha(path),sources=len(manifest['sources']),native_contract_unchanged=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=parent.PARENTS,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.mode),indent=2))
