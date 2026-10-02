"""Expected broken-source reset witness, never a functional reset PASS."""
import json


def validate(stdout,stderr,returncode,config,assets):
    if config!={'aw':5,'purpose':'reset-origin-expected-fault'} or assets or returncode!=1 or stderr!='S4_HOST_LOAD_IDLE\n':raise ValueError('RESET_ORIGIN_TYPED_FAULT_EXIT')
    if not stdout.startswith('{"schema":"s4-reset-observation-v1","rows":[') or stdout.endswith(']}\n'):raise ValueError('RESET_ORIGIN_PRESERVED_PARTIAL_OUTPUT')
    decoder=json.JSONDecoder();offset=stdout.index('[',stdout.index('"rows"'))+1;rows=[]
    while offset<len(stdout):
        while offset<len(stdout) and stdout[offset] in ', \n':offset+=1
        if offset==len(stdout):break
        row,offset=decoder.raw_decode(stdout,offset);rows.append(row)
    phases=[(0,'before_reset')]+[(1,p) for p in ('assert_pre','assert_rise','assert_fall','release_pre','release_rise','released')]+[(k,p) for k in range(2,10) for p in ('pre','rise','fall')]
    if [(r['history'],r['age'],r['step'],r['phase']) for r in rows]!=[(0,age,step,phase) for age in (10,236) for step,phase in phases]:raise ValueError('RESET_ORIGIN_EXACT_PREFIX')
    for r in rows:
        values={k:v for k,v in r.items() if k not in ('history','age','step','phase')}
        if any(type(v) is not int or not 0<=v<=0xffffffff for v in values.values()):raise ValueError('RESET_ORIGIN_TYPED_SIGNALS')
    flags=('busy','done','error','warm_done','read_valid')
    if any(any(r[k] for k in flags) for r in rows if r['age']==10 and r['step']>=2 and r['phase']=='fall'):raise ValueError('RESET_ORIGIN_AGE10_QUIET_CONTROL')
    selected=[r for r in rows if r['age']==236]
    release=next(r for r in selected if r['phase']=='released')
    public=next(r for r in selected if r['step']==2 and r['phase']=='fall')
    if release['error']!=0 or release['protocol_error']!=1 or release['raw_child_error']!=1 or public['done']!=1 or public['error']!=1:raise ValueError('RESET_ORIGIN_ACTUAL_FAULT_CASCADE')
    return dict(status='PASS_expected_contracts',scope='Expected failing-source reset ORIGIN DIAGNOSTIC only; functional long reset remains FAIL, no promotion.',
      snapshots=len(rows),pre_release=next(r for r in selected if r['phase']=='release_pre'),released=release,public_fault=public,promotion_allowed=False)
