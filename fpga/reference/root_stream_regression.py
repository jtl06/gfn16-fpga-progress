"""Verify elaborated root streamers on aethia, including reset and all phases."""
import argparse
import json
from pathlib import Path
from .engine_regression import Lab
from .rns_reference import GENEFER_SIGNED_PRIMES


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    lab=Lab(args.output,"verilator")
    try:
        for field,p in enumerate(GENEFER_SIGNED_PRIMES):
            for aw in (1,4,16):
                exe=lab.build(f"build-p{field+1}-aw{aw}","genefer_root_stream32",
                    [lab.root/"rtl/kernel"/s for s in ("genefer_montgomery_mul32_pipe.sv","genefer_root_stream32.sv")],
                    lab.root/"rtl/tb/root_stream.cpp",[f"-GAW={aw}",f"-GP={p.p}",f"-GQ={p.q}",f"-GGENERATOR={p.generator}"])
                lab.run(f"roots-p{field+1}-aw{aw}",[exe,str(p.p),str(p.generator),str(aw)])
        lab.report["status"]="pass"
    except Exception as error:
        lab.report["status"]="fail";lab.report["error"]=str(error);raise
    finally:
        (lab.output/"report.json").write_text(json.dumps(lab.report,indent=2)+"\n")


if __name__=="__main__":main()
