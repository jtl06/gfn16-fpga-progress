"""Banked II=1 NTT candidate regression; execute on aethia, not the Mac.

Reuse the independent integer-DIF/naive-DFT oracle, not baseline RTL outputs.
Full-size squares are additionally checked against whole-integer modular square.
"""
from __future__ import annotations
import argparse
import json
import platform
import random
import shutil
import subprocess
from pathlib import Path
from .engine_regression import Lab, dif
from .rns_reference import GENEFER_SIGNED_PRIMES, RADIX, centered_crt
from .gfn_reference import decode_digits


class StreamLab(Lab):
    def build_ntt(self, field: int) -> str:
        prime=GENEFER_SIGNED_PRIMES[field]
        return self.build(f"build-stream-p{field+1}","genefer_ntt_stream_engine",
            [self.root/"rtl/kernel"/n for n in ("genefer_montgomery_mul32_pipe.sv", "genefer_ntt_butterfly32.sv", "genefer_ntt_stream_engine.sv")],
            self.root/"rtl/tb/ntt_stream_engine.cpp",[f"-GP={prime.p}",f"-GQ={prime.q}"])

    def reset_and_pointwise(self, field: int, exe: str) -> None:
        p=GENEFER_SIGNED_PRIMES[field].p;r=RADIX%p;n=32;lg=5
        rng=random.Random(123+field);values=[rng.randrange(p) for _ in range(n)]
        prime=GENEFER_SIGNED_PRIMES[field];root=pow(prime.generator,(p-1)//n,p)
        roots=[pow(root,i,p)*r%p for i in range(n)]
        lines=[str(lg)]
        def emit(cmd: str, a: list[int]) -> None: lines.append(cmd+"\n"+" ".join(map(str,a)))
        # Abort during reversal, early/mid/last BF pipe and MUL pipe/drain.
        for op,when in ((0,1),(0,44),(0,47),(0,51),(0,66),(0,151),(1,1),(1,5),(1,33),(2,6),(3,34)):
            emit("LOAD",[v*r%p for v in values]);emit("ROOTS",roots)
            lines.append(f"ABORT_AT {op} 0 {r} {when}")
        for op in (0,1,2,3):
            emit("LOAD",[v*r%p for v in values]);emit("ROOTS",roots)
            lines.append(f"RUN {op} 0 {r if op!=3 else 1}")
            if op==0:expected=[v*r%p for v in dif(values,p,prime.generator)]
            elif op==1:expected=[v*v*r%p for v in values]
            elif op==2:expected=[v*pow(root,i,p)*r%p for i,v in enumerate(values)]
            else:expected=values
            emit("CHECK",expected)
        path=self.output/f"reset-stream-p{field+1}.txt";path.write_text("\n".join(lines)+"\n")
        self.run(f"reset-stream-p{field+1}",[exe,str(path),str(self.output/f"reset-stream-p{field+1}-dump.txt")])

    def square_checks(self, executables: list[str]) -> None:
        rng=random.Random(0x53545245414d)
        cases=[("zero",[0]*8,1024),("minus-one",[-1]+[0]*7,1024),
               ("wrap",[0]*7+[1023],1024),("max",[999999999]*32,1000000000),
               ("random",[rng.randrange(604832956) for _ in range(32)],604832956),
               ("gfn16",[rng.randrange(604832956) for _ in range(65536)],604832956)]
        for name,digits,base in cases:
            planes=[self.square_field(f,digits,executables[f],f"stream-square-{name}") for f in range(3)]
            if name=="gfn16":
                unfused=[self.square_field(f,digits,executables[f],f"stream-square-{name}-unfused",fused=False) for f in range(3)]
                if unfused!=planes:raise RuntimeError("fused/unfused disagreement")
            coefficients=[centered_crt((plane[i] for plane in planes),GENEFER_SIGNED_PRIMES) for i in range(len(digits))]
            if len(digits)<=32:
                schoolbook=[0]*len(digits)
                for i,a in enumerate(digits):
                    for j,b in enumerate(digits):
                        k=i+j;schoolbook[k%len(digits)]+=a*b if k<len(digits) else -a*b
                if coefficients!=schoolbook:raise RuntimeError("schoolbook convolution mismatch")
            modulus=pow(base,len(digits))+1
            got=decode_digits(coefficients,base)%modulus
            expected=pow(decode_digits(digits,base),2,modulus)
            if got!=expected:raise RuntimeError("whole-integer modular square mismatch")
            self.report.setdefault("integer_squares",[]).append({"name":name,"n":len(digits),"base":base,"passed":True})
            print(f"integer-square-{name}: PASS",flush=True)

    def reject_mutants(self) -> None:
        # The first three should be rejected by the independent value oracle;
        # the last deliberately exercises the RAM collision assertion itself.
        cases=[
            ("twiddle", "root_step<=root_step>>1;", "root_step<=root_step;", "NTT mismatch"),
            ("write-tag", "tag_a[5]", "tag_a[4]", None),
            ("bank-order", ".u(read_bank_d?q1a:q0a)", ".u(read_bank_d?q0a:q1a)", "NTT mismatch"),
            ("collision", "addr0b=RW'(((^tag_a[5]) ? tag_b[5] : tag_a[5])>>1);",
             "addr0b=addr0a;", "bank0 mixed-port collision"),
        ]
        for name,old,new,diagnostic in cases:
            directory=self.output/f"mutation-{name}";directory.mkdir(exist_ok=True)
            source=self.root/"rtl/kernel/genefer_ntt_stream_engine.sv"
            text=source.read_text()
            if old not in text:raise RuntimeError("mutation anchor missing")
            path=directory/source.name;path.write_text(text.replace(old,new))
            exe=self.build(f"build-mutation-{name}","genefer_ntt_stream_engine",
                [self.root/"rtl/kernel/genefer_montgomery_mul32_pipe.sv",
                 self.root/"rtl/kernel/genefer_ntt_butterfly32.sv",path],
                self.root/"rtl/tb/ntt_stream_engine.cpp")
            proc=subprocess.run([exe,str(self.output/"ntt-p1-n32.txt"),str(directory/"dump.txt")],
                                cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (self.output/f"reject-mutation-{name}.log").write_text(proc.stdout)
            passed=proc.returncode!=0 and (diagnostic in proc.stdout if diagnostic else
                        ("NTT mismatch" in proc.stdout or "mixed-port collision" in proc.stdout))
            self.report["steps"].append({"name":f"reject-mutation-{name}","passed":passed,
                                         "returncode":proc.returncode,"reject":diagnostic})
            print(f"reject-mutation-{name}: {'PASS' if passed else 'FAIL'}",flush=True)
            if not passed:raise RuntimeError(proc.stdout[-2000:])


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--verilator",default="verilator")
    parser.add_argument("--quick",action="store_true")
    args=parser.parse_args()
    if platform.system()!="Linux":raise RuntimeError("Run this simulation on aethia Linux only")
    lab=StreamLab(args.output,args.verilator)
    try:
        executables=[lab.build_ntt(f) for f in range(1 if args.quick else 3)]
        for f,exe in enumerate(executables):
            for lg in ((1,2,3,5) if args.quick else range(1,17)):lab.transform_test(f,lg,exe)
            lab.reset_and_pointwise(f,exe)
        if not args.quick:
            lab.square_checks(executables)
            lab.reject_mutants()
        lab.report["status"]="passed"
    except Exception:
        lab.report["status"]="failed"
        raise
    finally:(lab.output/"report.json").write_text(json.dumps(lab.report,indent=2)+"\n")


if __name__=="__main__":main()
