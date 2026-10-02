"""Bounded CPU-only S1 joined-model gate; emits JSON to stdout, no file writes.

FullN arithmetic is opt-in and intended for an independently pinned native
source bundle. This is NOT an HDL/native executable/physical timing gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from fpga.reference import stream_ntt_blockcarry_schedule as schedule
from fpga.reference import stream_ntt_blockwrap2_proposal as arithmetic


def run_gate(n,p):
    rng=random.Random(300930+p+n);cases=[]
    for base in (schedule.minimum_base(n,p),1_000_000_000):
        K=2*n+24*p
        state=arithmetic.BlockState(tuple(rng.randrange(base) for _ in range(n)),base,
            tuple(rng.randrange(1-base,base) for _ in range(p)),
            tuple(rng.randrange(-K,K+1) for _ in range(p)))
        modulus=pow(base,n)+1
        for epoch,double in enumerate((0,1)):
            # Balanced whole-integer packing and modular squaring are an
            # independent oracle, not an NTT or serial-carry comparison.
            value=arithmetic.core._pack(state.effective(),base)%modulus
            expected=value*value*(1<<double)%modulus
            started=time.monotonic()
            result=schedule.joined_square(state,double,allow_full_size=n==65536)
            state=result['state'];actual=arithmetic.core._pack(state.effective(),base)%modulus
            if actual!=expected:raise AssertionError('joined whole-integer mismatch')
            cases.append(dict(base=base,epoch=epoch,double_bit=double,status='PASS',
                elapsed_seconds=time.monotonic()-started,first_digit_edge=result['first_digit_edge'],
                digest=hashlib.sha256(actual.to_bytes((actual.bit_length()+7)//8 or 1,'big')).hexdigest()))
    events=schedule.joined_events(n,p)
    return dict(status='PASS',scope='purePython full joined arithmetic and timed token model, not RTL',
        n=n,p=p,cases=cases,queued_events=events,
        source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__),ROOT/'fpga/reference/stream_ntt_blockcarry_schedule.py',
                ROOT/'fpga/reference/stream_ntt_schedule.py',ROOT/'fpga/reference/stream_ntt_model.py',
                ROOT/'fpga/reference/stream_ntt_blockwrap2_proposal.py')})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n',type=int,default=1024,choices=(32,64,128,256,1024,65536))
    parser.add_argument('--parallel',type=int,default=8,choices=(8,16))
    parser.add_argument('--run-full-joined',action='store_true')
    parser.add_argument('--max-seconds',type=int,default=900)
    args=parser.parse_args()
    if args.n==65536 and not args.run_full_joined:parser.error('fullN requires --run-full-joined')
    if not 1<=args.max_seconds<=1800:parser.error('bounded timeout1..1800seconds')
    if sys.platform.startswith('linux'):
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    def expired(*unused):raise TimeoutError('bounded CPU model gate deadline')
    signal.signal(signal.SIGALRM,expired);signal.alarm(args.max_seconds)
    try:print(json.dumps(run_gate(args.n,args.parallel),sort_keys=True))
    finally:signal.alarm(0)
