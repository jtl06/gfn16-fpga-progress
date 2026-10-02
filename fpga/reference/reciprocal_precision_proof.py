"""Exact W-bit reciprocal proof and boundary checks; execute on aethia only."""
from pathlib import Path
import argparse, hashlib, json, random, socket

def tiled_product(m,c,width):
    rows=[]
    for offset in range(0,width,27):
        lw=min(27,width-offset);digit=m>>offset&((1<<lw)-1);partial=[]
        for roffset in range(0,width,27):
            rw=min(27,width-roffset);v=digit*((c>>roffset)&((1<<rw)-1))
            assert v<1<<(lw+rw);partial.append(v)
        pair=partial[0]+(partial[1]<<27)
        assert pair<1<<(lw+min(width,54))
        row=pair+(partial[2]<<54 if len(partial)==3 else 0)
        assert row<1<<(lw+width) and row==digit*c;rows.append(row)
    row01=rows[0]+(rows[1]<<27)
    assert row01<1<<(min(width,54)+width)
    full=row01+(rows[2]<<54 if len(rows)==3 else 0)
    assert full<1<<(2*width) and full==m*c
    return full

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    a.output.mkdir(parents=True,exist_ok=False);root=Path(__file__).resolve().parents[1]
    rng=random.Random(0x774727);counts={'exhaustive_signed':0,'boundary_signed':0,'random_signed':0,'arbitrary_products':0}
    correction={}
    def check(width,b,m,tile=False):
        assert 0<=m<1<<width and 2<=b<=1000000000
        c=((1<<96)//b)>>(96-width)
        assert c==(1<<width)//b and c<1<<width
        product=tiled_product(m,c,width) if tile else m*c;e=product>>width
        q,r=divmod(m,b);assert e in (q,q-1)
        delta=m-b*e;assert 0<=delta<2*b<1<<31
        low=((m&0xffffffff)-((e&0xffffffff)*b&0xffffffff))&0xffffffff
        assert low==delta
        fixed_q=e+(delta>=b);fixed_r=delta-b if delta>=b else delta
        assert (fixed_q,fixed_r)==(q,r)
        assert (-fixed_q-(fixed_r!=0),b-fixed_r if fixed_r else 0)==divmod(-m,b)
        correction.setdefault(str(width),[0,0])[int(delta>=b)]+=1
    for width in range(1,11):
        for b in range(2,65):
            for m in range(1<<width):check(width,b,m);counts['exhaustive_signed']+=2
    for width in (77,47):
        maximum=(1<<width)-1
        bases=[2,3,4,5,7,9,37,131077,604832956,999999999,1000000000]
        bases += [(1<<k)+d for k in (24,27,29) for d in (-1,0,1)]
        for b in bases:
            values={0,1,b-1,b,b+1,maximum,maximum-1,maximum-b}
            for bit in (1,26,27,46,47,53,54,76):
                values.update((1<<bit)+d for d in (-1,0,1) if 0<=(1<<bit)+d<=maximum)
            for q in (maximum//b,maximum//b-1,maximum//(2*b)):
                values.update(q*b+d for d in (-1,0,1) if 0<=q*b+d<=maximum)
            for m in sorted(values):check(width,b,m,True);counts['boundary_signed']+=2
        for _ in range(50000):
            check(width,rng.randrange(2,1000000001),rng.randrange(1<<width),True);counts['random_signed']+=2
        for _ in range(20000):
            tiled_product(rng.randrange(1<<width),rng.randrange(1<<width),width);counts['arbitrary_products']+=1
        assert all(correction[str(width)])
    files=[Path(__file__)]+[p for p in (root/'rtl/kernel/genefer_div_recip_precision.sv',root/'rtl/kernel/genefer_carry_prefix_stream_precision.sv') if p.exists()]
    report={'status':'passed','host':socket.gethostname(),'checks':counts,'correction_counts':correction,
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
