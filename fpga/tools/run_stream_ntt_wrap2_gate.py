"""Aethia-only pinned arithmetic matrix; no streaming schedule or RTL claim."""
import hashlib
import json
import os
from pathlib import Path
import resource
import socket
import time

PINS={
    'stream_ntt_model.py':'b8526b6174491c35b537c0287a33c7467c07fa049c7a397c1f491e56c6121b23',
    'stream_ntt_wrap2_model.py':'d737aa80348b43f6a2d266ff81f832fb759ca732d6c189f386ee4fd12b2b2056',
    'vectors-aw8.txt':'0c9047f7e9e3259683d8aebd88c137a788368078bb53c06a879728fcbe3c386e',
    'vectors-aw12.txt':'5e9f3f01e6acda97e2d770012163c1b2e000a648ae10f7c541efe831807b36d3',
}
FULL=Path('/home/jtl/gfn-fpga-lab/agent-work/stream-ntt-model-v1/vectors-aw16.txt')
FULL_SHA='3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    root=Path(__file__).resolve().parent
    if socket.gethostname()!='aethia' or sorted(os.sched_getaffinity(0))!=[4]:raise RuntimeError('aethia physical core4')
    group=next(x.split('::',1)[1] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    cg=Path('/sys/fs/cgroup')/group.lstrip('/')
    if (cg/'memory.max').read_text().strip()!=str(2<<30) or (cg/'cpu.max').read_text().split()!=['100000','100000']:raise RuntimeError('2GiB/one-core cgroup')
    def check():
        for name,digest in PINS.items():
            if sha(root/name)!=digest:raise RuntimeError('input drift '+name)
        if sha(FULL)!=FULL_SHA:raise RuntimeError('full-N archived input drift')
    check();out=root/'result';out.mkdir();resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    report=dict(status='running_arithmetic_matrix',sources=PINS,full_vector_sha256=FULL_SHA,
        runner_sha256=sha(Path(__file__)),host=socket.gethostname(),affinity=[4],cgroup=group,runs=[],
        scope='New AW8/AW12 normal vectors, archived AW16 normal vectors. Not spatial, RTL, cycle, reset/error, area or timing qualification.')
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        import stream_ntt_model as exact
        import stream_ntt_wrap2_model as wrap2
        for profile,aw in [('exact',8),('exact',12),('wrap2',12),('wrap2',16)]:
            check();start=time.monotonic();path=FULL if aw==16 else root/f'vectors-aw{aw}.txt'
            result=exact.verify_normal_vectors(path,'exact') if profile=='exact' else wrap2.verify_vectors(path)
            if result['cases']!=12:raise RuntimeError('all twelve cases required')
            report['runs'].append(dict(profile=profile,aw=aw,seconds=time.monotonic()-start,result=wrap2.exact_json(result)))
            check();save();print(json.dumps(report['runs'][-1]),flush=True)
        report['status']='passed_arithmetic_matrix_only'
    except BaseException as error:
        report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:
        report['max_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;save()

if __name__=='__main__':main()
