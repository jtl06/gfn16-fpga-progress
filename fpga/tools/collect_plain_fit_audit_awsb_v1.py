"""Exact AWS-B derivative of frozen qualified collector1bf16ac0.

Only five unique host/slot admission, topology, lock and context anchors
change. Native timing/source/copy/journal/archive semantics are unchanged.
"""
import hashlib
from pathlib import Path

BASE_SHA='1bf16ac0fdace73bf43ccf6f61db5c78bf4def154c729b545db947d0d1c3ba48'
CHANGES=[
 ("root=Path(ad.HOSTS[ad.FIT]['root'])","root=Path(ad.HOSTS[ad.AWS]['root'])"),
 ("request['host']==ad.FIT and request['slot']=='c','delegated F16C audit collection only'",
  "request['host']==ad.AWS and request['slot']=='b','delegated AWSB audit collection only'"),
 ("ad.topology(ad.FIT,'c')","ad.topology(ad.AWS,'b')"),
 ("ad.lock_names(ad.FIT,'c',physical)","ad.lock_names(ad.AWS,'b',physical)"),
 ("context['slot']=='c'","context['slot']=='b'")]


def derive(text):
    for old,new in CHANGES:
        if text.count(old)!=1: raise ValueError('exact unique AWS-B collector anchor')
        text=text.replace(old,new,1)
    return text


def main():
    base=Path('/home/ubuntu/gfn16-worker/tools-collect-plain-audit-base-v1.py')
    if base.resolve()!=base or not base.is_file() or base.stat().st_nlink!=1: raise ValueError('canonical frozen collector')
    raw=base.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASE_SHA: raise ValueError('frozen qualified collector SHA')
    namespace={'__file__':str(Path(__file__).resolve()),'__name__':'__main__'}
    exec(compile(derive(raw.decode()),str(base)+'[AWS-B-only]','exec'),namespace)


if __name__=='__main__': main()
