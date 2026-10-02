"""One full-N source-selected P8/P16 dependent FIFO job; metadata-only coordinator.

The immutable record-base paired60 model includes exactly the baseline49
candidate. T5b stays dormant in this harness; the unchanged independent
three-prime NTT/centered CRT/serial integer reference checks all final96 bits.
All full-N arithmetic and HDL execute only on admitted Linux workers.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_s4_continuous_v1.py'
CPP='rtl/tb/stream27_s4_continuous_v1.cpp'
HEADER='rtl/tb/stream27_s4_continuous_config_v1.h'
TEST='tests/test_stream27_s4_continuous_v1.py'
MODEL=ROOT/'results/throughput-20260929/s4-aw16-p8-record-base-host-native-v1/input'
MODEL_SHA='60c82e283b29a38529bab12fc6ae274330a6b13cb2ee209471fca4ff8ccc140b'
CORE='ee65a33fdaac06de83c7122f7e95704c835f4c1ee55171f846ac7e553ed30d21'
PIPE_MODEL=ROOT/'results/throughput-20260929/s4-aw16-p8-canon-pipe-host-normal-v2b/input'
PIPE_MODEL_SHA='22fd90c8635aea662085c73ba4c830460965e8812e84589eaaceb265bc2640e9'
PIPE_CORE='140e2b306e39a5fba02046917d0733eb31ed1e2f9c80f81be7fd086181b8c051'
BOUNDARY_MODEL=ROOT/'results/throughput-20260929/trackS-boundary-inputreg-v1/whole-normal-v1'
BOUNDARY_MODEL_SHA='43a0210e4613ba44cc71ab54bda5761d03fcce2676332a6327bfc6feef0ed642'
BOUNDARY_CORE='d08a71cdce6136b7ed1560045a64b27b00e4943a27bde4d98507bb7103e91bcb'
DIET_MODEL=ROOT/'results/throughput-20260929/s4-p16-diet-whole-full9-normal-v1/input'
DIET_MODEL_SHA='2a53b07f630bc7e056b0077e9d43ae925ac56d125e821a80f04d7e00abc6f51d'
DIET_CORE='b683cb1113a17652f5d6266c4298c5eb825c6af6b9f92bd28f758dba9b8de898'
REFERENCE='rtl/tb/stream27_host_chain_full_reference_v1.h'
REFERENCE_SHA='88849a77ad7c58fc99f6d56eeded2a772a78fbe2b2da03fabdf7ac71aaf12c54'
NTT='rtl/tb/stream27_shared_reference_ntt_v1.h'
NTT_SHA='c7837ba92829293131efda704dfdde347708641bf9aff46dccbcb87b825ba390'
RUNTIME='rtl/tb/native_runtime_context_v1.h'
N,P,BASE,INTERVAL,CARRY_DONE,FIRST_DIGIT=65536,8,604832956,16653,24847,16652
PATTERN=(0,1,0,1,1,0,1,0)
NEGATIVE='S4_CONTINUOUS_NEGATIVE_ORACLE_REJECT\n'


def need(value,why):
    if not value:raise ValueError('S4 continuous: '+why)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def plan(canonical_pipe_stages=0,boundary_inputreg=0,p16_diet=0):
    need(type(canonical_pipe_stages) is int and canonical_pipe_stages in (0,1),'explicit canonical pipeline flag')
    need(type(boundary_inputreg) is int and boundary_inputreg in (0,1) and
         (not boundary_inputreg or canonical_pipe_stages==1),'explicit frozen boundary/canonical flags')
    need(type(p16_diet) is int and p16_diet in (0,1) and
         (not p16_diet or (canonical_pipe_stages==1 and boundary_inputreg==0)),
         'explicit frozen P16 diet/canonical1 with no boundary substitution')
    value=dict(schema='stream27-s4-continuous-plan-v1',
        profile=dict(aw=16,n=N,p=16 if p16_diet else P,contexts=1,base=BASE,epoch_seed=65534,canonical_pipe_stages=canonical_pipe_stages),
        initial=dict(algorithm='xorshift32 unsigned modulo base',seed=0x9135ba27,
                     signed_minus_one_positions=[17,N-1],full_nontrivial_dense=True),
        double_bits=''.join(str(PATTERN[i%8]) for i in range(1000)),maximum_operations=1000,
        candidate_root_sha256=DIET_CORE if p16_diet else BOUNDARY_CORE if boundary_inputreg else PIPE_CORE if canonical_pipe_stages else CORE,reference_sha256=REFERENCE_SHA,ntt_sha256=NTT_SHA,
        contract='ONE reset/load/start; dependent FIFO; final-only canonical/copy/full readback, no per-square host barrier.',
        geometry=dict(interval=8459 if p16_diet else INTERVAL,carry_done=12557 if p16_diet else CARRY_DONE,
                      first_digit=8458 if p16_diet else FIRST_DIGIT,cold_first=102))
    if boundary_inputreg:value['profile']['boundary_inputreg']=1
    if p16_diet:value['profile'].update(p16_diet=1,corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
    value['case_id']=sha(canonical(value));return value


def counts(operations,special=0,canonical_pipe_stages=0,boundary_inputreg=0,p16_diet=0):
    need(type(operations) is int and operations in (1,100,1000) and type(special) is int and special in (0,1),'finite operation/special count')
    descriptors=operations-1;exchange=max(0,operations-5)
    case=plan(canonical_pipe_stages,boundary_inputreg,p16_diet);geo=case['geometry'];p=case['profile']['p']
    return dict(case_id=case['case_id'],operations=operations,doubles=sum(PATTERN[i%8] for i in range(operations)),
        resets=1,loads=1,loaded_digits=N,starts=1,readbacks=1,words=N,signed96_words=N,
        feed_descriptors=descriptors,fifo_peak=min(4,descriptors),full_exchanges=exchange,
        backpressure_edges=102+exchange*geo['interval']-operations+1 if exchange else 0,
        final_rows=N//p,canonical_cycles=(6+3*canonical_pipe_stages+special)*N,copy_cycles=N+3,
        candidate_cycles=102+(operations-1)*geo['interval']+geo['carry_done']+2+(7+3*canonical_pipe_stages+special)*N+4,
        profile_loads=1,profile_hits=0,root_cycles=99,conversion_cycles=N//p,special=special)


def validate(stdout,stderr,returncode,config,assets):
    need(type(config) is dict and set(config) in ({'operations','negative','canonical_pipe_stages'},
         {'operations','negative','canonical_pipe_stages','boundary_inputreg'},
         {'operations','negative','canonical_pipe_stages','p16_diet'}) and
        type(config['operations']) is int and config['operations'] in (1,100,1000) and
        config['negative'] in ('none','oracle') and (config['negative']=='none' or config['operations']==1),'exact normal/fault configuration')
    stages=config['canonical_pipe_stages'];boundary=config.get('boundary_inputreg',0);diet=config.get('p16_diet',0);case=plan(stages,boundary,diet)
    need('boundary_inputreg' not in config or boundary==1,'explicit source-specific boundary configuration')
    need('p16_diet' not in config or diet==1,'explicit source-specific P16 diet configuration')
    need(type(assets) is dict and set(assets)=={'plan'} and json.loads(assets['plan'])==case,'unchanged explicit numeric plan')
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int,'typed native output')
    operations=config['operations']
    if config['negative']=='oracle':
        need((stdout,stderr,returncode)==('',NEGATIVE,1),'exact separate reference-comparator rejection')
        return dict(status='PASS_expected_contracts',negative='oracle',operations=1,promotion_allowed=False)
    need(returncode==0 and stderr=='' and stdout.endswith('\n'),'normal native success')
    rows=[]
    for line in stdout.splitlines():
        prefix,sep,body=line.partition(' ');need(bool(sep),'JSON row separator');rows.append((prefix,json.loads(body)))
    need(len(rows)==operations+1,'all descriptor rows plus final image/footer only')
    for index,(prefix,value) in enumerate(rows[:-2],1):
        wanted=dict(index=index,age=102+index*case['geometry']['interval'],bit=PATTERN[index%8])
        need(prefix=='S4_CONTINUOUS_POP' and value==wanted and all(type(v) is int for v in value.values()),'ordered actual descriptor age/index/bit')
    prefix,image=rows[-2]
    need(prefix=='S4_CONTINUOUS_IMAGE' and set(image)=={'actual','expected'},'one complete final image')
    for name in ('actual','expected'):
        need(type(image[name]) is list and len(image[name])==N and all(type(v) is int and -1<=v<BASE for v in image[name]),'every canonical signed96 word')
    need(image['actual']==image['expected'],'full independent final array equality')
    special=int(image['expected'][0]==-1)
    need((image['expected']==[-1]+[0]*(N-1)) if special else all(v>=0 for v in image['expected']),'exact canonical special/ordinary representation')
    prefix,value=rows[-1];wanted=counts(operations,special,stages,boundary,diet)
    timers={'reference_ms','candidate_ms','read_ms'}
    need(prefix=='S4_CONTINUOUS_PASS' and set(value)==set(wanted)|timers and
         all(value[k]==v for k,v in wanted.items()) and
         all(type(v) is int for k,v in value.items() if k!='case_id'),'exact one-job/cold/FIFO/phase/cycle/full-read counts')
    limit=10450 if operations==1000 else 1800
    need(all(value[k]>=0 for k in timers) and sum(value[k] for k in timers)<=limit*1000,'finite native phase observations')
    result=dict(status='PASS_expected_contracts',candidate='diet-corr2-sharedmlab-factored-canonical1-P16-context1' if diet else 'boundary-inputreg1-canonical-pipe1-P8-context1' if boundary else 'canonical-pipe1-P8-context1' if stages else 'baseline-P8-context1',
        candidate_root_sha256=case['candidate_root_sha256'],canonical_pipe_stages=stages,base=BASE,operations=operations,counts=wanted,
        phase_wall_ms={key:value[key] for key in sorted(timers)},independent_reference_equal=True,
        final_actual_sha256=sha(canonical(image['actual'])),final_expected_sha256=sha(canonical(image['expected'])),
        uninterrupted_1000_native=operations==1000,promotion_allowed=False,
        scope='ONE actually dependent FIFO job, exact source-selected candidate; independent reference is native-only, T5b dormant, not full PRP/clock or inherited9/25/100-op result.')
    if boundary:result['boundary_inputreg']=1
    if diet:result['p16_diet']=1
    return result


def role(operations,canonical_pipe_stages=0,boundary_inputreg=0,p16_diet=0):
    need(type(operations) is int and operations in (1,100,1000),'normal-first finite short/pilot/continuous role')
    case=plan(canonical_pipe_stages,boundary_inputreg,p16_diet)
    model=DIET_MODEL if p16_diet else BOUNDARY_MODEL if boundary_inputreg else PIPE_MODEL if canonical_pipe_stages else MODEL
    raw=(model/'manifest.json').read_bytes();need(sha(raw)==(DIET_MODEL_SHA if p16_diet else BOUNDARY_MODEL_SHA if boundary_inputreg else PIPE_MODEL_SHA if canonical_pipe_stages else MODEL_SHA),'frozen matched record-base model')
    m=json.loads(raw);files={}
    for name,pin in m['sources'].items():
        path=model/'source/fpga'/name
        need(not path.is_symlink() and sha(path.read_bytes())==pin,'unchanged closed paired model '+name)
        files[name]=path.read_bytes()
    parameters=dict(AW=16,P=16 if p16_diet else 8,CONTEXTS=1,EPOCH_SEED=65534)
    if canonical_pipe_stages:parameters['CANONICAL_PIPE_STAGES']=1
    if boundary_inputreg:parameters['BOUNDARY_INPUTREG']=1
    if p16_diet:parameters.update(CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1)
    root='rtl/genefer_stream27_host_chain_aw16_p8_'+('canonreg' if canonical_pipe_stages else 'param')+'_v1.sv'
    if boundary_inputreg:root=root[:-3]+'_boundary_inputreg_v1.sv'
    if p16_diet:root='rtl/genefer_stream27_host_chain_aw16_p16_diet_v1.sv'
    need(len(m['build']['sv_sources'])==(69 if p16_diet else 60+boundary_inputreg) and m['build']['parameters']==parameters and
         m['sources'][root]==case['candidate_root_sha256'],'exact source-selected candidate within paired model')
    for name,pin in ((REFERENCE,REFERENCE_SHA),(NTT,NTT_SHA)):
        need(sha(files[name])==pin,'unchanged independent native reference')
    top=m['build']['top'];geo=case['geometry'];p=case['profile']['p']
    files[HEADER]=(f'#include <cstdint>\n#include "V{top}.h"\nusing DUT=V{top};\n'
        f'constexpr unsigned AW=16,P={p},N=65536,BASE={BASE};\n'
        f'constexpr unsigned CANONICAL_PIPE_STAGES={canonical_pipe_stages};\n'
        f'constexpr uint64_t INTERVAL={geo["interval"]},CARRY_DONE={geo["carry_done"]},FIRST_DIGIT={geo["first_digit"]};\n'
        f'constexpr const char* CASE_ID="{case["case_id"]}";\n').encode()
    for name in (SELF,CPP,TEST,RUNTIME):files[name]=(ROOT/name).read_bytes()
    files['continuous/plan.json']=json.dumps(case,indent=2).encode()+b'\n'
    m['build']['cpp_source']=CPP
    config=dict(operations=operations,negative='none',canonical_pipe_stages=canonical_pipe_stages)
    if boundary_inputreg:config['boundary_inputreg']=1
    if p16_diet:config['p16_diet']=1
    m['steps']=[dict(name='stream27-s4-continuous-normal',argv=['{exe}',str(operations)],expected_returncode=0,expected_stderr='',
        validator=dict(source=SELF,function='validate',config=config,assets={'plan':'continuous/plan.json'}))]
    m['sources']={name:sha(data) for name,data in files.items()}
    m['continuous']=dict(plan=case,operations=operations,canonical_pipe_stages=canonical_pipe_stages,counts_ordinary_source_projection=counts(operations,0,canonical_pipe_stages,boundary_inputreg,p16_diet),
        T5b_compiled_but_dormant=True,original_RTL_unchanged=True,full_N_math_locally_performed=False,
        requested_scope='uninterrupted1000' if operations==1000 else 'one continuous100-operation timing pilot' if operations==100 else 'one exact cold loaded-state short')
    if boundary_inputreg:m['continuous']['boundary_inputreg']=1
    if p16_diet:m['continuous'].update(p16_diet=1,small_PRP_prerequisite='separate supported-small-geometry diet qualification required; no P8 result inherited')
    return m,files


def prepare(operations,output,canonical_pipe_stages=0,boundary_inputreg=0,p16_diet=0):
    output=Path(output).resolve()
    need(not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'fresh source output/no PAUSE')
    m,files=role(operations,canonical_pipe_stages,boundary_inputreg,p16_diet);source=output/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(status='source_prepared_not_native',operations=operations,manifest_sha256=sha((output/'manifest.json').read_bytes()),
                canonical_pipe_stages=canonical_pipe_stages,boundary_inputreg=boundary_inputreg,p16_diet=p16_diet,selected_candidate_unchanged=True,full_N_numeric_locally_performed=False,promotion_allowed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operations',type=int,choices=(1,100,1000),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--canonical-pipe-stages',type=int,choices=(0,1),default=0)
    parser.add_argument('--boundary-inputreg',type=int,choices=(0,1),default=0)
    parser.add_argument('--p16-diet',type=int,choices=(0,1),default=0)
    args=parser.parse_args();print(json.dumps(prepare(args.operations,args.output,args.canonical_pipe_stages,args.boundary_inputreg,args.p16_diet),indent=2))
