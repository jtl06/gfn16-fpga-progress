"""Finite P3 point-only AW5/AW8 base-range PRPs; no current-range/prime claim.

Ordinary builtin pow supplies expected residues. A separate MSB-first integer
loop checks the schedule. N is hard-limited to32/256; no full-N oracle, HDL,
vendor tool or cloud launcher is implemented here. The unchanged point RTL and
qualified command bench are reused through a source-pinned additive adapter.
"""
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/anext_point_base_fuzz_v1.py'
TEST = 'tests/test_anext_point_base_fuzz_v1.py'
CPP = 'rtl/tb/anext_point_base_fuzz_v1.cpp'
PARENT_CPP = 'rtl/tb/anext_point_small_prp_v1.cpp'
PARENT_CPP_SHA = '0488e65c703d7ef2c6945a25f8b2f8d59b48f085bc0ec9e46ee1892a80a97f29'
CORE = 'f37123255ed08225f9c26a5d556fafb94c4e3eda9547b28713be956cda4cbe7b'
BLOCK = '076f6dcf120b448f38aff04fcb438e0f43158262ef08fcaa7c07ce8de8c83091'
ROLES = {
    5: ('anext-point-whole-aw5-role-v1', '11340a6819c863139bff8b50564d44a0b5d1df3b2eaa8b154f969a0e42d7aeeb'),
    8: ('anext-point-whole-aw8-role-v1', '5e688cbd1de473b445a216642a6b63d79b3ca676b6821dab317802ef8e29a7ef'),
}
PROFILE = {
    5: dict(n=32, cases=32, floor=300, cold=207, warm=184, prefill=12, roots=9, ntt=115, post=64),
    8: dict(n=256, cases=16, floor=599, cold=314, warm=277, prefill=26, roots=9, ntt=194, post=78),
}
SEED = 20261001
MODES = ('normal', 'negative-comparator', 'negative-schedule')
MISMATCH = 'E2E_RESIDUE_MISMATCH case=0 digit=0\n'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def profile(aw):
    need(type(aw) is int and aw in PROFILE, 'FUZZ_ONLY_AW5_AW8')
    p = PROFILE[aw]
    need(p['n'] <= 256 and p['floor'] == max(2*p['n']+5, (2*(2*p['n']+384)+2)//3+1), 'FUZZ_PROVED_FLOOR')
    return p


def bases(aw):
    """Source-fixed edge cases plus reproducible interior coverage, not mining."""
    p = profile(aw)
    floor = p['floor']
    # The first odd base exposes both matched negative controls at digit0.
    first = floor+3 if floor % 2 == 0 else floor+2
    values = [first]+[value for value in range(floor,floor+6) if value != first]+[
              604832956, 1000000000, 999999999, 999999998, 999999997, 999999996]
    state = (SEED ^ (aw << 24)) & 0xffffffff
    while len(values) < p['cases']:
        state = (1664525*state + 1013904223) & 0xffffffff
        value = floor + state % (1000000000-floor+1)
        if value not in values:
            values.append(value)
    need(len(values) == len(set(values)) == p['cases'] and
         all(floor <= b <= 1000000000 for b in values), 'FUZZ_CLOSED_BASE_SET')
    return tuple(values)


def encode(value, base, n):
    need(n in (32,256) and type(value) is int and 0 <= value < base**n+1, 'FUZZ_SMALL_RESIDUE')
    if value == base**n:
        return [-1]+[0]*(n-1)
    words=[]
    for _ in range(n):
        value, word = divmod(value,base)
        words.append(word)
    need(value == 0, 'FUZZ_DIGIT_OVERFLOW')
    return words


def decode(words, base, n):
    need(n in (32,256) and len(words) == n and all(type(v) is int for v in words), 'FUZZ_DIGIT_EXTENT')
    need(words == [-1]+[0]*(n-1) or all(0 <= v < base for v in words), 'FUZZ_CANONICAL_DIGITS')
    value=0
    for word in reversed(words):
        value=value*base+word
    return value % (base**n+1)


@lru_cache(maxsize=2)
def _corpus(aw):
    p=profile(aw);n=p['n'];cases=[];lines=[f'GFNPRP1 {aw} {p["cases"]}']
    for index,base in enumerate(bases(aw)):
        exponent=base**n;modulus=exponent+1;bits=bin(exponent)[2:]
        residue=pow(2,exponent,modulus)
        chained=1
        for bit in bits:
            chained=(chained*chained*(1 << int(bit))) % modulus
        need(chained == residue, 'FUZZ_INDEPENDENT_SCHEDULE')
        words=encode(residue,base,n)
        need(decode(words,base,n) == residue, 'FUZZ_RADIX_ROUNDTRIP')
        lines.extend((f'CASE {index} {base} unclassified {len(bits)} {bits.count("1")} {bits}',
                      ' '.join(map(str,words))))
        cases.append(dict(index=index,base=base,classification='unclassified',operations=len(bits),
                          doubles=bits.count('1'),exponent_bits=bits,expected_digits=words,
                          expected_residue_hex=hex(residue),expected_prp=residue==1))
    text='\n'.join(lines)+'\n'
    oracle=dict(schema='anext-point-base-fuzz-v1',aw=aw,n=n,seed=SEED,base_floor=p['floor'],base_ceiling=1000000000,
        cases=cases,operations=sum(c['operations'] for c in cases),doubles=sum(c['doubles'] for c in cases),
        corpus_sha256=hashlib.sha256(text.encode()).hexdigest(),
        oracle='builtin pow(2,b**N,b**N+1), checked by separate MSB square/double loop; no RNS/NTT/carry model',
        schedule='x0=1 per case; all exponent bits MSB-first; one reset/base/load then no reads/reloads until finalNword readback',
        coverage='Source-fixed admissible-domain test bases only; no PrimeGrid-current-range or primality claim.')
    first=cases[0];b=first['base'];wrong=encode(pow(2,b**n-1,b**n+1),b,n)
    need(first['exponent_bits'][-1] == '1' and wrong[0] != first['expected_digits'][0], 'FUZZ_MATCHED_SCHEDULE_SENSITIVITY')
    # Cache serialized data, so callers cannot mutate shared oracle objects.
    return text,json.dumps(oracle,sort_keys=True,separators=(',',':'))


def corpus(aw):
    text,raw=_corpus(aw)
    return text,json.loads(raw)


def validate(stdout_text,stderr_text,returncode_int,config_dict,assets_text_map):
    need(type(config_dict) is dict and set(config_dict) == {'aw','mode'}, 'FUZZ_EXACT_CONFIG')
    aw=config_dict['aw'];p=profile(aw);mode=config_dict['mode'];n=p['n']
    need(mode in MODES, 'FUZZ_FINITE_MODE')
    text,oracle=corpus(aw)
    need(type(assets_text_map) is dict and set(assets_text_map) == {'corpus','oracle'} and
         assets_text_map['corpus'] == text and json.loads(assets_text_map['oracle']) == oracle, 'FUZZ_CLOSED_ASSETS')
    need(type(returncode_int) is int and returncode_int == (0 if mode=='normal' else 1), 'FUZZ_NATIVE_EXIT')
    need(stderr_text == ('' if mode=='normal' else MISMATCH), 'FUZZ_TYPED_ERROR')
    lines=stdout_text.splitlines()
    need(stdout_text.endswith('\n') and len(lines) == (p['cases']+1 if mode=='normal' else 1), 'FUZZ_EXACT_EXTENT')
    result=re.compile(r'E2E_RESULT case=(\d+) base=(\d+) class=(unclassified) steps=(\d+) doubles=(\d+) cycles=(\d+) cold=(\d+) warm=(\d+) conversion=(\d+) roots=(\d+) prp=([01]) digits=(-?\d+(?:,-?\d+){'+str(n-1)+r'})')
    rows=[]
    for line,case in zip(lines[:-1] if mode=='normal' else lines,oracle['cases']):
        match=result.fullmatch(line);need(match is not None,'FUZZ_RESULT_GRAMMAR')
        index,base,label,steps,ones,cycles,cold,warm,prefill,roots,prp,raw=match.groups()
        changed=mode=='negative-schedule'
        need((int(index),int(base),label,int(steps),int(ones)) ==
             (case['index'],case['base'],'unclassified',case['operations'],case['doubles']-int(changed)), 'FUZZ_SCHEDULE_IDENTITY')
        exponent=case['base']**n-int(changed)
        expected=pow(2,exponent,case['base']**n+1)
        words=list(map(int,raw.split(',')))
        need(words == encode(expected,case['base'],n) and decode(words,case['base'],n) == expected, 'FUZZ_ORDINARY_RESIDUE')
        need(int(prp) == int(expected==1), 'FUZZ_PRP_RESULT_NOT_CLASSIFICATION')
        wanted=p['cold']+(case['operations']-1)*p['warm']
        need((int(cycles),int(cold),int(warm),int(prefill),int(roots)) ==
             (wanted,1,case['operations']-1,p['prefill'],p['roots']), 'FUZZ_PHASE_ACCOUNTING')
        rows.append(dict(base=case['base'],operations=int(steps),doubles=int(ones),cycles=wanted))
    if mode=='normal':
        expected_footer=f'E2E_PASS aw={aw} cases={p["cases"]} operations={oracle["operations"]} doubles={oracle["doubles"]} readbacks={p["cases"]} cycles={sum(r["cycles"] for r in rows)} cold={p["cases"]} warm={oracle["operations"]-p["cases"]} conversion={p["cases"]*p["prefill"]} roots={p["cases"]*p["roots"]}'
        need(lines[-1] == expected_footer,'FUZZ_COMPLETE_FOOTER')
    else:
        need(words[0] != oracle['cases'][0]['expected_digits'][0] if mode=='negative-schedule'
             else words == oracle['cases'][0]['expected_digits'], 'FUZZ_CONTROL_SENSITIVITY')
    return dict(status='PASS_expected_contracts',candidate='A-next-point-v1',aw=aw,mode=mode,cases=rows,
                operations=sum(r['operations'] for r in rows),promotion_allowed=False,
                scope='Finite AW5/AW8 admissible-domain PRP residue tests; no fullN/PrimeGrid/current-range/prime/clock/continuous-soak claim.')


def once(text,old,new,count=1):
    need(text.count(old) == count, 'FUZZ_EXACT_BENCH_ANCHOR '+old)
    return text.replace(old,new)


def bench():
    need(sha(ROOT/PARENT_CPP) == PARENT_CPP_SHA, 'FUZZ_QUALIFIED_POINT_BENCH')
    text=(ROOT/PARENT_CPP).read_text()
    text=once(text,'#include <vector>','#include <vector>\n#ifndef A4_CORE_AW\n#define A4_CORE_AW 5\n#endif\nstatic constexpr unsigned AW=A4_CORE_AW,N=1u<<AW,CASES=AW==5?32u:16u;\nstatic_assert(AW==5 || AW==8,"FUZZ_ONLY_SMALL_N");\nstatic constexpr unsigned FLOOR=std::max(2*N+5,(2*(2*N+384)+2)/3+1);\nstatic constexpr unsigned COLD=AW==5?207u:314u,WARM=AW==5?184u:277u;\nstatic constexpr unsigned PREFILL=AW==5?12u:26u,NTT=AW==5?115u:194u,POST=AW==5?64u:78u;')
    for old,new,count in (
        ('aw==5 && count==8','aw==AW && count==CASES',1),
        ('base>=300','base>=FLOOR',1),
        ('(label=="prime" || label=="composite")','label=="unclassified"',1),
        ('steps<=957','steps<=30*N+1',1),
        ('expected(32),actual(32)','expected(N),actual(N)',1),
        ('i<32','i<N',5),
        ('k==0?207u:184u','k==0?COLD:WARM',1),
        ('k==0?12u:0u','k==0?PREFILL:0u',1),
        ('d.ntt_cycles==115 && d.post_cycles==64','d.ntt_cycles==NTT && d.post_cycles==POST',1),
        ('need(label!="prime" || prp,"E2E_PROVEN_PRIME_NOT_PRP");','need(label=="unclassified","FUZZ_NO_PRIMALITY_LABEL");',1),
        ('"E2E_PASS aw=5 cases="','"E2E_PASS aw="<<AW<<" cases="',1),
    ):
        text=once(text,old,new,count)
    need(text.count('No intermediate host reads/reloads') == 1,'FUZZ_RETAINED_LOOP')
    return text


def prepare(aw,output):
    from fpga.reference.anext_point_qualification_v1 import closed
    p=profile(aw);output=Path(output).resolve()
    need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'FUZZ_FRESH_NO_PAUSE')
    manifest,files=closed(*ROLES[aw])
    need(files['rtl/kernel/genefer_anext_point_core_v1.sv'] == (ROOT/'rtl/kernel/genefer_anext_point_core_v1.sv').read_bytes(), 'FUZZ_UNCHANGED_POINT_CORE')
    need(hashlib.sha256(files['rtl/kernel/genefer_anext_point_core_v1.sv']).hexdigest()==CORE and
         hashlib.sha256(files['rtl/kernel/genefer_anext_point_block_engine_v1.sv']).hexdigest()==BLOCK,'FUZZ_EXACT_POINT_RTL')
    for name in (SELF,TEST,PARENT_CPP):
        files[name]=(ROOT/name).read_bytes()
    files[CPP]=bench().encode()
    text,oracle=corpus(aw)
    files['vectors/base-fuzz.txt']=text.encode()
    files['vectors/base-fuzz-oracle.json']=(json.dumps(oracle,indent=2)+'\n').encode()
    manifest['build']['cpp_source']=CPP
    manifest['probe']={'argv':['{exe}','--runtime-probe'],'expected_json':{'context_threads':1,'model_threads':1,'expected_threads':1}}
    manifest['steps']=[]
    for mode in MODES:
        argv=['{exe}','{root}/vectors/base-fuzz.txt']+([] if mode=='normal' else ['--'+mode])
        manifest['steps'].append(dict(name=f'point-base-fuzz-aw{aw}-{mode}',argv=argv,
            expected_returncode=0 if mode=='normal' else 1,expected_stderr='' if mode=='normal' else MISMATCH,
            validator=dict(source=SELF,function='validate',config={'aw':aw,'mode':mode},
                           assets={'corpus':'vectors/base-fuzz.txt','oracle':'vectors/base-fuzz-oracle.json'})))
    need(len(manifest['build']['sv_sources'])==30 and manifest['build']['parameters']['AW']==aw,'FUZZ_30_RTL_CLOSED_BUILD')
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    manifest['sources']={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result=dict(status='prepared_source_only_not_native',aw=aw,n=p['n'],cases=p['cases'],
                base_floor=p['floor'],base_ceiling=1000000000,seed=SEED,operations=oracle['operations'],
                steps=len(MODES),source_count=len(files),compiled_sv=30,manifest_sha256=sha(output/'manifest.json'),
                arithmetic_or_RTL_changed=False,promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw',type=int,choices=(5,8),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.aw,args.output),indent=2))
