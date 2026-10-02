"""Separate R^2-phase0 root profile; run simulations only on aethia."""
import argparse
import json
from pathlib import Path
from .engine_regression import Lab
from .rns_reference import GENEFER_SIGNED_PRIMES, RADIX


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--mutations",action="store_true")
    args=parser.parse_args()
    assert RADIX == 1 << 32, "operand width never changes the Montgomery radix"
    lab=Lab(args.output,"verilator")
    kernel=lab.root/"rtl/kernel"
    top="genefer_root_stream32_r2"
    original=kernel/f"{top}.sv"
    sources=[kernel/"genefer_montgomery_mul32_pipe.sv",original]
    cpp=lab.root/"rtl/tb/root_stream_r2.cpp"
    lab.report["radix"]=RADIX
    try:
        for field,p in enumerate(GENEFER_SIGNED_PRIMES):
            for aw in (1,2,3,4,16):
                exe=lab.build(f"build-p{field+1}-aw{aw}",top,sources,cpp,
                    [f"-GAW={aw}",f"-GP={p.p}",f"-GQ={p.q}",f"-GGENERATOR={p.generator}"])
                lab.run(f"roots-p{field+1}-aw{aw}",[exe,str(p.p),str(p.generator),str(aw)])
        if args.mutations:
            mutations=[
                ("seed-format","R2=cmul(R,R)","R2=R","root mismatch"),
                ("step-format","cmul(R,cpow(PSI,4))","cmul(R2,cpow(PSI,4))","root mismatch"),
                ("inverse-format","IN=cpow(32'(N),P-2)","IN=cmul(R,cpow(32'(N),P-2))","root mismatch"),
                ("seed-lane","0: seed=S0[index[1:0]]","0: seed=S0[0]","root mismatch"),
                ("phase-latch","phase_reg<=phase","phase_reg<=phase+1'b1","root mismatch"),
                ("done-edge","int'(index)==N-1","int'(index)==N-2","done cycle"),
            ]
            content=original.read_text()
            p=GENEFER_SIGNED_PRIMES[0]
            for name,old,new,diagnostic in mutations:
                if content.count(old)!=1: raise RuntimeError("mutation anchor: "+name)
                directory=lab.output/f"mutation-{name}"
                directory.mkdir()
                modified=directory/original.name
                modified.write_text(content.replace(old,new))
                exe=lab.build(f"mutation-{name}/build",top,[sources[0],modified],cpp,["-GAW=4"])
                lab.run(f"reject-{name}",[exe,str(p.p),str(p.generator),"4"],reject=diagnostic)
        lab.report["status"]="passed"
    except BaseException as error:
        lab.report["status"]="failed";lab.report["error"]=str(error);raise
    finally:
        (lab.output/"report.json").write_text(json.dumps(lab.report,indent=2)+"\n")


if __name__=="__main__":main()
