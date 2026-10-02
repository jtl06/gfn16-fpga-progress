"""Memory-backed RTL transforms and mutation tests. Execute on aethia only.

The integer DIF oracle below is independent of RTL's DIT schedule and uses
ordinary modular arithmetic, not the RTL Montgomery reduction algorithm.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import random
import shutil
import subprocess
import time
from pathlib import Path

from .rns_reference import GENEFER_SIGNED_PRIMES, RADIX, naive_ntt, centered_crt
from .gfn_reference import canonical_unbalanced_digits, decode_digits, square_dup_oracle
from .rtl_vectors import write_vectors


def dif(values: list[int], p: int, generator: int, inverse: bool = False) -> list[int]:
    n = len(values)
    root = pow(generator, (p-1)//n, p)
    if inverse: root = pow(root, -1, p)
    a = [v % p for v in values]
    width = n
    while width > 1:
        half = width//2
        step = pow(root, n//width, p)
        for start in range(0, n, width):
            w = 1
            for j in range(half):
                u, v = a[start+j], a[start+j+half]
                a[start+j] = (u+v) % p
                a[start+j+half] = (u-v)*w % p
                w = w*step % p
        width //= 2
    lg = n.bit_length()-1
    result = [a[int(f"{i:0{lg}b}"[::-1], 2)] for i in range(n)]
    if inverse:
        inv = pow(n, -1, p)
        result = [v*inv % p for v in result]
    return result


class Lab:
    def __init__(self, output: Path, verilator: str):
        self.root = Path(__file__).resolve().parents[1]
        self.output = output.resolve(); self.output.mkdir(parents=True, exist_ok=True)
        self.verilator = verilator
        self.report = {"host": platform.node(), "status": "running", "steps": [],
                       "source_sha256": {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(self.root.rglob("*")) if p.is_file()
                           and p.suffix in (".sv", ".cpp", ".py")
                           and not {"artifacts", "results", "__pycache__"}.intersection(p.parts)}}

    def run(self, name: str, command: list[str], reject: str | None = None) -> str:
        then = time.monotonic()
        proc = subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try: stdout, _ = proc.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, _ = proc.communicate()
            (self.output/f"{name}.log").write_text(stdout)
            raise RuntimeError(f"timeout: {name}")
        (self.output/f"{name}.log").write_text(stdout)
        passed = proc.returncode == 0 if reject is None else proc.returncode == 1 and reject in stdout
        self.report["steps"].append({"name": name, "command": command, "returncode": proc.returncode,
                                     "passed": passed, "seconds": time.monotonic()-then, "reject": reject})
        print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)
        if not passed: raise RuntimeError(f"{name}: {stdout[-2500:]}")
        return stdout

    def build(self, name: str, top: str, sources: list[Path], cpp: Path, params: list[str] | None = None) -> str:
        directory = self.output/name
        self.run(name, [self.verilator, "--cc", "--exe", "--build", "-j", "2",
                       "--top-module", top, "--Mdir", str(directory), *(params or []),
                       *map(str, sources), str(cpp)])
        return str(directory/f"V{top}")

    def mutations(self) -> None:
        kernel = self.root/"rtl/kernel"
        cases = [
            ("arithmetic", "genefer_montgomery_mul32_pipe.sv", "m_s2 <= ab_s1[31:0] * Q;", "m_s2 <= (ab_s1[31:0] * Q) ^ 1;", "value mismatch"),
            ("latency", "genefer_montgomery_mul32_pipe.sv", "out_valid <= valid_pipe[2];", "out_valid <= valid_pipe[1];", "valid/latency mismatch"),
            ("reset", "genefer_montgomery_mul32_pipe.sv", "valid_pipe <= '0;", "valid_pipe <= '1;", "valid/latency mismatch"),
            ("alignment", "genefer_ntt_butterfly32.sv", "u_pipe[3]", "u_pipe[2]", "butterfly value mismatch"),
        ]
        vectors = self.output/"mutation-vectors.txt"; write_vectors(vectors)
        for name, file, old, new, diagnostic in cases:
            directory = self.output/f"mutation-{name}"; directory.mkdir(exist_ok=True)
            for source in kernel.glob("*.sv"): shutil.copy2(source, directory/source.name)
            path = directory/file
            text = path.read_text()
            if old not in text: raise RuntimeError(f"mutation anchor missing: {name}")
            path.write_text(text.replace(old, new))
            sources = [directory/n for n in ("genefer_montgomery_mul32.sv", "genefer_montgomery_mul32_pipe.sv", "genefer_ntt_butterfly32.sv")]
            exe = self.build(f"build-mutation-{name}", "genefer_arithmetic_top",
                             sources+[self.root/"rtl/tb/genefer_arithmetic_top.sv"], self.root/"rtl/tb/arithmetic_stream.cpp")
            self.run(f"reject-mutation-{name}", [exe, str(vectors)], reject=diagnostic)

    def build_ntt(self, field: int) -> str:
        prime = GENEFER_SIGNED_PRIMES[field]
        return self.build(f"build-ntt-p{field+1}", "genefer_ntt_engine",
            [self.root/"rtl/kernel"/n for n in ("genefer_montgomery_mul32_pipe.sv", "genefer_ntt_butterfly32.sv", "genefer_ntt_engine.sv")],
            self.root/"rtl/tb/ntt_engine.cpp", [f"-GP={prime.p}", f"-GQ={prime.q}"])

    def transform_test(self, field: int, lg: int, exe: str) -> None:
        prime = GENEFER_SIGNED_PRIMES[field]; p = prime.p; n = 1<<lg
        r = RADIX % p; root = pow(prime.generator, (p-1)//n, p)
        rng = random.Random(0x4e5454 + field*100 + lg)
        patterns = [[0]*n, [1]+[0]*(n-1), [p-1]*n, [rng.randrange(p) for _ in range(n)]] if lg<=5 else [[rng.randrange(p) for _ in range(n)]]
        lines = [str(lg)]
        def emit(cmd: str, values: list[int]) -> None: lines.append(cmd+"\n"+" ".join(map(str, values)))
        for values in patterns:
            forward = dif(values, p, prime.generator)
            if lg<=5 and forward != naive_ntt(values, prime): raise RuntimeError("DIF disagrees with naive DFT")
            emit("LOAD", [v*r%p for v in values]); emit("ROOTS", [pow(root,i,p)*r%p for i in range(n)])
            if lg>=5:
                lines.append("ABORT 0 0 0")
                emit("LOAD", [v*r%p for v in values]); emit("ROOTS", [pow(root,i,p)*r%p for i in range(n)])
            lines.append("RUN 0 0 0"); emit("CHECK", [v*r%p for v in forward])
            invroot = pow(root,-1,p)
            emit("ROOTS", [pow(invroot,i,p)*r%p for i in range(n)])
            lines.append(f"RUN 0 1 {pow(n,-1,p)*r%p}"); emit("CHECK", [v*r%p for v in values])
        name = f"ntt-p{field+1}-n{n}"; path=self.output/f"{name}.txt"; path.write_text("\n".join(lines)+"\n")
        self.run(name, [exe, str(path), str(self.output/f"{name}-dump.txt")])

    def square_field(self, field: int, digits: list[int], exe: str, name: str, fused: bool = True) -> list[int]:
        prime=GENEFER_SIGNED_PRIMES[field]; p=prime.p; n=len(digits); r=RADIX%p
        psi=pow(prime.generator,(p-1)//(2*n),p); root=psi*psi%p
        lines=[str(n.bit_length()-1)]
        def emit(cmd: str, values: list[int]) -> None: lines.append(cmd+"\n"+" ".join(map(str,values)))
        def powers(root: int) -> list[int]:
            values=[]; w=1
            for _ in range(n): values.append(w); w=w*root%p
            return values
        def roots(values: list[int]) -> None: emit("ROOTS", [v*r%p for v in values])
        def check(values: list[int], mont: bool=True) -> None: emit("CHECK", [v*r%p for v in values] if mont else values)
        a=[v%p for v in digits]; emit("LOAD",[v*r%p for v in a])
        twist=powers(psi); roots(twist); lines.append("RUN 2 0 0")
        a=[v*w%p for v,w in zip(a,twist)]; check(a)
        roots(powers(root)); lines.append("RUN 0 0 0"); a=dif(a,p,prime.generator); check(a)
        lines.append("RUN 1 0 0"); a=[v*v%p for v in a]; check(a)
        untwist=powers(pow(psi,-1,p))
        roots(powers(pow(root,-1,p)))
        if fused:
            # Run inverse roots without the engine's separate normalization pass.
            # One non-Montgomery table combines N^-1, untwist and conversion out
            # of Montgomery: Mont(a*N*R, psi^-i/N) = a*psi^-i.
            lines.append("RUN 0 0 0")
            a=[v*n%p for v in dif(a,p,prime.generator,True)]; check(a)
            inv_n=pow(n,-1,p)
            emit("ROOTS",[w*inv_n%p for w in untwist])
            lines.append("RUN 2 0 0")
            a=[v*w*inv_n%p for v,w in zip(a,untwist)]; check(a,False)
        else:
            lines.append(f"RUN 0 1 {pow(n,-1,p)*r%p}")
            a=dif(a,p,prime.generator,True); check(a)
            roots(untwist); lines.append("RUN 2 0 0")
            a=[v*w%p for v,w in zip(a,untwist)]; check(a)
            lines.append("RUN 3 0 1"); check(a,False)
        lines.append("DUMP")
        path=self.output/f"{name}-p{field+1}.txt"; path.write_text("\n".join(lines)+"\n")
        output=self.output/f"{name}-p{field+1}-residues.txt"
        self.run(f"{name}-p{field+1}",[exe,str(path),str(output)])
        residues=list(map(int,output.read_text().split()))
        if residues!=a: raise RuntimeError("residue dump disagrees with checked RTL outputs")
        return residues

    def build_postprocess(self) -> str:
        return self.build("build-postprocess", "genefer_postprocess_top",
            [self.root/"rtl/kernel/genefer_crt3.sv", self.root/"rtl/kernel/genefer_carry.sv", self.root/"rtl/tb/genefer_postprocess_top.sv"],
            self.root/"rtl/tb/postprocess.cpp")

    def postprocess(self, name: str, exe: str, planes: list[list[int]], coefficients: list[int], base: int, bit: int, expected: list[int]) -> None:
        n=len(coefficients); lines=[f"{n.bit_length()-1} {base} {bit}"]
        bound=1
        for p in GENEFER_SIGNED_PRIMES: bound*=p.p
        if any(abs(c)>bound//2 for c in coefficients): raise ValueError("coefficient outside centered CRT range")
        for i,c in enumerate(coefficients): lines.append(f"{planes[0][i]} {planes[1][i]} {planes[2][i]} {c}")
        lines.extend(map(str,expected)); path=self.output/f"{name}.txt"; path.write_text("\n".join(lines)+"\n")
        self.run(name,[exe,str(path)])

    def carry_cases(self, exe: str) -> None:
        rng=random.Random(9271); basis=1
        for p in GENEFER_SIGNED_PRIMES: basis*=p.p
        cases=[[-1,0], [0,1], [1,-1], [basis//2,-(basis//2)]]
        cases += [[rng.randrange(-basis//2+1,basis//2) for _ in range(n)] for n in (2,8,32)]
        for k,coefficients in enumerate(cases):
            for base in (2,3,1024,604832956,999999937,1000000000):
                bit=k%2
                expected=canonical_unbalanced_digits(decode_digits(coefficients,base)*(2 if bit else 1),base,len(coefficients))
                planes=[[c%p.p for c in coefficients] for p in GENEFER_SIGNED_PRIMES]
                self.postprocess(f"carry-case{k}-b{base}",exe,planes,coefficients,base,bit,expected)
        for base in (2,3,1024,604832956,999999937,1000000000):
            for k,coefficients in enumerate(([-base-1,base-1],[-base,0],[base,-base],[0,0])):
                for bit in (0,1):
                    expected=canonical_unbalanced_digits(decode_digits(coefficients,base)*(2 if bit else 1),base,2)
                    planes=[[c%p.p for c in coefficients] for p in GENEFER_SIGNED_PRIMES]
                    self.postprocess(f"carry-boundary{k}-b{base}-bit{bit}",exe,planes,coefficients,base,bit,expected)

    def engine_mutations(self) -> None:
        cases=[
            ("twiddle", "genefer_ntt_engine.sv", "root_step <= root_step >> 1;", "root_step <= root_step;", "genefer_ntt_engine", "ntt_engine.cpp", "ntt-p1-n32.txt", "NTT mismatch"),
            ("crt-sign", "genefer_crt3.sv", "value > (MODULUS>>1)", "value < (MODULUS>>1)", "genefer_postprocess_top", "postprocess.cpp", "carry-case0-b2.txt", "CRT mismatch"),
            ("carry-floor", "genefer_carry.sv", "quotient-96'sd1", "quotient", "genefer_postprocess_top", "postprocess.cpp", "carry-case0-b2.txt", "carry mismatch"),
        ]
        for name,file,old,new,top,cpp,test,diagnostic in cases:
            directory=self.output/f"mutation-{name}"; directory.mkdir(exist_ok=True)
            for source in (self.root/"rtl/kernel").glob("*.sv"): shutil.copy2(source,directory/source.name)
            path=directory/file; source=path.read_text()
            if source.count(old)!=1: raise RuntimeError("unexpected mutation anchor count")
            path.write_text(source.replace(old,new))
            if top=="genefer_ntt_engine":
                sources=[directory/n for n in ("genefer_montgomery_mul32_pipe.sv","genefer_ntt_butterfly32.sv","genefer_ntt_engine.sv")]
            else: sources=[directory/"genefer_crt3.sv",directory/"genefer_carry.sv",self.root/"rtl/tb/genefer_postprocess_top.sv"]
            exe=self.build(f"build-mutation-{name}",top,sources,self.root/"rtl/tb"/cpp)
            command=[exe,str(self.output/test)]
            if top=="genefer_ntt_engine": command.append(str(directory/"dump.txt"))
            self.run(f"reject-mutation-{name}",command,reject=diagnostic)

    def squares(self, executables: list[str], post: str) -> None:
        rng=random.Random(0x535155415245)
        cases=[("zero",[0]*8,1024), ("minus-one",[-1]+[0]*7,1024),
               ("wrap",[0]*7+[1023],1024), ("max",[999999999]*32,1000000000),
               ("random",[rng.randrange(604832956) for _ in range(32)],604832956),
               ("gfn16",[rng.randrange(604832956) for _ in range(65536)],604832956)]
        for name,digits,base in cases:
            planes=[self.square_field(field,digits,executables[field],f"square-{name}") for field in range(3)]
            if name=="gfn16":
                legacy=[self.square_field(field,digits,executables[field],f"square-{name}-unfused",fused=False) for field in range(3)]
                if legacy!=planes: raise RuntimeError("fused and original modular-square schedules disagree")
            coefficients=[centered_crt((plane[i] for plane in planes), GENEFER_SIGNED_PRIMES) for i in range(len(digits))]
            if len(digits)<=32:
                schoolbook=[0]*len(digits)
                for i,a in enumerate(digits):
                    for j,b in enumerate(digits):
                        k=i+j; schoolbook[k%len(digits)] += a*b if k<len(digits) else -a*b
                if coefficients!=schoolbook: raise RuntimeError("RTL convolution disagrees with schoolbook")
            for bit in (0,1):
                # Independent whole-integer modular square, not CRT/carry code.
                expected=square_dup_oracle(digits,base,bit)
                self.postprocess(f"square-{name}-bit{bit}-post",post,planes,coefficients,base,bit,expected)


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=["all", "mutation", "ntt", "square"], default="all")
    args=parser.parse_args(); lab=Lab(args.output,args.verilator)
    try:
        lab.run("tool-version",[args.verilator,"--version"])
        lab.run("python-tests",["make","verify"])
        if args.phase in ("all", "mutation"): lab.mutations()
        if args.phase in ("all", "ntt", "square"):
            executables=[]
            for field in range(3):
                exe=lab.build_ntt(field)
                executables.append(exe)
                if args.phase in ("all", "ntt"):
                    for lg in (1,3,5,16): lab.transform_test(field,lg,exe)
            if args.phase in ("all", "square"):
                post=lab.build_postprocess(); lab.carry_cases(post); lab.squares(executables,post)
                if args.phase=="all": lab.engine_mutations()
        if args.phase=="all":
            metrics={"n":65536,"units":"simulation clock cycles; not hardware time",
                     "scope":"kernel operations only; host transfers and checks excluded",
                     "fields":{}}
            for field in range(1,4):
                rows=[]
                for line in (lab.output/f"square-gfn16-p{field}.log").read_text().splitlines():
                    if line.startswith("RUN "):
                        rows.append({key:int(value) for key,value in (part.split("=") for part in line.split()[1:])})
                metrics["fields"][str(field)]={"operations":rows,"total_cycles":sum(row["cycles"] for row in rows)}
            metrics["carry"]={str(bit):(lab.output/f"square-gfn16-bit{bit}-post.log").read_text().strip() for bit in (0,1)}
            lab.report["metrics"]=metrics
        lab.report["status"]="pass"
    except Exception as error:
        lab.report["status"]="fail"; lab.report["error"]=str(error); raise
    finally:
        (lab.output/"report.json").write_text(json.dumps(lab.report,indent=2)+"\n")


if __name__=="__main__": main()
