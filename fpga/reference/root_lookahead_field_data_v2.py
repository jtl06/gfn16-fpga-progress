"""Fresh paired vector/receipt generator for the F2 field role; never native RTL.

Use the shared host workflow to invoke this data-preparation CLI on aethia for
AW16. It inherits the strict full-numeric host guard and creates no runner,
compile policy, unbounded job or source mutation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
from fpga.reference import root_lookahead_field_v2 as field

FIELD_SHA='8104fa1e6eeeee0114937e1ce988078e4a2ad8bbe2b59fef9913acb3bbd34904'


def generate(aw,index,output,receipt):
    field.need(not output.exists() and not receipt.exists(),'fresh field vector and receipt')
    source=Path(field.__file__)
    field.need(hashlib.sha256(source.read_bytes()).hexdigest()==FIELD_SHA,'frozen field oracle source')
    vectors,meta=field.corpus(aw,index)
    digest=hashlib.sha256(vectors.encode()).hexdigest()
    meta.update(schema='F2-field-vector-receipt-v2',vector_sha256=digest,vector_bytes=len(vectors.encode()),
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                hostname=platform.node(),platform=platform.system(),
                numeric_full_N=aw==16,native_RTL_executed=False)
    with output.open('x') as stream:stream.write(vectors)
    with receipt.open('x') as stream:stream.write(json.dumps(meta,indent=2)+'\n')
    return meta


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--aw',type=int,required=True)
    parser.add_argument('--field',type=int,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(generate(args.aw,args.field,args.output,args.receipt),indent=2))
