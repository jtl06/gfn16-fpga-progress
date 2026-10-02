"""Aethia-only raw27/raw36/direct/split mapping probe correctness gate."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import socket
import subprocess


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--mutations",action="store_true")
    args=ap.parse_args()
    if socket.gethostname()!="aethia": raise RuntimeError("aethia only")
    root=Path(__file__).resolve().parents[1]
    rtl=root/"rtl/kernel/genefer_raw_mul_probe.sv"
    cpp=root/"rtl/tb/raw_mul_probe.cpp"
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={"status":"running","steps":[],"sources":{
        str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (rtl,cpp,Path(__file__))}}

    def run(name,command,reject=False,assertion=None):
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
        (out/(name+".log")).write_text(result.stdout)
        report["steps"].append({"name":name,"returncode":result.returncode,"expected_rejection":reject})
        print(name,result.returncode,result.stdout[-200:],flush=True)
        markers=(assertion,) if assertion else ("raw valid/latency mismatch","raw multiplication mismatch","raw invalid/reset hold mismatch")
        if reject:
            if result.returncode==0 or not any(m in result.stdout for m in markers):
                raise RuntimeError(name+" failed to detect intended mutation")
        elif result.returncode: raise RuntimeError(name+" failed")

    def build(name,width,split,source):
        directory=out/("build-"+name)
        run("build-"+name,["verilator","--cc","--exe","--build","-j","2",
            "--top-module","genefer_raw_mul_probe","--Mdir",str(directory),
            f"-GWIDTH={width}",f"-GSPLIT18=1'b{split}",str(source),str(cpp)])
        return str(directory/"Vgenefer_raw_mul_probe")

    try:
        for width,split in ((27,0),(36,0),(36,1)):
            name=f"w{width}-s{split}";mask=(1<<width)-1
            edges=sorted({0,1,2,mask,mask-1,*(1<<i for i in range(width)),
                          *((1<<i)-1 for i in range(1,width))})
            pairs=[(a,b) for a in edges for b in edges]
            rng=random.Random(360027+width)
            pairs.extend((rng.randrange(mask+1),rng.randrange(mask+1)) for _ in range(10000))
            vectors=out/(name+".txt")
            vectors.write_text("".join(f"{a} {b} {(a*b)&0xffffffff} {((a*b)>>32)&0xffffffff} {(a*b)>>64}\n" for a,b in pairs))
            report["sources"][vectors.name]=hashlib.sha256(vectors.read_bytes()).hexdigest()
            exe=build(name,width,split,rtl);run("test-"+name,[exe,str(vectors)])
            if width==27:
                for label,a,b in (("lhs",1<<27,1),("rhs",1,(1<<36)-1)):
                    run("reject-input-"+label,[exe,"reject",str(a),str(b)],True,"raw27 input exceeds width")
            if args.mutations:
                defects=[("latency","out_valid<=valid_pipe[1]","out_valid<=valid_pipe[0]"),
                         ("reset","valid_pipe<='0","valid_pipe<='1")]
                if split:
                    defects.append(("cross-shift","{18'b0,lh,18'b0}","{19'b0,lh,17'b0}"))
                else:
                    defects.append(("truncate","ab<=a_s0*b_s0","ab<=(a_s0*b_s0)&72'h3fffffffffffff"))
                    if width==27: defects[-1]=("product-bit","ab<=a_s0*b_s0","ab<=(a_s0*b_s0)^54'd1")
                for label,old,new in defects:
                    source=rtl.read_text();assert source.count(old)==1
                    mutant=out/(name+"-"+label+".sv");mutant.write_text(source.replace(old,new))
                    exe=build(name+"-"+label,width,split,mutant)
                    run("reject-"+name+"-"+label,[exe,str(vectors)],True)
        for name,width,split,message in (("bad-width",35,0,"unsupported raw multiplier width"),
                                         ("bad-split",27,1,"split18 requires WIDTH36")):
            exe=build(name,width,split,rtl)
            run("reject-"+name,[exe,str(vectors)],True,message)
        report["status"]="passed"
    except BaseException as exc:
        report.update(status="failed",error=repr(exc));raise
    finally: (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":main()
