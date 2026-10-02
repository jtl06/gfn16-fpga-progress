"""Warm-candidate scheduling feasibility model, NOT RTL or fitted throughput.

Assumes a redesigned controller, independent digit contexts, separately
accessible NTT data banks, and shared cached roots for a fixed transform size.
The frozen core does NOT implement these interfaces or this overlap. No memory
ports, mux timing, setup latency or routing are inferred to be free.
The banks argument counts full three-field NTT data-buffer sets, NOT the
many physical banking partitions within each existing NTT engine.
"""
import argparse
import hashlib
import heapq
import json
from pathlib import Path


def schedule(conversion, ntt, crt, carry_tail, contexts, banks, rounds=100):
    values=(conversion,ntt,crt,carry_tail,contexts,banks,rounds)
    if any(type(x) is not int or x <= 0 for x in values):
        raise ValueError('positive integer durations/capacities required')
    states=['convert']*contexts
    completed=[0]*contexts
    owned=[None]*contexts
    free_banks=set(range(banks))
    engines={'convert':None,'ntt':None,'post':None}
    events=[];trace=[];finished=[];now=0;sequence=0

    def event(at,kind,context):
        nonlocal sequence
        sequence+=1
        heapq.heappush(events,(at,sequence,kind,context))

    while len(finished)<contexts*rounds:
        # Drain downstream first, then advance upstream. One engine per stage.
        for stage in ('post','ntt','convert'):
            if engines[stage] is not None:
                continue
            ready=[i for i,s in enumerate(states) if s==stage]
            if not ready or (stage=='convert' and not free_banks):
                continue
            i=min(ready,key=lambda k:(completed[k],k))
            if stage=='convert':
                owned[i]=min(free_banks);free_banks.remove(owned[i])
            duration={'convert':conversion,'ntt':ntt,'post':crt+carry_tail}[stage]
            engines[stage]=i;states[i]='active-'+stage
            trace.append(dict(stage=stage,context=i,round=completed[i],bank=owned[i],
                              start=now,end=now+duration))
            if stage=='post':
                # NTT memory is released after the last CRT input drain, not
                # only after carry finishes. The frozen core does not do this.
                event(now+crt,'release-bank',i)
            event(now+duration,stage,i)
        if not events:
            raise AssertionError('model deadlock')
        now=events[0][0]
        while events and events[0][0]==now:
            _,_,kind,i=heapq.heappop(events)
            if kind=='release-bank':
                assert owned[i] is not None and owned[i] not in free_banks
                free_banks.add(owned[i]);owned[i]=None
            else:
                assert engines[kind]==i
                engines[kind]=None
                if kind=='post':
                    assert owned[i] is None
                    completed[i]+=1;finished.append(now)
                    states[i]='convert' if completed[i]<rounds else 'done'
                else:
                    states[i]='ntt' if kind=='convert' else 'post'
    serial=conversion+ntt+crt+carry_tail
    bound=max(conversion,ntt,crt+carry_tail,
              (conversion+ntt+crt)/banks,serial/contexts)
    return dict(status='abstract_redesigned_schedule_not_rtl',contexts=contexts,ntt_data_sets=banks,
                rounds_per_context=rounds,completed_squares=len(finished),elapsed_cycles=now,
                average_cycles_per_square=now/len(finished),
                resource_interval_lower_bound=bound,
                serial_warm_cycles=serial,
                finite_run_cycle_speedup=serial*len(finished)/now,
                trace=trace)


def from_report(path):
    report=json.loads(path.read_text())
    if report.get('status')!='passed':
        raise ValueError('requires passed source report')
    rows=[r for r in report.get('metrics',[]) if r.get('case')=='full-random-s1-d1'
          and r.get('n')==65536 and r.get('base')==604832956]
    if len(rows)!=1:
        raise ValueError('requires unique representative full-size warm case')
    row=rows[0]
    if (row.get('readback') is not True or row.get('root_cache_warm') is not True
        or row.get('root_loads')!=0 or row.get('root_hits')!=4 or row.get('roots')!=0
        or row['cycles']!=sum(row[k] for k in ('conversion','roots','ntt','crt','carry'))):
        raise ValueError('inconsistent measured warm sample')
    results=[]
    for contexts,banks in ((1,1),(2,1),(2,2),(3,2),(4,2)):
        result=schedule(row['conversion'],row['ntt'],row['crt'],row['carry'],contexts,banks)
        result.pop('trace')
        # Logical bit counts only. Actual M20K packing, extra ports and muxes
        # require RTL and fitting. Baseline words/ports are explicitly32-bit.
        result['extra_ntt_data_bits']=(banks-1)*3*65536*32
        result['extra_candidate_digit_bits']=(contexts-1)*65536*32
        results.append(result)
    return dict(status='architecture_feasibility_not_throughput_projection',
        report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),sample=row,
        configurations=results,limitations=[
            'No RTL implementation, physical fit, board measurement or frequency assumption.',
            'Warm fixed-size independent candidates only; no cold roots, errors or checkpoints.',
            'Redesigned independently accessible data banks and digit contexts are assumed, not present in the frozen core.',
            'Post stage reserves the carry engine for CRT drain plus carry tail; setup/control costs are optimistically hidden.',
            'Measured phase durations may change after interfaces, buffering and arbitration are implemented.',
            'Memory numbers are added logical bits only, excluding packing waste, FIFOs, metadata and routing.',
            'Greedy schedule is constructive under these assumptions, not proof of optimal scheduling or hardware feasibility.',
        ])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=from_report(args.report)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
