"""Standalone A10 queue output validator; all inputs supplied and hash-bound.

No project imports, process execution or source mutation. Numeric bigint replay
is AW5 only. Engine full-N logs validate exact native counters, not numeric NTT.
"""
import json
import re

FIELDS=(104857601,69206017,67239937)
ENGINE=re.compile(r'A10_ENGINE_PASS aw=(5|8|16) field=(\d+) cases=(\d+) operations=(\d+) residues=(\d+) cycles=(\d+) profile_words=4\n')
RESULT=re.compile(r'E2E_RESULT case=(\d+) base=(\d+) class=(prime|composite) steps=(\d+) doubles=(\d+) cycles=(\d+) prp=([01]) digits=(-?\d+(?:,-?\d+){31})')
FOOTER=re.compile(r'E2E_PASS aw=5 cases=(\d+) operations=(\d+) doubles=(\d+) readbacks=(\d+) cycles=(\d+)')

def need(ok,message):
    if not ok:raise ValueError(message)

def engine_metrics(aw):
    need(type(aw) is int and aw in (5,8,16),'A10_ROLE_GEOMETRY')
    n=1<<aw;g=(n+127)//128;trans=aw*(g+9);point=(n+63)//64+7
    return dict(aw=aw,cases=5,operations=15,residues=15*n,cycles=5*(2*trans+point),profile_words=4)

def decode(values,base):
    need(len(values)==32 and (values==[-1]+[0]*31 or all(0<=v<base for v in values)),'A10_E2E_CANONICAL_DIGITS')
    x=0
    for v in reversed(values):x=x*base+v
    return x%(base**32+1)

def prp_case(line,case):
    m=RESULT.fullmatch(line);need(m is not None,'A10_E2E_LINE')
    index,base,classification,steps,doubles,cycles,prp,digits=m.groups()
    index,base,steps,doubles,cycles,prp=map(int,(index,base,steps,doubles,cycles,prp))
    need((index,base,classification,steps,doubles)==(case['index'],case['base'],case['classification'],case['operations'],case['doubles']),
         'A10_E2E_CASE_BINDING')
    need(69<=base<=1000000000 and 0<steps<=957 and 0<cycles<=65536*steps,'A10_E2E_BOUND')
    exponent=base**32;modulus=exponent+1
    need(bin(exponent)[2:]==case['exponent_bits'] and steps==len(case['exponent_bits']) and doubles==case['exponent_bits'].count('1'),
         'A10_E2E_EXPONENT_BINDING')
    expected=pow(2,exponent,modulus);values=list(map(int,digits.split(',')))
    need(values==case['expected_digits'] and decode(values,base)==expected and bool(prp)==(expected==1),'A10_E2E_NUMERIC_RESIDUE')
    certificate=case['certificate']
    if classification=='composite':
        factor=certificate['factor'];need(certificate['kind']=='proper-factor' and 1<factor<modulus and modulus%factor==0,'A10_E2E_FACTOR')
    else:
        need(certificate['kind']=='Proth-proof','A10_E2E_PRIME_CERTIFICATE')
        odd,power=exponent,0
        while odd%2==0:odd//=2;power+=1
        need(odd<1<<power and pow(certificate['witness'],exponent//2,modulus)==modulus-1 and expected==1,'A10_E2E_PROTH')
    return dict(case=index,base=base,classification=classification,operations=steps,doubles=doubles,cycles=cycles,residue_hex=hex(expected))

def validate(stdout,stderr,returncode,config,assets):
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int and type(config) is dict and type(assets) is dict,
         'A10_ROLE_INPUT_TYPES')
    role=config.get('role');negative=config.get('negative')
    if role=='engine':
        need(set(config)=={'role','negative','aw','field'} and type(config['field']) is int and config['field'] in FIELDS
             and not assets,'A10_ROLE_CONFIG')
        expected=engine_metrics(config['aw'])
        if negative is None:
            need(returncode==0 and stderr=='','A10_NATIVE_CONTROL_TERMINAL')
            m=ENGINE.fullmatch(stdout);need(m is not None,'A10_NATIVE_CONTROL_FOOTER')
            aw,field,cases,ops,residues,cycles=map(int,m.groups())
            need((aw,field,cases,ops,residues,cycles)==(config['aw'],config['field'],expected['cases'],expected['operations'],expected['residues'],expected['cycles']),
                 'A10_NATIVE_COUNTER_BINDING')
            return dict(status='bounded_native_engine_log_contract_passed_not_promoted',**expected,field=field,promotion_allowed=False)
        need(negative in ('root','normalization','form') and returncode==1 and stdout=='','A10_NATIVE_TYPED_NEGATIVE_TERMINAL')
        phase='inverse' if negative=='normalization' else 'forward'
        m=re.fullmatch(r'A10_NUMERIC_'+negative.upper()+r'_MISMATCH phase='+phase+r' index=(\d+)\n',stderr)
        need(m is not None and 0<=int(m.group(1))<1<<config['aw'],'A10_NATIVE_TYPED_NEGATIVE_KIND')
        return dict(status='bounded_native_typed_negative_log_contract_passed_not_promoted',kind=negative,phase=phase,
                    index=int(m.group(1)),aw=config['aw'],field=config['field'],promotion_allowed=False)
    need(role=='e2e1' and set(config)=={'role','negative'} and negative in (None,'comparator'),'A10_ROLE_CONFIG')
    need(set(assets)=={'oracle'} and type(assets['oracle']) is str,'A10_E2E_ORACLE_ASSET')
    oracle=json.loads(assets['oracle'])
    need(oracle['schema']=='crtmont-prp-e2e-aw5-v1' and oracle['aw']==5 and oracle['n']==32 and len(oracle['cases'])==8,'A10_E2E_ORACLE_SCOPE')
    lines=stdout.splitlines();need(stdout.endswith('\n'),'A10_E2E_OUTPUT_NEWLINE')
    if negative=='comparator':
        need(returncode==1 and len(lines)==1 and stderr=='E2E_RESIDUE_MISMATCH case=0 digit=0\n','A10_E2E_COMPARATOR_TERMINAL')
        record=prp_case(lines[0],oracle['cases'][0])
        return dict(status='bounded_native_e2e1_comparator_log_contract_passed_not_promoted',case=record,promotion_allowed=False)
    need(returncode==0 and stderr=='' and len(lines)==9,'A10_E2E_CONTROL_TERMINAL')
    records=[prp_case(line,case) for line,case in zip(lines[:8],oracle['cases'])]
    footer=FOOTER.fullmatch(lines[-1]);need(footer is not None,'A10_E2E_FOOTER')
    expected=(8,sum(c['operations'] for c in records),sum(c['doubles'] for c in records),8,sum(c['cycles'] for c in records))
    need(tuple(map(int,footer.groups()))==expected,'A10_E2E_ACCOUNTING')
    return dict(status='bounded_native_e2e1_bigint_log_contract_passed_not_promoted',cases=records,operations=expected[1],doubles=expected[2],
                readbacks=8,cycles=expected[4],promotion_allowed=False)
