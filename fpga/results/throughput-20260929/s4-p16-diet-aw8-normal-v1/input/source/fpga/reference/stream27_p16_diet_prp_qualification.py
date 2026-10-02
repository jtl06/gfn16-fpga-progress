"""Own eight valid-base AW5/P16 diet PRPs; ordinary N32 integer reference.

Frozen P8 helpers are a mechanical harness donor only. No P8 numeric result,
calendar, base limit or clock is inherited. FullN fitted RTL remains unchanged.
All actual RTL execution belongs to the existing Linux native queue.
"""
import argparse
import hashlib
import json
from pathlib import Path
from . import core27_small_gfn_prp_v1 as oracle
from . import stream27_p8_canonpipe_qualification as donor
from . import stream27_host_chain_diet_qualification as compiler
from . import stream27_host_chain_param_v3 as calendar
from . import stream27_host_chain_model_v1 as integers

ROOT=donor.ROOT
SELF='reference/stream27_p16_diet_prp_qualification.py'
TEST='tests/test_stream27_p16_diet_prp_qualification.py'
CPP='rtl/tb/stream27_p16_diet_prp_v1.cpp'
FAULT='rtl/tb/stream27_p16_diet_faults_v1.cpp'
AW8='rtl/tb/stream27_p16_diet_aw8_normal_v1.cpp'
HELPER='rtl/tb/stream27_p16_diet_prp_helpers_v1.h'
SCALAR='rtl/tb/stream27_p16_diet_prp_scalar_v1.cpp'
CONFIG='rtl/tb/stream27_p16_diet_prp_config_v1.h'
ASSET='assets/p16-diet-eight-prp-v1.txt'
AW8_ASSET='assets/p16-diet-aw8-dense-v1.txt'
COMPILER_SHA='dca6b8aeb63bf799040c91fcfe541b447c41c75de8b9991cbca2b15a591f422d'
SPEC=((300,'composite',1217),(301,'composite',2),(448,'prime',3),(7552,'prime',3),
      (989233152,'prime',5),(999999998,'composite',1409),
      (999999999,'composite',2),(1000000000,'composite',193))


def need(ok,why):
    if not ok:raise ValueError('P16 diet PRP: '+why)


def sha(data):return hashlib.sha256(data).hexdigest()


def corpus(geometry):
    need((geometry['first_digit'],geometry['warm_interval'],geometry['carry_done'],geometry['feedback_delay'])
         ==(156,161,161,4),'actual supported N32/P16 correction/feedback calendar')
    cases=[];lines=['5 8'];stdout=[]
    for index,(base,label,witness) in enumerate(SPEC):
        need(300<=base<=1000000000,'own P16 base floor')
        proof=oracle.prove_label(base,label,witness)
        exponent=base**32;bits=[int(v) for v in bin(exponent)[2:]]
        value=pow(2,exponent,exponent+1);sequential=1
        for bit in bits:sequential=sequential*sequential*(1<<bit)%(exponent+1)
        need(value==sequential and (label!='prime' or value==1),'independent pow/MSB chain/proved label')
        digits=oracle.encode(value,base);need(oracle.decode(digits,base)==value,'all32 canonical words')
        cycles=calendar.cycle_contract(32,geometry,count=len(bits),special=digits[0]==-1,
                                      canonical_pipe_stages=1)['host_done']
        cases.append(dict(index=index,base=base,label=label,proof=proof,operations=len(bits),
                          doubles=sum(bits),bits=bits,expected=digits,residue_hex=hex(value),cycles=cycles))
        lines += [f'{base} {len(bits)}',' '.join(map(str,bits)),' '.join(map(str,digits))]
        stdout.append(f'P16_PRP_CASE index={index} base={base} operations={len(bits)} cycles={cycles} prp={int(value==1)} reads=32')
    operations=sum(case['operations'] for case in cases);total=sum(case['cycles'] for case in cases)
    stdout.append(f'P16_PRP_PASS cases=8 operations={operations} descriptors={operations-8} rows=16 reads=256 cycles={total} base_floor=300')
    meta=dict(base_floor=300,cases=cases,operations=operations,host_cycles=total,reads=256,
        oracle='ordinary builtin pow(2,b**32,b**32+1), independent MSB square/double integer chain',
        scope='Own eight complete N32/P16 diet PRPs; persistent DUT, one initial x0=1 load per job, no mid-PRP reset/reload/barrier, actual T5b and all signed96 words. Not fullN PRP/clock.')
    return '\n'.join(lines)+'\n',meta,'\n'.join(stdout)+'\n'


