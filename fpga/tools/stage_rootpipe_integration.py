"""Generate a source-only archive for the isolated aethia integration directory."""
import argparse
import json
from pathlib import Path
import tarfile
from reference.square_core27_rootpipe_regression import check_sources, source_inputs, sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    pins=source_inputs(root,check_sources(root))
    for name in ('tests/test_square_core27_rootpipe_structure.py',
                 'tests/test_square_core27_rootpipe_regression.py','tools/stage_rootpipe_integration.py'):
        pins[name]=sha(root/name)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    archive=out/'source.tar.gz'
    with tarfile.open(archive,'x:gz') as tar:
        for name,value in sorted(pins.items()):
            path=root/name
            if path.is_symlink() or sha(path)!=value:raise RuntimeError('source drift/link '+name)
            tar.add(path,arcname='fpga/'+name,recursive=False)
    manifest=dict(status='prepared_not_executed',sources=pins,archive_sha256=sha(archive),
        target='/home/jtl/gfn-fpga-lab/agent-work/square-core27-rootpipe/profiles/small-v1',
        note='Source only; do not overwrite existing directory. Launch requires parent-reviewed disk/resource reservation.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(files=len(pins),archive_bytes=archive.stat().st_size,sha256=sha(archive))))


if __name__=='__main__':main()
