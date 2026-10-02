"""Whole-integer proof checks for the27x24 reciprocal-product partition."""
from pathlib import Path
import argparse, hashlib, json, random, socket

def tiled_product(m,c,width):
    """Assert every register-width bound before comparing with Python m*c."""
    rows=[]
    for offset in range(0,width,27):
        w=min(27,width-offset);digit=(m>>offset)&((1<<w)-1)
        partial=[digit*((c>>(24*j))&((1<<24)-1)) for j in range(4)]
        assert all(0<=v<1<<(w+24) for v in partial)
        low=partial[0]+(partial[1]<<24);high=partial[2]+(partial[3]<<24)
        assert low<1<<(w+48) and high<1<<(w+48)
        row=low+(high<<48);assert row<1<<(w+96)
        assert row==digit*c
        rows.append(row)
    row01=rows[0]+(rows[1]<<27)
    assert row01<1<<(min(width,54)+96)
    full=row01+(rows[2]<<54 if len(rows)==3 else 0)
    assert full<1<<(width+96) and full==m*c
    return full

def edges(bits):
    maximum=(1<<bits)-1;values={0,1,maximum}
    for k in (1,23,24,26,27,47,48,53,54,71,72,76,77,95):
        values.update((1<<k)+d for d in (-1,0,1) if 0<=(1<<k)+d<=maximum)
    return sorted(values)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    a.output.mkdir(parents=True,exist_ok=False);root=Path(__file__).resolve().parents[1]
    rng=random.Random(0x272496);counts={};division=0;equivalent=0
    assert (1<<47)*(1+((1<<24)-1)*(1<<23))<1<<96
    for width in (77,47):
        count=0
        for m in edges(width):
            for c in edges(96):tiled_product(m,c,width);count+=1
        for _ in range(20000):
            m=rng.randrange(1<<width);c=rng.randrange(1<<96)
            tiled_product(m,c,width);count+=1
        for _ in range(20000):
            b=rng.randrange(2,1000000001);m=rng.randrange(1<<width)
            c=(1<<96)//b;e=tiled_product(m,c,width)>>96
            q,r=divmod(m,b);delta=m-b*e
            assert e in (q-1,q) and 0<=delta<2*b<1<<31
            assert ((m&0xffffffff)-((e&0xffffffff)*b&0xffffffff))&0xffffffff==delta
            corrected_q=e+(delta>=b);corrected_r=delta-b if delta>=b else delta
            assert (corrected_q,corrected_r)==(q,r)
            assert (-corrected_q-(corrected_r!=0),b-corrected_r if corrected_r else 0)==divmod(-m,b)
            if width==47:
                # The initial low-pair mutation is an equivalent divider:
                # its extra estimate deficit is <1/4, repaired by correction.
                altered=c-(((c>>24)&((1<<24)-1))<<23)
                altered_e=(m*altered)>>96;altered_r=m-altered_e*b
                assert altered_e in (q-1,q) and 0<=altered_r<2*b
                assert (altered_e+(altered_r>=b),altered_r%b)==(q,r)
                equivalent+=1
            division+=2
        counts[str(width)]=count
    files=[Path(__file__),root/'rtl/kernel/genefer_div_recip_dsp27.sv',root/'rtl/kernel/genefer_carry_prefix_stream_dsp27.sv']
    report={'status':'passed','host':socket.gethostname(),'arbitrary_product_checks':counts,
            'signed_division_checks':division,
            'equivalent_low_pair_checks':equivalent,
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
