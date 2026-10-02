"""Small exact post-NTT corpus: true CRT residues in, redundant prefill out."""
import hashlib
import random
from fpga.reference.track_a4_blockcarry_model import arithmetic,bounds


def corpus(aw):
    if aw not in (5,8):raise ValueError("post-NTT local numeric preparation AW5/AW8 only")
    n,t=1<<aw,(1<<aw)//16
    rng=random.Random(0xA4F020261001+aw)
    cases=[]
    for base in (arithmetic.minimum_base(n,16),10**9):
        bound=bounds(n,base)["doubled_coefficient_bound"]
        for double in (0,1):
            peak=bound//(1<<double)
            patterns=[[0]*n,[peak]*n,[-peak]*n,[peak if i%2 else -peak for i in range(n)],
                      [rng.randrange(-peak,peak+1) for _ in range(n)]]
            for coefficients in patterns:
                result,stats=arithmetic.proposal.carry_split([x<<double for x in coefficients],base,16)
                serial,_=arithmetic.proposal.carry_serial([x<<double for x in coefficients],base,16)
                assert result==serial
                modulus=base**n+1
                assert sum(v*base**i for i,v in enumerate(result.effective()))%modulus==sum((v<<double)*base**i for i,v in enumerate(coefficients))%modulus
                cases.append((base,double,bound,(1<<96)//base,coefficients,result))
    lines=[f"A4POST1 {aw} {len(cases)}"]
    for base,double,bound,reciprocal,coefficients,result in cases:
        lines.append(f"{base} {double} {t+58} {bound:024x} {reciprocal:024x}")
        for p,_ in arithmetic.core.FIELDS:lines.append(" ".join(str(v%p) for v in coefficients))
        lines.append(" ".join(str(v&((1<<33)-1)) for v in result.effective()))
        for p,_ in arithmetic.core.FIELDS:lines.append(" ".join(str(v%p) for v in result.effective()))
        lines.append(" ".join(str(v&0xffffffff) for v in result.c0))
        lines.append(" ".join(str(v&0xffffffff) for v in result.c1))
        lines.append(" ".join(str(result.digits[k*t]) for k in range(16)))
        lines.append(" ".join(str(result.digits[k*t+1]) for k in range(16)))
    text="\n".join(lines)+"\n"
    return text,dict(aw=aw,cases=len(cases),post_clocks=t+58,field_words=len(cases)*3*n,image_words=len(cases)*n,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),scope="CRT/carry/prefill/patch normal cases, NTT excluded")
