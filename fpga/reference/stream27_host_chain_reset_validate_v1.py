"""Validate bounded diagnostic observation shape, not functional reset PASS."""
import json

PUBLIC=('busy','done','error','warm_done','read_valid')


def validate(stdout,stderr,returncode,config,assets):
    if config!={'aw':5,'purpose':'reset-observation'} or assets or returncode!=0 or stderr:raise ValueError('RESET_DIAGNOSTIC_CONFIG_EXIT')
    value=json.loads(stdout)
    if set(value)!={'schema','rows'} or value['schema']!='s4-reset-observation-v1':raise ValueError('RESET_DIAGNOSTIC_SCHEMA')
    expected=[(history,age,step,phase) for history in (0,1) for age in (10,236)
              for step,phase in [(0,'before_reset'),(1,'released')]+[(k,p) for k in range(2,10) for p in ('pre','rise','fall')]]
    rows=value['rows']
    if len(rows)!=len(expected):raise ValueError('RESET_DIAGNOSTIC_ROW_COUNT')
    for row,key in zip(rows,expected):
        if tuple(row.get(x) for x in ('history','age','step','phase'))!=key:raise ValueError('RESET_DIAGNOSTIC_ORDER')
        fields={k:v for k,v in row.items() if k not in ('history','age','step','phase')}
        if not fields or any(type(v) is not int or not 0<=v<=0xffffffff for v in fields.values()):raise ValueError('RESET_DIAGNOSTIC_TYPED_VALUES')
        if any(row[x] not in (0,1) for x in PUBLIC):raise ValueError('RESET_DIAGNOSTIC_PUBLIC_FLAGS')
    dirty=[{k:row[k] for k in ('history','age','step','phase',*PUBLIC)} for row in rows
           if row['step']>=2 and row['phase']=='fall' and any(row[x] for x in PUBLIC)]
    return dict(status='PASS_expected_contracts',scope='DIAGNOSTIC_OBSERVATION_ONLY, not functional reset/PRP PASS or promotion',
      rows=len(rows),dirty_public_snapshots=dirty,promotion_allowed=False)