def aw8_program(geometry):
    need((geometry['first_digit'],geometry['warm_interval'],geometry['carry_done'],geometry['feedback_delay'])
         ==(193,212,212,18),'actual supported N256/P16 correction/18-row feedback calendar')
    n=256;base=1000000000;state=0x9135ba27;initial=[]
    for _ in range(n):
        state^=(state<<13)&0xffffffff;state^=state>>17;state^=(state<<5)&0xffffffff
        initial.append(state%base)
    initial[3]=initial[-1]=-1
    bits=list(integers.program(n,'paired')['bits']);need(len(bits)==256,'finite AW8 normal operations')
    modulus=base**n+1;x=sum(v*base**i for i,v in enumerate(initial))%modulus
    accumulated=0;chained=x
    for bit in bits:
        accumulated=(accumulated<<1)|bit;chained=chained*chained*(1<<bit)%modulus
    independent=pow(x,1<<len(bits),modulus)*pow(2,accumulated,modulus)%modulus
    need(chained==independent,'independent closed-form pow/dense signed chain')
    expected=list(integers.image(independent,base,n))
    cycles=calendar.cycle_contract(n,geometry,count=len(bits),special=expected[0]==-1,
                                  canonical_pipe_stages=1)['host_done']
    text='\n'.join(('8 1',f'{base} {len(bits)}',' '.join(map(str,initial)),
                    ' '.join(map(str,bits)),' '.join(map(str,expected))))+'\n'
    meta=dict(aw=8,n=n,p=16,base=base,operations=len(bits),doubles=sum(bits),initial=initial,
        bits=bits,expected=expected,candidate_cycles=cycles,
        oracle='N256 ordinary closed-form modular pow vs independent sequential square/double',
        scope='Own dense signed N256/P16 diet normal with18 counted feedback rows, actual T5b/all256 signed96 reads; not fullN PRP/clock.')
    return text,meta,f'P16_DIET_AW8_NORMAL_PASS operations=256 descriptors=255 rows=16 reads=256 cycles={cycles} feedback_rows=18\n'


