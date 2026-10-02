"""Exact slot-B-only derivative of frozen, qualified collector1bf16ac0.

No audit/helper/adapter/compiled-input semantics change. Five unique literals
change the C affinity/lock/context admission and its error label to B.
"""
import hashlib
from pathlib import Path

BASE_SHA='1bf16ac0fdace73bf43ccf6f61db5c78bf4def154c729b545db947d0d1c3ba48'
CHANGES=[
 ("request['slot']=='c','delegated F16C audit collection only'","request['slot']=='b','delegated F16B audit collection only'"),
 ("ad.topology(ad.FIT,'c')","ad.topology(ad.FIT,'b')"),
 ("ad.lock_names(ad.FIT,'c',physical)","ad.lock_names(ad.FIT,'b',physical)"),
 ("context['slot']=='c'","context['slot']=='b'")]


def derive(text):
    for old,new in CHANGES:
        if text.count(old)!=1: raise ValueError('exact unique slot-B collector anchor')
        text=text.replace(old,new,1)
    return text


def main():
    base=Path('/home/azureuser/gfn16-worker/tools-collect-plain-audit-v2.py')
    if base.resolve()!=base or not base.is_file() or base.stat().st_nlink!=1: raise ValueError('canonical frozen collector')
    raw=base.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASE_SHA: raise ValueError('frozen qualified collector SHA')
    namespace={'__file__':str(Path(__file__).resolve()),'__name__':'__main__'}
    exec(compile(derive(raw.decode()),str(base)+'[slot-B-only]','exec'),namespace)


if __name__=='__main__': main()
