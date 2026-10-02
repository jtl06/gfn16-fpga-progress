"""Oracle-dependency-only successor of the frozen canonical-image packeter."""
import argparse
import json
from pathlib import Path
import types

from fpga.reference import stream27_canonical_image_native_v2 as native

PARENT='reference/stream27_canonical_image_prepare_v1.py'
PARENT_SHA='439158701196ecda3447c96f8bd6faf57769f9f7cb02ce56ec8dec7186bb1c3f'


def worker():
    path=native.ROOT/PARENT;raw=path.read_bytes()
    native.model.need(native.sha(raw)==PARENT_SHA,'CANON_PREP_V1_FROZEN')
    text=raw.decode()
    changes=(
        ('stream27_canonical_image_native_v1 as native','stream27_canonical_image_native_v2 as native'),
        ("SELF='reference/stream27_canonical_image_prepare_v1.py'","SELF='reference/stream27_canonical_image_prepare_v2.py'"),
        ("NATIVE='reference/stream27_canonical_image_native_v1.py'","NATIVE='reference/stream27_canonical_image_native_v2.py'"),
        ('tests/test_stream27_canonical_image_prepare_v1.py','tests/test_stream27_canonical_image_prepare_v2.py'),
        ('s4-canonical-image-dual-v1','s4-canonical-image-dual-v2'),
        ('s4-canonical-aw{aw}-p{p}-{pair}-v1','s4-canonical-aw{aw}-p{p}-{pair}-v2'),
        ('s4-canonical-aw{aw}-p{p}-q1-v1','s4-canonical-aw{aw}-p{p}-q1-v2'),
        ('s4-canonical-aw5-p{p}-q1-v1','s4-canonical-aw5-p{p}-q1-v2'))
    for old,new in changes:
        native.model.need(text.count(old)==1,'CANON_PREP_EXACT_DELTA '+old);text=text.replace(old,new)
    module=types.ModuleType('_canonical_image_prepare_v2');module.__file__=__file__
    exec(compile(text,str(path)+'[oracle-source-v2]','exec'),module.__dict__)
    original=module.role
    def role(aw,p):
        m,files=original(aw,p)
        m['build']['cflags'].append(f'-DCANON_ORACLE_CHECKSUM={native.corpus.checksum(aw,p)}')
        m['canonical_image'].update(oracle='native independent self-contained uint32-limb whole-X modulo b^N+1',
            oracle_checksum=native.corpus.checksum(aw,p),oracle_checksum_scope='Supplemental32bit checksum of independentPython42-vectorwholeintegeroracle, not cryptographic equivalence.',
            predecessor='Frozenv1 missingBoost buildfailures preserved; no numericresults; RTL/model/vector/protocol/expectedcontracts unchanged.')
        return m,files
    module.role=role
    return module


def role(aw,p):return worker().role(aw,p)


def prepare(output,aw,p,budget):return worker().prepare(output,aw,p,budget)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw',type=int,choices=(5,8),required=True);parser.add_argument('--p',type=int,choices=(8,16),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.p,args.budget),indent=2))
