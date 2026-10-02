"""T5b qualification recipes: eight shared-control mutants and AW16 E0..E9.

This extends the frozen T5 batch/reuse plan. No native work or large-N numeric
oracle is performed here; the archived passed AW16 integer vector is reused.
"""
from . import core27_prefill_pipe_v1_structure as design
from . import core27_prefill_pipe_v1_gates as gates
from . import core27_prefill_pipe_v1_mutations as mutations

AW16_BENCH='rtl/tb/core27_prefill_pipe_tail_aw16_v1.cpp'
AW16_VECTOR='results/throughput-20260929/core27-prefill-aw16-reset-middle-v2/vectors.txt'
AW16_VECTOR_SHA='1bf48c7afb2145813573e5f10e2075194128de65a07863ef4bdf5bf85e6d66e0'
AW5_VECTOR='results/throughput-20260929/core27-prefill-aw5-base-change-v2/vectors.txt'


def aw16_harness(root=design.ROOT):
    gates.validate(root)
    source=(root/'rtl/tb/core27_prefill_pipe_tail_v1.cpp').read_text()
    for old,new in (
        ('// AW5-first targeted T5 qualification;','// AW16 targeted T5b qualification;'),
        ('n==32 && a==604832956 && b==1000000000','n==65536 && a==604832956 && b==1000000000'),
        ('exact AW5 targeted profile','exact AW16 targeted profile'),
        ('need(changed || row=="final" || age==0,"non-final emission probes target commit E0 only");',
         'need(n/16>2 && (n/16)/2<n/16-1,"AW16 middle must be distinct from final");'),
        ('while(!d.done && elapsed<20000)','while(!d.done && elapsed<200000)'),
        ('while(!triggered && elapsed<20000)','while(!triggered && elapsed<200000)'),
        ('d.conversion_cycles==(fast?0:11)','d.conversion_cycles==(fast?0:4105)')):
        source=design.once(source,old,new)
    return source


def shared_mutants(root=design.ROOT):
    control=None;mutants={};contracts={}
    for name in mutations.NAMES:
        fresh,mutant,contract=mutations.pair_sources(root,name)
        if name not in mutations.TEE_MUTANTS:
            fresh[mutations.CARRY]=mutations.tee_control(fresh[mutations.CARRY])
            mutant[mutations.CARRY]=mutations.tee_control(mutant[mutations.CARRY])
        if control is not None and fresh!=control:raise ValueError('byte-identical common control required')
        control=fresh
        contracts[name]=dict(contract,shared_control_guard_removal='T5_EMIT_SIGNED32_REPRESENTATION')
        mutants[name]=mutant
    return control,mutants,contracts


def step(aw,mode,age=None,row=None,name=None):
    if aw not in (5,16):raise ValueError('bounded AW')
    simple=mode in ('--changed-base','--base-reject','--reload-control')
    if not simple and (mode not in ('--tail-reset','--tail-error','--tail-carry-error') or age not in range(10) or row not in ('first','middle','final')):
        raise ValueError('typed fault coordinate')
    n=1<<aw
    age,row=(0,'none') if simple else (age,row)
    index=0 if row=='first' else n//32 if row=='middle' else n//16-1
    successful,recoveries=(3,0) if mode=='--changed-base' else (2,1) if mode=='--base-reject' else (2,0) if mode=='--reload-control' else (1,1)
    footer=f'T5_TARGET_PASS mode={mode} age={age} row={row} row_index={index} middle_aliases_final={int(aw==5)} event_hits=1 successful={successful} readbacks={successful} recoveries={recoveries}\n'
    argv=['{exe}',mode,'{root}/'+(AW16_VECTOR if aw==16 else AW5_VECTOR)]+([] if simple else [str(age),row])+['control']
    return dict(name=name or mode[2:]+'-'+row+'-e'+str(age),argv=argv,expected_returncode=0,expected_stdout=footer,expected_stderr='')


def full_matrix():
    faults={'reset':'--tail-reset','host-error':'--tail-error','carry-error':'--tail-carry-error'}
    anchor=[step(16,mode,age,'final',f'{fault}-final-e{age}') for fault,mode in faults.items() for age in (7,8,9)]
    groups={}
    # Distinct AW16 middle is next priority after late/final anchor, then early
    # final edges and first rows. Every selected invocation is a fresh DUT.
    for row in ('middle','final','first'):
        for fault,mode in faults.items():
            ages=range(7) if row=='final' else range(10)
            groups[f'{fault}-{row}']=[step(16,mode,age,row,f'{fault}-{row}-e{age}') for age in ages]
    groups['base-reload']=[step(16,mode,name=mode[2:]) for mode in ('--changed-base','--base-reject','--reload-control')]
    cases=anchor+[s for group in groups.values() for s in group]
    if len(cases)!=93 or len({s['name'] for s in cases})!=93:raise ValueError('complete unique full-N matrix')
    return anchor,groups
