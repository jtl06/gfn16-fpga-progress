"""Bounded aethia full-size arithmetic check, NOT a spatial/RTL simulation."""
import hashlib
import json
import os
from pathlib import Path
import resource
import socket
import time

MODEL_SHA='b8526b6174491c35b537c0287a33c7467c07fa049c7a397c1f491e56c6121b23'
VECTOR_SHA='3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    root=Path(__file__).resolve().parent
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    if sorted(os.sched_getaffinity(0))!=[4]:raise RuntimeError('reserved physical core4 required')
    group=next(line.split('::',1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    cg=Path('/sys/fs/cgroup')/group.lstrip('/')
    if (cg/'memory.max').read_text().strip()!=str(2<<30):raise RuntimeError('2GiB cgroup required')
    if (cg/'cpu.max').read_text().split()!=['100000','100000']:raise RuntimeError('one-core quota required')
    model=root/'stream_ntt_model.py';vectors=root/'vectors-aw16.txt'
    if sha(model)!=MODEL_SHA or sha(vectors)!=VECTOR_SHA:raise RuntimeError('source/vector identity')
    out=root/'result';out.mkdir()
    report=dict(status='running_arithmetic_only',host=socket.gethostname(),model_sha256=MODEL_SHA,
                vector_sha256=VECTOR_SHA,runner_sha256=sha(Path(__file__)),affinity=[4],cgroup=group,
                memory_limit_bytes=2<<30,variant='exact',aw=16,
                scope='Full archived normal vectors; no spatial schedule, RTL, reset/error, resource or clock qualification')
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    save();started=time.monotonic();resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    try:
        import stream_ntt_model as model_module
        result=model_module.verify_normal_vectors(vectors,'exact')
        if result['cases']!=12:raise RuntimeError('expected all12 full-size normal transactions')
        if sha(model)!=MODEL_SHA or sha(vectors)!=VECTOR_SHA:raise RuntimeError('post-run source drift')
        report.update(status='passed_arithmetic_only',result=result)
    except BaseException as error:
        report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:
        report.update(seconds=time.monotonic()-started,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        save();print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
