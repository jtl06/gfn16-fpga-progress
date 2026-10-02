"""Check frozen32-bit RTL against the same canonical27-bit vectors/scoreboard."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from .ntt27_experiment import select_basis


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vectors",type=Path,required=True)
    parser.add_argument("--scoreboard",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if platform.node()!="aethia":raise RuntimeError("aethia only")
    root=Path(__file__).resolve().parents[1]
    source=root/"rtl/kernel/genefer_montgomery_mul32_pipe.sv"
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={"status":"running","sources":{str(p):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (source,args.scoreboard,Path(__file__))},"steps":[]}
    def run(name,command):
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
        (out/f"{name}.log").write_text(result.stdout)
        report["steps"].append({"name":name,"command":command,"returncode":result.returncode})
        print(name,result.returncode,result.stdout[-400:],flush=True)
        if result.returncode:raise RuntimeError(name+" failed")
    try:
        for prime in select_basis():
            vectors=args.vectors/f"vectors-{prime.p}.txt"
            report["sources"][str(vectors)]=hashlib.sha256(vectors.read_bytes()).hexdigest()
            build=out/f"build-{prime.p}"
            run(f"build-{prime.p}",["verilator","--cc","--exe","--build","-j","2",
                "--top-module","genefer_montgomery_mul32_pipe","--prefix","Vgenefer_montgomery_mul27_pipe",
                "--Mdir",str(build),f"-GP={prime.p}",f"-GQ={prime.q}",str(source),str(args.scoreboard)])
            run(f"test-{prime.p}",[str(build/"Vgenefer_montgomery_mul27_pipe"),str(vectors),str(prime.p)])
        report["status"]="passed"
    except BaseException as exc:
        report.update(status="failed",error=repr(exc));raise
    finally:(out/"report.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":main()