def role(mode='normal'):
    need(mode in ('normal','faults','aw8'),'separate normal/fault/AW8 role')
    need(sha((ROOT/compiler.SELF).read_bytes())==COMPILER_SHA,'frozen supported-small compiler')
    m,files=donor.role('normal')
    n=256 if mode=='aw8' else 32;aw=n.bit_length()-1
    b=compiler.prepare(n,16,paired=True,contexts=1,allow_full_constants=True,
        canonical_pipe_stages=1,corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
    need(len(b['rtl_sources'])==69 and b['parameters']==dict(AW=aw,P=16,CONTEXTS=1,
        CANONICAL_PIPE_STAGES=1,CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1),
        'own diet69 small source and exact flags')
    for name in m['build']['sv_sources']:files.pop(name)
    for name,text in b['files'].items():files['rtl/'+name]=text.encode()
    helper=donor.replace_once(files[donor.HELPER].decode(),
        '#include "stream27_p8_canonpipe_scalar_v1.cpp"','#include "stream27_p16_diet_prp_scalar_v1.cpp"')
    scalar=donor.replace_once(files[donor.SCALAR].decode(),
        '#include "stream27_p8_canonpipe_config_v1.h"','#include "stream27_p16_diet_prp_config_v1.h"')
    old_top=m['build']['top'];config=files[donor.CONFIG].decode()
    need(config.count(old_top)==2,'old include/typedef anchors')
    config=config.replace(old_top,b['top'])
    minimum=599 if mode=='aw8' else 300;g=b['geometry']
    config=donor.replace_once(config,'AW=5,N=32',f'AW={aw},N={n}')
    config=donor.replace_once(config,'MIN_BASE=172,INTERVAL=127,CARRY_DONE=129',
        f'MIN_BASE={minimum},INTERVAL={g["warm_interval"]},CARRY_DONE={g["carry_done"]}')
    config=donor.replace_once(config,'FIRST_DIGIT=122',f'FIRST_DIGIT={g["first_digit"]}')
    config=donor.replace_once(config,'constexpr unsigned P=8;','constexpr unsigned P=16;')
    config=config.replace('P8','P16')
    files[HELPER]=helper.encode();files[SCALAR]=scalar.encode();files[CONFIG]=config.encode()
    driver=AW8 if mode=='aw8' else CPP if mode=='normal' else FAULT
    for name in (SELF,TEST,driver):files[name]=(ROOT/name).read_bytes()
    for name,pin in b['source_sha256'].items():
        raw=(ROOT/name).read_bytes();need(sha(raw)==pin,'source lineage '+name)
        files['p16-diet-lineage/'+name]=raw
    if mode=='aw8':
        text,meta,expected=aw8_program(b['geometry']);files[AW8_ASSET]=text.encode()
        files['p16-diet-lineage/reference/stream27_host_chain_model_v1.py']=(ROOT/'reference/stream27_host_chain_model_v1.py').read_bytes()
    else:text,meta,expected=corpus(b['geometry']);files[ASSET]=text.encode()
    files['assets/p16-diet-eight-prp-oracle-v1.json']=(json.dumps(meta,indent=2)+'\n').encode()
    m['build'].update(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],
        cpp_source=driver,parameters=dict(b['parameters'],EPOCH_SEED=65534))
    if mode in ('normal','aw8'):
        m['steps']=[dict(name='p16-diet-aw8-dense-normal' if mode=='aw8' else 'p16-diet-eight-prp-normal',
            argv=['{exe}','{root}/'+(AW8_ASSET if mode=='aw8' else ASSET)],
            expected_returncode=0,expected_stdout=expected,expected_stderr='')]
    else:
        m['steps']=[dict(name='p16-diet-whole-host-controls-and-special',argv=['{exe}'],expected_returncode=0,
            expected_stdout='P16_DIET_FAULT_PASS descriptor_codes=1,2,3,4 reset_ages=10,271 quarantine_checks=20 recovery_words=224 special_signed96_words=32 canonical_special_cycles=320\n',expected_stderr=''),
            dict(name='p16-diet-special-oracle-negative',argv=['{exe}','--negative-oracle'],expected_returncode=1,
            expected_stdout='',expected_stderr='S4_LONG_POW_TYPED address=0 expected=0 actual=-1\n')]
    m.pop('p8_prp_qualification');m.pop('canonical_qualification')
    m['p16_diet_prp_qualification']=dict(meta,geometry=b['geometry'],source_sha256=b['source_sha256'],
        generated_sha256=b['generated_sha256'],small_compiler_sha256=COMPILER_SHA,
        original_fitted_fullN_unchanged=True,old_native_results_not_inherited=True,
        fullN_integer_arithmetic_locally_performed=False,promotion_allowed=False)
    if mode=='faults':
        m.pop('p16_diet_prp_qualification')
        m['p16_diet_whole_host_faults']=dict(geometry=b['geometry'],source_sha256=b['source_sha256'],
            generated_sha256=b['generated_sha256'],descriptor_codes=[1,2,3,4],reset_ages=[10,271],
            reference='x0=b**16, square→b**32≡−1 (mod b**32+1); full signed96 T5b comparison',
            special_cycles=10*32,oracle_negative_after_correct_candidate=True,
            old_native_results_not_inherited=True,promotion_allowed=False)
    if mode=='aw8':m['p16_diet_aw8_qualification']=m.pop('p16_diet_prp_qualification')
    m['sources']={name:sha(data) for name,data in files.items()}
    return m,files


def prepare(output,mode='normal'):
    output=Path(output).resolve()
    need(not output.exists() and not any((ROOT/name).exists() for name in ('queue/PAUSE','docs/briefs/PAUSE')),
         'fresh source output/no PAUSE')
    m,files=role(mode);source=output/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    m['source_root']=str(source);manifest=output/'manifest.json'
    manifest.write_text(json.dumps(m,indent=2)+'\n')
    result=dict(status='source_prepared_not_native',mode=mode,manifest_sha256=sha(manifest.read_bytes()),
        base_floor=599 if mode=='aw8' else 300,promotion_allowed=False)
    if mode=='normal':result.update(operations=m['p16_diet_prp_qualification']['operations'],cycles=m['p16_diet_prp_qualification']['host_cycles'])
    if mode=='aw8':result.update(operations=m['p16_diet_aw8_qualification']['operations'],cycles=m['p16_diet_aw8_qualification']['candidate_cycles'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('normal','faults','aw8'),default='normal')
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.mode),indent=2))
