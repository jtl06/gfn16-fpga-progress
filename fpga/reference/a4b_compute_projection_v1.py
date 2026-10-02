"""Scalar full-operation accounting; no exponent expansion or full-N arithmetic.

Representative A4b schedules are measured; applicability to the old sample is
a fixed-schedule projection, not a native run of that numerical sample.
"""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NATIVE='results/throughput-20260929/track-a4b-representative-aw16-native-independent-v1.json'
NATIVE_SHA='4106cd4b7707eaf891db940305c406a013ed83b926614703f692e6b4bdcbb011'
COUNT=1911814

def calculate(measured,period_ps=10958,count=COUNT):
    if type(period_ps) is not int or period_ps<=0 or type(count) is not int or count<1:
        raise ValueError('A4B_EXACT_POSITIVE_INTEGER_PROJECTION')
    expected=dict(warm_backend_cycles=24721,warm_host_latency=24723,
        cold_cached_roots_backend_cycles=28829,cold_loaded_roots_backend_cycles=37572,
        cold_loaded_roots_host_latency=37574,NTT_cycles=20558,post_NTT_cycles=4158,
        cold_prefill_cycles=4106,root_load_cycles=8743,seed_setup_cycles=815)
    if any(type(measured.get(k)) is not int or measured[k]!=v for k,v in expected.items()):
        raise ValueError('A4B_MEASURED_OPERATION_LEDGER')
    # Seed815 is already included in aggregate NTT20558, never added twice.
    warm_control=24721-20558-4158
    cold_control=37572-20558-4158-4106-8743
    rows=dict(ntt=count*20558,post_ntt=count*4158,cold_prefill=4106,
              cold_root_load=8743,backend_control=cold_control+(count-1)*warm_control)
    backend=sum(rows.values());command=backend+2*count
    if backend!=37572+(count-1)*24721:raise ValueError('A4B_TOTAL_RECONCILIATION')
    seconds=lambda clocks,ps: str(Decimal(clocks)*Decimal(ps)/Decimal(10**12))
    parent=41674+(count-1)*28826
    return dict(status='provisional_compute_only_projection_no_promotion',sample=dict(n=65536,base=604832956,square_operations=count),
        period_ps=period_ps,backend_cycles_by_phase=rows,backend_cycles=backend,
        command_square_latency_cycles=command,command_edge_overhead=2*count,
        backend_compute_seconds=seconds(backend,period_ps),command_latency_sum_seconds=seconds(command,period_ps),
        parent_t5b_backend_cycles=parent,parent_t5b_compute_seconds=seconds(parent,9668),
        cold_operations=1,warm_operations=count-1,cold_control_cycles=cold_control,warm_control_cycles=warm_control,
        seed_counted_inside_ntt=True,measured_sample_base=False,measured_full_PRP=False,
        audited_clock_claim=False,promotion_allowed=False,
        exclusions=['initial base setup and digit load','final canonicalization/readback','inter-command issue gaps and response backpressure',
                    'periodic checkpoints and read-induced prefill-cold transitions','board/host I/O, proof and transfer work'],
        coverage='A4b own normal AW5, boundary, five admission mutants and16-square AW16 representative. No A4b-specific full PRP/1000-chain result; A-next results are not inherited backward.')

def project():
    raw=(ROOT/NATIVE).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=NATIVE_SHA:raise ValueError('A4B_NATIVE_RECEIPT_PIN')
    result=calculate(json.loads(raw)['measurements'])
    result['native_schedule_receipt_sha256']=NATIVE_SHA
    return result

if __name__=='__main__':print(json.dumps(project(),indent=2))
