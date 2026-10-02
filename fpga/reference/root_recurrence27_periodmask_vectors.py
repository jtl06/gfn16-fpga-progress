"""Ordinary-integer component vectors; never import candidate routing/arithmetic."""
import hashlib
from itertools import chain
from .root_recurrence_proof import FIELDS,R,check_geometry,powers,period

PERIODS=(0,)+tuple(1<<bit for bit in range(17))


def geometry_cases(lanes,field,sizes=range(1,17)):
    p,generator=FIELDS[field-1];k=lanes.bit_length();mont=R%p
    for lg in sizes:
        stages,point,_=check_geometry(lg,lanes);n=1<<lg
        psi=pow(generator,(p-1)//(2*n),p);omega=psi*psi%p
        for inverse in (False,True):
            alpha=pow(omega,-1,p) if inverse else omega
            table=[x*mont%p for x in powers(alpha,n//2,p)]
            for stage,demand in enumerate(stages):
                active=min(lanes,1<<stage);repeat=period(stage,k);shift=lg-1-stage
                step=mont if repeat<=4 else pow(alpha,1<<(k+shift+1),p)*mont%p
                rows=[]
                for indices,exponents in demand:
                    row=[None]*active
                    for index,exponent in zip(indices,exponents):
                        if row[index] is not None:assert row[index]==table[exponent]
                        row[index]=table[exponent]
                    assert all(value is not None for value in row);rows.append(row)
                contexts=min(4,repeat,len(rows))
                yield dict(name=f'lg{lg}-inv{int(inverse)}-stage{stage}',groups=len(rows),active=active,
                           period=repeat,step=step,contexts=contexts,seeds=rows[:contexts],rows=rows)
        for post in (False,True):
            alpha=pow(psi,-1,p) if post else psi;scale=pow(n,-1,p) if post else mont
            table=[x*scale%p for x in powers(alpha,n,p)];rows=[];active=min(lanes,n)
            for indices,addresses in point:
                row=[None]*active
                for index,address in zip(indices,addresses):row[index]=table[address]
                assert all(value is not None for value in row);rows.append(row)
            contexts=min(4,len(rows))
            yield dict(name=f'lg{lg}-post{int(post)}',groups=len(rows),active=active,period=0,
                       step=pow(alpha,4*lanes,p)*mont%p,contexts=contexts,seeds=rows[:contexts],rows=rows)


def targeted_cases(field):
    p,_=FIELDS[field-1];factor=7;step=factor*(R%p)%p
    for repeat in PERIODS:
        groups=min(65536,max(9,2*repeat+5)) if repeat else 65536
        contexts=min(4,groups,repeat or groups);seeds=[[19+31*index] for index in range(contexts)]
        # Independent modular exponent formula, not a candidate bit mask or
        # update-pipeline model. Arbitrary canonical seeds exercise recurrence.
        rows=[]
        for issued in range(groups):
            position=issued%repeat if repeat else issued
            rows.append([seeds[position%4][0]*pow(factor,position//4,p)%p])
        yield dict(name=f'period-{repeat}',groups=groups,active=1,period=repeat,
                   step=step,contexts=contexts,seeds=seeds,rows=rows)


def write_vectors(path,lanes,field):
    assert lanes in (16,64) and field in (1,2,3)
    cases=[];responses=words=reset_cases=0
    with path.open('x') as stream:
        for case in chain(geometry_cases(lanes,field),targeted_cases(field)):
            index=len(cases);g=case['groups'];active=case['active'];contexts=case['contexts']
            assert len(case['rows'])==g and len(case['seeds'])==contexts
            stream.write(f"CASE {case['name']} {g} {active} {case['period']} {case['step']} {contexts}\n")
            stream.write(' '.join(str(value) for row in case['seeds'] for value in row)+'\n')
            for row in case['rows']:
                assert len(row)==active
                stream.write(' '.join(map(str,row))+'\n')
            responses+=2*g;words+=2*g*active
            reset_cases+=int(g>=8 and (index%17==0 or case['name'].startswith('period-')))
            cases.append({key:value for key,value in case.items() if key not in ('seeds','rows')})
    return dict(cases=cases,case_count=len(cases),runs=2*len(cases),responses=responses,
                checked_root_words=words,aborts=4*reset_cases+1,rejects=8+4*reset_cases,
                legal_periods=list(PERIODS),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
