"""Pinned aethia-only S1 blockcarry arithmetic matrix; no RTL/timing claim."""
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import socket
import time

PINS={
 'stream_ntt_model.py':'b8526b6174491c35b537c0287a33c7467c07fa049c7a397c1f491e56c6121b23',
 'stream_ntt_blockwrap2_proposal.py':'b6f94debf66b07aa118ab7e82be6802fd5a81cbc8c41a99cb79f65f91726e255',
 'stream_ntt_blockcarry_model.py':'f7bf911826136494d990e6a878d7e9900e53101714bcde93838dda410d2c16e3',
 'vectors-aw5.txt':'a5b46cb2f52ce817bed3de90a91dfc6fb038b30215edc7d861514d1106919edd',
}
REMOTE=Path('/home/jtl/gfn-fpga-lab/agent-work')
VECTORS={
 8:(REMOTE/'stream-ntt-wrap2-v1/vectors-aw8.txt','0c9047f7e9e3259683d8aebd88c137a788368078bb53c06a879728fcbe3c386e'),
 12:(REMOTE/'stream-ntt-wrap2-v1/vectors-aw12.txt','5e9f3f01e6acda97e2d770012163c1b2e000a648ae10f7c541efe831807b36d3'),
 16:(REMOTE/'stream-ntt-model-v1/vectors-aw16.txt','3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d'),
}
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
        for path,digest in VECTORS.values():
            if sha(path)!=digest:raise RuntimeError('shared vector drift')
    check();out=root/'result';out.mkdir();resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    report=dict(status='running_arithmetic_matrix',profile='stream27-blockcarry',sources=PINS,
        shared_vectors={str(a):dict(path=str(p),sha256=h) for a,(p,h) in VECTORS.items()},
        runner_sha256=sha(Path(__file__)),host=socket.gethostname(),affinity=[4],cgroup=group,runs=[],
        scope='Arithmetic evaluation only. AW5 archived matrix uses P1 to retain its old minimum base; dedicated P8/P16 small cases use the new explicit minimum. No spatial/RTL/resource/timing qualification.')
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        import stream_ntt_blockcarry_model as m
        rng=random.Random(20260930);small_count=0
        for lanes in (8,16):
            for base in (m.minimum_base(32,lanes),m.minimum_base(32,lanes)+1,604832956,10**9):
                modulus=base**32+1
                patterns=([base-1]*32,[-1]+[0]*31,[(base-1)*(i%2) for i in range(32)],[rng.randrange(base) for _ in range(32)])
                for digits in patterns:
                    state=m.load(digits,base,lanes);value=sum(d*base**i for i,d in enumerate(digits))%modulus
                    for bit in (1,0,1):
                        coefficients=m.square_coefficients(state,bit)
                        serial,ends=m.proposal.carry_serial(coefficients,base,lanes)
                        state,stats=m.proposal.carry_split(coefficients,base,lanes)
                        if state!=serial or ends!=stats['block_carries']:raise RuntimeError('small split/serial mismatch')
                        value=value*value*(1<<bit)%modulus
                        if sum(d*base**i for i,d in enumerate(state.canonical()))%modulus!=value:raise RuntimeError('small independent integer mismatch')
                        small_count+=1
        if small_count!=96:raise RuntimeError('small gate coverage')
        report['dedicated_aw5_p8_p16_cases']=small_count;save()
        for aw,lanes in [(5,1),(8,8),(8,16),(12,8),(12,16),(16,8),(16,16)]:
            check();started=time.monotonic();path=root/'vectors-aw5.txt' if aw==5 else VECTORS[aw][0]
            result=m.verify_vectors(path,lanes)
            if result['cases']!=(568 if aw==5 else 12):raise RuntimeError('full normal coverage')
            row=dict(aw=aw,lanes=lanes,seconds=time.monotonic()-started,result=m.exact_json(result))
            report['runs'].append(row);check();save();print(json.dumps(row),flush=True)
        report['status']='passed_blockcarry_arithmetic_matrix_only'
    except BaseException as error:
        report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:
        report['max_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;save()

if __name__=='__main__':main()
