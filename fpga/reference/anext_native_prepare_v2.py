"""Add missing pure block-route model to v1's isolated test import closure.

The v1 role snapshots are preserved. No RTL, bench, vectors or phase contract
changes; the first isolated replay found ImportError in the adapter test only.
"""
import hashlib
from pathlib import Path
from fpga.reference import anext_native_prepare_v1 as parent

EXTRA=('reference/track_a4_blockroute_model_v1.py','reference/anext_native_prepare_v2.py')


def prepare(output,aw):
    original=list(parent.EXTRA)
    try:
        parent.EXTRA=[*original,*EXTRA]
        return parent.prepare(output,aw)
    finally:
        parent.EXTRA=original


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--aw',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.aw),indent=2))
