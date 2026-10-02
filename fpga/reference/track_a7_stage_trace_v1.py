"""A7 physical-bank event analysis only; no NTT arithmetic or RTL scheduling.

Trace edges are pre-rising-edge RAM accesses. A read needs an earlier write:
same-edge mixed-port access is forbidden by the frozen RAM. Every next-stage
read also waits until all prior-stage read issues are finished (shared ports).
Alternative orders are memory feasibility bounds, not root-generator schedules.
"""
import argparse
import json
from pathlib import Path


def require(ok,kind):
    if not ok:raise ValueError(kind)


def stage_rows(n,stage,group):
    """Small geometry check of the frozen XOR-bank address construction."""
    require(n in (32,64,128,256),'A7_SMALL_GEOMETRY_ONLY')
    aw=n.bit_length()-1;require(0<=stage<aw and 0<=group<max(1,n//128),'A7_GEOMETRY_RANGE')
    pairing=stage%7;base=0;k=0
    for bit in range(aw):
        if bit!=stage and not (bit<7 and bit!=pairing):
            base|=((group>>k)&1)<<bit;k+=1
    folded=0
    for bit in range(aw):folded^=((base>>bit)&1)<<(bit%7)
    orientation=(folded>>pairing)&1
    return tuple(((base|((((bank>>pairing)&1)^orientation)<<stage))>>7)
                 if bank<n else -1 for bank in range(128))


def parse(text):
    n=None;events=[];footer=False;trace_footer=False
    for line in text.splitlines():
        if line.startswith('A7_HEADER '):
            require(n is None,'A7_DUPLICATE_HEADER');n=int(line.split()[1])
        elif line.startswith('A7 '):
            tokens=line.split();require(len(tokens)==136,'A7_TRACE_WIDTH')
            _,kind,edge,run,phase,stage,group,count,*rows=tokens
            rows=tuple(map(int,rows));require(kind in ('R','W'),'A7_TRACE_KIND')
            require(sum(row>=0 for row in rows)==int(count),'A7_TRACE_MASK')
            events.append(dict(kind=kind,edge=int(edge),run=int(run),phase=int(phase),
                               stage=int(stage),group=int(group),rows=rows))
        elif line.startswith('PASS n='):
            footer=line==f'PASS n={n} squares=2 readbacks=2 aborts=0'
        elif line.startswith('A7_TRACE_PASS '):
            trace_footer=line==f'A7_TRACE_PASS n={n} runs=2 records={len(events)}'
    require(n in (32,64,128,256,65536) and events and footer and trace_footer,'A7_COMPLETE_NATIVE_TRACE_REQUIRED')
    require({e['run'] for e in events}=={1,2},'A7_TWO_SQUARES_REQUIRED')
    return n,events


def check_stage(n,events):
    reads=[e for e in events if e['kind']=='R'];writes=[e for e in events if e['kind']=='W']
    groups=max(1,n//128)
    require(len(reads)==len(writes)==groups,'A7_STAGE_ACCESS_COUNT')
    require([e['group'] for e in reads]==list(range(groups)),'A7_PARENT_GROUP_ORDER')
    require(all(a['edge']<b['edge'] for sequence in (reads,writes) for a,b in zip(sequence,sequence[1:])),
            'A7_EDGE_ORDER')
    maps=[]
    for sequence in (reads,writes):
        accesses={}
        for event in sequence:
            for bank,row in enumerate(event['rows']):
                require(-1<=row<max(1,n//128),'A7_PHYSICAL_ROW_RANGE')
                if row<0:continue
                require(bank<min(n,128),'A7_BANK_RANGE')
                require((bank,row) not in accesses,'A7_DUPLICATE_STAGE_ACCESS')
                accesses[bank,row]=event['edge']
        require(len(accesses)==n,'A7_STAGE_WORD_COVERAGE');maps.append(accesses)
    require(maps[0].keys()==maps[1].keys(),'A7_READ_WRITE_SET')
    latencies={maps[1][key]-edge for key,edge in maps[0].items()}
    require(len(latencies)==1 and min(latencies)>0,'A7_NONUNIFORM_OR_NONPOSITIVE_LATENCY')
    return reads,writes,maps[1],latencies.pop()


def earliest(previous,current,order):
    """Min start from actual predecessor writes and next-stage read offsets."""
    pre_reads,pre_writes,commits,_=previous;reads,writes,_,latency=current
    require(sorted(order)==list(range(len(reads))),'A7_ORDER_PERMUTATION')
    offsets=[e['edge']-reads[0]['edge'] for e in reads]
    start=pre_reads[-1]['edge']+1
    witness=None
    for offset,index in zip(offsets,order):
        for bank,row in enumerate(reads[index]['rows']):
            if row<0:continue
            bound=commits[bank,row]+1-offset
            if bound>start:
                start=bound;witness=dict(bank=bank,row=row,prior_write=commits[bank,row],
                                        next_issue_offset=offset)
    # Single write port per bank; preserve measured read-to-write latency.
    old_writes={(e['edge'],bank) for e in pre_writes for bank,row in enumerate(e['rows']) if row>=0}
    while any((start+offset+latency,bank) in old_writes for offset,index in zip(offsets,order)
              for bank,row in enumerate(reads[index]['rows']) if row>=0):
        start+=1
    return start,witness


def analyze(n,events):
    groups={}
    for e in events:
        require(e['phase'] in (1,3),'A7_ONLY_NTT_PHASES')
        groups.setdefault((e['run'],e['phase'],e['stage']),[]).append(e)
    checked={key:check_stage(n,es) for key,es in groups.items()}
    transitions=[];aw=n.bit_length()-1
    runs=sorted({key[0] for key in checked})
    for run in runs:
        for phase in (1,3):
            stages=list(range(aw-1,-1,-1)) if phase==1 else list(range(aw))
            require(all((run,phase,s) in checked for s in stages),'A7_MISSING_STAGE')
            for before,after in zip(stages,stages[1:]):
                previous=checked[run,phase,before];current=checked[run,phase,after]
                count=len(current[0]);indices=list(range(count));width=(count-1).bit_length()
                orders={'current':indices,'reverse':indices[::-1],
                        'bit_reverse':sorted(indices,key=lambda i:int(f'{i:0{width}b}'[::-1],2))}
                # Rotation candidates preserve groups and their internal banks;
                # only memory feasibility is tested, root recurrence is excluded.
                for shift in (1,count//2):
                    if shift<count:orders['rotate_'+str(shift)]=indices[shift:]+indices[:shift]
                results={}
                for name,order in orders.items():
                    start,witness=earliest(previous,current,order)
                    actual=current[0][0]['edge']
                    require(start<=actual or name!='current','A7_PARENT_RAW_HAZARD')
                    results[name]=dict(earliest_edge=start,memory_only_recoverable=max(0,actual-start),
                                       tight_hazard_witness=witness)
                transitions.append(dict(run=run,phase=phase,from_stage=before,to_stage=after,
                    prior_last_issue=previous[0][-1]['edge'],prior_last_commit=previous[1][-1]['edge'],
                    observed_next_issue=current[0][0]['edge'],orders=results))
    totals={str(run):{name:sum(t['orders'][name]['memory_only_recoverable'] for t in transitions
                             if t['run']==run and name in t['orders'])
                     for name in ('current','reverse','bit_reverse')} for run in runs}
    return dict(status='event_only_memory_feasibility_not_RTL_or_cycle_qualification',n=n,
        transitions=transitions,totals_per_square=totals,
        rtl_proposal_threshold=600,
        threshold_met=any(max(values.values())>=600 for values in totals.values()),
        constraints=['One shared bank read issue per edge; next reads follow prior last issue.',
                     'Read edge strictly after corresponding prior write; same-edge RAM collision forbidden.',
                     'One shared bank write per edge; observed uniform pipeline latency retained.'],
        excluded=['Root recurrence/reseed readiness for reordered groups.','Overlapping stage-control and write-route metadata.',
                  'Timing/area and any synthesized early-start implementation.'],
        caution='Transition bounds are independent, not an additive implemented schedule; trace must precede RTL proposal.')


def missing_interlock_witness(n=256):
    """Directed tail/head RAW witness, not an RTL mutation result."""
    old=[stage_rows(n,7,g) for g in range(n//128)]
    writes={(bank,row):g+7 for g,rows in enumerate(old) for bank,row in enumerate(rows) if row>=0}
    for group in range(n//128):
        for bank,row in enumerate(stage_rows(n,6,group)):
            if row>=0 and group+2<=writes[bank,row]:
                return dict(kind='A7_MISSING_INTERLOCK_RAW',n=n,from_stage=7,to_stage=6,
                            bank=bank,row=row,read_edge=group+2,required_after=writes[bank,row])
    raise ValueError('A7_HAZARD_WITNESS_ABSENT')


def verify_native_metrics(text,lineage):
    """Retain the parent arithmetic/counter contract alongside the trace."""
    actual={}
    for line in text.splitlines():
        if line.split(' ',1)[0] in lineage['labels']:
            label,*words=line.split();require(label not in actual,'A7_DUPLICATE_NATIVE_METRIC')
            actual[label]={key:int(value) for key,value in (word.split('=') for word in words)}
    require(set(actual)==set(lineage['labels']),'A7_PARENT_METRIC_COVERAGE')
    keys=('cycles','conversion','roots','ntt','crt','carry','passes','base','profile_before',
          'profile_loads','profile_hits','profile_words','seed_setup','readback')
    for expected in lineage['metrics']:
        require(actual[expected['case']]=={key:expected[key] for key in keys},'A7_FROZEN_COUNTER_MISMATCH')
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('trace',type=Path)
    parser.add_argument('--preparation',type=Path,required=True)
    args=parser.parse_args();text=args.trace.read_text();n,events=parse(text)
    preparation=json.loads(args.preparation.read_text())
    verify_native_metrics(text,preparation['profiles'][str(n.bit_length()-1)]['vector_lineage'])
    print(json.dumps(analyze(n,events),indent=2))


if __name__=='__main__':main()
