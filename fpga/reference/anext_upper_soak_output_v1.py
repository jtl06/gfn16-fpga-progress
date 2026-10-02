"""Strict A-next counters plus frozen donor GMP/checkpoint validation.

Legacy field renaming is solely an internal adapter for the unchanged numerical
validator. Native rows retain actual prefill/post and derived control overhead;
that overhead is never presented as a measured CRT pipeline latency.
"""
import hashlib,importlib.util,json
from pathlib import Path
from fpga.reference.anext_point_contract_v1 import schedule
ROOT=Path(__file__).resolve().parents[1]
DONOR='donor/fpga/reference/core27_t5b_soak_native_v1.py'
DONOR_SHA='43a35c1bd1c2d256fb793a8087681e9e2c0281441eeca57aa2fd6dfdf7934db0'
CORE_SHA='47a84a9f20490709756af28623b3a7233832a2080a435f2fe71b2487b0dbe8bc'
def need(ok,why):
    if not ok:raise ValueError(why)
def donor():
    p=ROOT/DONOR;need(hashlib.sha256(p.read_bytes()).hexdigest()==DONOR_SHA,'immutable donor adapter')
    s=importlib.util.spec_from_file_location('_anext_donor',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def normalise(stdout,oracle,reference):
    plan,segment=reference.check_oracle(oracle);s=schedule(plan['profile']['aw'])
    need(plan['profile']['base']>=max(2*s['n']+5,(2*(2*s['n']+384)+2)//3+1),'A-next proof base floor')
    need(stdout.endswith('\n'),'complete native output')
    checkpoints={c['step'] for c in segment['checkpoints']};ops=0;cold_count=0;rows=[];native_metrics=[]
    for line in stdout.splitlines():
        prefix,separator,payload=line.partition(' ');need(separator,'native JSON row');row=json.loads(payload)
        if prefix=='ANEXT_SOAK_STEP':
            keys={'case_id','step','bit','cycles','prefill','roots','ntt','post','control','profile_loads','profile_hits'}
            need(set(row)==keys and all(type(row[k]) is int for k in keys-{'case_id'}),'exact A-next phase fields')
            need(ops<segment['operations'] and row['step']==segment['start']+ops+1,'ordered operation')
            cold=row['step']-1 in checkpoints;load=ops==0
            expected=dict(cycles=s['warm_backend']+(s['cold_cached_backend']-s['warm_backend'])*cold+9*load,
                          prefill=s['cold_prefill_child_cycles']*cold,roots=9*load,ntt=s['ntt_controller_cycles'],post=s['post_child_cycles'],control=7 if cold else 5,
                          profile_loads=int(load),profile_hits=int(not load))
            need(all(row[k]==v for k,v in expected.items()),'A-next checkpoint/cache/prefill schedule')
            native_metrics.append(row.copy());cold_count+=cold;ops+=1
            renamed={k:v for k,v in row.items() if k not in ('prefill','post','control')}
            renamed.update(conversion=row['prefill'],carry=row['post'],crt=row['control'])
            rows.append('SOAK_STEP '+json.dumps(renamed,separators=(',',':')))
        elif prefix=='ANEXT_SOAK_CHECK':rows.append('SOAK_CHECK '+json.dumps(row,separators=(',',':')))
        elif prefix=='ANEXT_SOAK_PASS':
            keys={'case_id','mode','start','end','operations','doubles','readbacks','cycles','resets','loaded_digits','cold_prefill','warm_prefill','cache_cold','cache_warm'}
            need(set(row)==keys,'exact native footer fields')
            need((row['cold_prefill'],row['warm_prefill'],row['cache_cold'],row['cache_warm'])==(cold_count,ops-cold_count,1,ops-1),'separate cache and prefill accounting')
            renamed={k:v for k,v in row.items() if k not in ('cold_prefill','warm_prefill','cache_cold','cache_warm')};renamed.update(cold=1,warm=ops-1)
            rows.append('SOAK_PASS '+json.dumps(renamed,separators=(',',':')))
        else:raise ValueError('unknown native soak row')
    return '\n'.join(rows)+'\n',dict(operations=ops,cold_prefill=cold_count,warm_prefill=ops-cold_count,metrics=native_metrics,
        legacy_numeric_adapter_fields=dict(conversion='measured prefill',carry='measured combined post service',crt='derived backend control overhead, NOT measured CRT latency',cold='cache load count',warm='cache hit count'))

def validate(stdout,stderr,returncode,config,assets):
    need(set(config)=={'negative'} and config['negative'] in ('none','boundary','loaded-state'),'exact soak configuration')
    need(set(assets)=={'oracle','runtime'},'closed donor assets')
    d=donor();admitted=d.admit_runtime(assets['runtime']) # BEFORE any full-N integer work/import.
    ref=d.reference();oracle=json.loads(assets['oracle']);converted,metrics=normalise(stdout,oracle,ref)
    result=d.validate(converted,stderr,returncode,config,assets)
    need(hashlib.sha256((ROOT/'rtl/kernel/genefer_anext_upper_core_v1.sv').read_bytes()).hexdigest()==CORE_SHA,'separate actual A-next candidate identity')
    return dict(status='PASS_expected_contracts',candidate='A-next-upper-v1',candidate_core_sha256=CORE_SHA,
                donor_reference_validation=result,donor_runtime_admission=admitted,native_anext_metrics=metrics,
                donor_provenance_unchanged=True,promotion_allowed=False,
                scope='Actual command-host chain; numeric donor provenance is not a T5b RTL result inherited by A-next.')
