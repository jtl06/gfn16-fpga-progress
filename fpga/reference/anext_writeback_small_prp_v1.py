"""A-next AW5 full PRPs on the proven P16 base domain; ordinary integer oracle."""
import hashlib,json,re
from fpga.reference.core27_small_gfn_prp_v1 import prove_label,encode,decode,need,RESULT,FOOTER,MISMATCH
SPEC=((301,'composite',2),(300,'composite',1217),(448,'prime',3),(7552,'prime',3),
      (989233152,'prime',5),(999999998,'composite',1409),(999999999,'composite',2),(1000000000,'composite',193))

def corpus():
    lines=['GFNPRP1 5 8'];cases=[]
    for index,(base,label,witness) in enumerate(SPEC):
        need(base>=300,'A-next proof floor');proof=prove_label(base,label,witness)
        exponent=base**32;bits=bin(exponent)[2:];residue=pow(2,exponent,exponent+1)
        digits=encode(residue,base);need(decode(digits,base)==residue,'ordinary radix roundtrip')
        lines += [f'CASE {index} {base} {label} {len(bits)} {bits.count("1")} {bits}',' '.join(map(str,digits))]
        cases.append(dict(index=index,base=base,classification=label,certificate=proof,exponent_bits=bits,operations=len(bits),doubles=bits.count('1'),expected_digits=digits,expected_residue_hex=hex(residue)))
    text='\n'.join(lines)+'\n'
    return text,dict(schema='anext-small-prp-aw5-v1',aw=5,n=32,base_floor=300,cases=cases,operations=sum(c['operations'] for c in cases),doubles=sum(c['doubles'] for c in cases),corpus_sha256=hashlib.sha256(text.encode()).hexdigest(),oracle='ordinary builtin pow plus independent Proth certificates/proper factors; no RNS/NTT oracle',changed_from_T5b='First four cases replaced because frozen69/70/96/112 violate A4 P16 AW5 minimum300; original corpus preserved.')

def validate(stdout_text,stderr_text,returncode_int,config_dict,assets_text_map):
    need(set(config_dict)=={'mode'},'exact PRP configuration');mode=config_dict['mode']
    need(mode in ('normal','negative-comparator','negative-schedule'),'finite PRP mode')
    text,oracle=corpus();need(set(assets_text_map)=={'corpus','oracle'} and assets_text_map['corpus']==text and json.loads(assets_text_map['oracle'])==oracle,'closed ordinary oracle assets')
    need(type(returncode_int) is int and returncode_int==(0 if mode=='normal' else 1),'exact native exit')
    need(stderr_text==('' if mode=='normal' else MISMATCH),'typed native error')
    lines=stdout_text.splitlines();need(stdout_text.endswith('\n') and len(lines)==(9 if mode=='normal' else 1),'exact result extent')
    rows=[]
    for line,c in zip(lines[:8 if mode=='normal' else 1],oracle['cases']):
        m=RESULT.fullmatch(line);need(m is not None,'result grammar')
        index,base,label,steps,doubles,cycles,cold,warm,prefill,roots,prp,raw=m.groups()
        delta=1 if mode=='negative-schedule' else 0
        need((int(index),int(base),label,int(steps),int(doubles))==(c['index'],c['base'],c['classification'],c['operations'],c['doubles']-delta),'exact exponent schedule identity')
        exponent=c['base']**32-(1 if mode=='negative-schedule' else 0);value=pow(2,exponent,c['base']**32+1);digits=list(map(int,raw.split(',')))
        need(digits==encode(value,c['base']) and decode(digits,c['base'])==value,'final independent PRP residue')
        need(int(prp)==int(value==1) and (label!='prime' or value==1),'proved classification')
        wanted=218+(c['operations']-1)*195
        need((int(cycles),int(cold),int(warm),int(prefill),int(roots))==(wanted,1,c['operations']-1,12,9),'exact A-next backend phase accounting')
        rows.append(dict(index=int(index),cycles=int(cycles),operations=int(steps),doubles=int(doubles),prefill=int(prefill),roots=int(roots)))
    if mode=='normal':
        m=FOOTER.fullmatch(lines[-1]);need(m is not None,'footer grammar')
        need(tuple(map(int,m.groups()))==(8,oracle['operations'],oracle['doubles'],8,sum(x['cycles'] for x in rows),8,oracle['operations']-8,96,72),'complete eight-case accounting')
    else:need(digits[0]!=oracle['cases'][0]['expected_digits'][0] if mode=='negative-schedule' else digits==oracle['cases'][0]['expected_digits'],'matched negative sensitivity')
    return dict(status='PASS_expected_contracts',candidate='A-next-writeback-v1',mode=mode,cases=rows,promotion_allowed=False,scope='New AW5 base-valid eight-case fullPRP profile with host-only comparator/schedule negatives; no RTL-mutant/soak/clock claim.')
