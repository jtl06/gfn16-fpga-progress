"""Genuine small dependent whole-integer programs for the future real host ABI.

N<=256 only. Python integers supply independent GFN residues/canonical words.
No RTL, NTT, host controller, throughput or full-size qualification is claimed.
"""
import argparse,json
from pathlib import Path

def canonical_words(value,base,n):
    modulus=base**n+1;value%=modulus
    if value==modulus-1:return [-1]+[0]*(n-1)
    words=[]
    for _ in range(n):words.append(value%base);value//=base
    assert value==0
    return words
def expand(digits,c0,c1,base,p):
    rows=len(digits)//p;words=list(digits)
    for block in range(p):words[block*rows]+=c0[block];words[block*rows+1]+=c1[block]
    return sum(word*base**i for i,word in enumerate(words))%(base**len(digits)+1)
def programs(n=32,p=8,kind='sentinel',counts=(3,5)):
    assert n in (32,256) and p in (8,16) and kind in ('sentinel','dense')
    assert len(counts)==2 and all(type(count) is int and 1<=count<=32 for count in counts)
    assert kind!='sentinel' or all((1<<count)<=n for count in counts)
    rows=n//p;contexts=[]
    for ctx,count in enumerate(counts):
        base=(1009,2017)[ctx];c0=[-(ctx+1) for _ in range(p)];c1=[-(2-ctx) for _ in range(p)]
        if kind=='sentinel':
            digits=[0]*n;digits[n//(1<<count)]=1
        else:digits=[(i*i+17*i+31+ctx*97)%base for i in range(n)]
        for block in range(p):digits[block*rows]-=c0[block];digits[block*rows+1]-=c1[block]
        assert all(0<=word<base for word in digits)
        initial=expand(digits,c0,c1,base,p);value=initial;steps=[];modulus=base**n+1
        for ordinal in range(count):
            previous=value;value=pow(value,2,modulus)
            steps.append(dict(ordinal=ordinal,input_residue_hex=hex(previous),output_residue_hex=hex(value),
                canonical_signed32=canonical_words(value,base,n)))
        if kind=='sentinel':assert steps[-1]['canonical_signed32']==[-1]+[0]*(n-1)
        contexts.append(dict(context=ctx,base=base,generation=(11,23)[ctx],initial_epoch=(65534,42)[ctx],
            frame_count=count,initial_digits=digits,initial_c0=c0,initial_c1=c1,initial_residue_hex=hex(initial),
            modulus_hex=hex(modulus),dependent_steps=steps,final_owner=dict(generation=(11,23)[ctx],
                epoch=((65534,42)[ctx]+count-1)&65535,ordinal=count-1)))
    return dict(schema='s4-two-context-small-whole-programs-v1',n=n,p=p,kind=kind,contexts=contexts,
        integration_contract=f'Actual host/controller feedback must produce each next frame; do not inject the expected independent digit images. Initial c0/c1 application is an explicit pending host-ABI hook. A stops after{counts[0]} while B continues to{counts[1]}; snapshot A during B activity/finalization and verify both signed32/signed96 host images and full final owners.',
        status='independent_small_integer_vectors_NOT_RTL_qualified',full_N_numeric_locally_performed=False,dispatch_allowed=False)
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--output',type=Path,required=True);a=q.parse_args();assert not a.output.exists()
    result={kind:programs(kind=kind) for kind in ('sentinel','dense')}
    with a.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(a.output)
