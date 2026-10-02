"""Standalone II=1 CRT regression. Run only on aethia, not the user's Mac.

Oracle is a direct CRT basis sum in Python integers, not RTL's Garner ladder.
Both simulators consume the exact same adversarial reset/bubble/value stream.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import random
import shlex
import subprocess

P = (2130706433, 2113929217, 2013265921)
M = P[0]*P[1]*P[2]
BASIS = tuple(M//p * pow(M//p, -1, p) for p in P)


def oracle(residues: tuple[int, int, int]) -> int:
    x = sum(r*b for r, b in zip(residues, BASIS)) % M
    return x-M if x>M//2 else x


def vectors(path: Path, seed: int) -> dict:
    rng = random.Random(seed)
    records = []
    def emit(reset: int, valid: int, rs=None):
        rs = rs or tuple(rng.randrange(p) for p in P)
        x = oracle(rs) % (1 << 96)
        records.append((reset, valid, *rs, *(x >> (32*j) & 0xffffffff for j in range(3))))
    emit(0, 0)
    boundaries = [0, 1, -1, M//2, M//2-1, M//2+1, -(M//2), -(M//2)+1]
    for k in range(94):
        boundaries.extend((2**k-1, 2**k, 2**k+1, -2**k))
    for x in boundaries:
        rs = tuple(x % p for p in P)
        if oracle(rs) != ((x + M//2) % M) - M//2:
            raise AssertionError("independent basis oracle boundary check failed")
        emit(1, 1, rs)
    for rs in itertools.product(*[(0, 1, p//2, p-2, p-1) for p in P]):
        emit(1, 1, rs)
    for r1 in (P[1]-1,P[1],P[1]+1,P[0]-1):
        for r2 in (0,1,P[1]-1):
            for r3 in (0,1,P[2]-1): emit(1,1,(r1,r2,r3))
    # No bubbles: sustained throughput over 10,000 consecutive inputs.
    for _ in range(12000): emit(1,1)
    # Random validity/reset bursts, including repeated resets and partial fills.
    for i in range(40000):
        reset = int(i%997 not in (0,1,3))
        valid = int(rng.random() < 0.72)
        emit(reset, valid)
    for _ in range(65): emit(1,0)
    path.write_text("".join(" ".join(map(str,row))+"\n" for row in records))
    return {"cycles":len(records),"seed":seed,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


IVERILOG_TB = r'''
module crt_stream_tb;
reg clk=0,rst_n=0,in_valid=0;
reg [31:0] r1=0,r2=0,r3=0;
wire ready,out_valid;
wire signed [95:0] coefficient;
genefer_crt3_pipe dut(.*);
reg [95:0] expected[0:60];
reg [60:0] valid_pipe=0;
reg [95:0] held=0;
reg [31:0] lo,mid,hi;
integer file,rc,i,cycle=0,checked=0,rv,iv;
reg [4095:0] filename;
initial begin
    if (!$value$plusargs("vectors=%s",filename)) $fatal(1,"missing vectors");
    file=$fopen(filename,"r");
    if (!file) $fatal(1,"cannot open vectors");
    while (!$feof(file)) begin
        clk=0; #1;
        rc=$fscanf(file,"%d %d %d %d %d %d %d %d\n",rv,iv,r1,r2,r3,lo,mid,hi);
        if (rc==8) begin
            rst_n=rv!=0; in_valid=iv!=0; #1;
            if (!rst_n) begin valid_pipe=0; held=0; end
            else begin
                for (i=60;i>0;i=i-1) expected[i]=expected[i-1];
                expected[0]={hi,mid,lo}; valid_pipe={valid_pipe[59:0],in_valid};
            end
            clk=1; #1;
            if (out_valid !== valid_pipe[60]) $fatal(1,"valid/latency mismatch cycle %0d",cycle);
            if (valid_pipe[60]) begin held=expected[60]; checked=checked+1; end
            if (coefficient !== held) $fatal(1,"value/hold mismatch cycle %0d",cycle);
            if (!ready) $fatal(1,"II=1 ready mismatch");
            cycle=cycle+1;
        end else if (!$feof(file)) $fatal(1,"malformed input");
    end
    if (valid_pipe || checked<10000) $fatal(1,"incomplete input");
    $display("PASS cycles=%0d checked=%0d stages=61 II=1",cycle,checked); $finish;
end
endmodule
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--seed",type=int,default=20260929)
    parser.add_argument("--icarus",action="store_true")
    parser.add_argument("--mutations",action="store_true")
    args=parser.parse_args()
    if platform.system() != "Linux" or platform.node() != "aethia":
        raise SystemExit("Run this regression on aethia only")
    root=Path(__file__).resolve().parents[1]
    out=args.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    src=[root/"rtl/kernel"/name for name in ("genefer_mod64_pipe.sv","genefer_crt3_pipe.sv")]
    cpp=root/"rtl/tb/crt_stream.cpp"
    report={"host":platform.node(),"status":"running","stages":61,"II":1,
            "sources":{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src+[cpp,Path(__file__)]},"steps":[]}
    def run(name,cmd,reject=None):
        proc=subprocess.run(cmd,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=240)
        (out/f"{name}.log").write_text(proc.stdout)
        report["steps"].append({"name":name,"command":cmd,"returncode":proc.returncode,"expected_rejection":reject})
        print(name,proc.returncode,proc.stdout[-400:],flush=True)
        if reject is None:
            if proc.returncode: raise RuntimeError(name+" failed")
        elif proc.returncode != 1 or reject not in proc.stdout:
            raise RuntimeError(name+" did not reject the intentional fault")
    try:
        vfile=out/"vectors.txt"; report["vectors"]=vectors(vfile,args.seed)
        run("verilator-build",["verilator","--cc","--exe","--build","-j","2","--top-module","genefer_crt3_pipe","--Mdir",str(out/"verilator"),*map(str,src),str(cpp)])
        run("verilator-test",[str(out/"verilator/Vgenefer_crt3_pipe"),str(vfile)])
        if args.icarus:
            tb=out/"crt_stream_tb.sv"; tb.write_text(IVERILOG_TB)
            run("icarus-build",["iverilog",*shlex.split(os.environ.get("IVERILOG_FLAGS","")),"-g2012","-s","crt_stream_tb","-o",str(out/"crt.vvp"),*map(str,src),str(tb)])
            run("icarus-test",["vvp",*shlex.split(os.environ.get("VVP_FLAGS","")),str(out/"crt.vvp"),f"+vectors={vfile}"])
        if args.mutations:
            mutations=[
                ("inverse", "INV123=32'd1150438012", "INV123=32'd1150438013", "value/hold mismatch"),
                ("center", "value>(MODULUS>>1)", "value>=(MODULUS>>1)", "value/hold mismatch"),
                ("latency", "out_valid<=vd[2]", "out_valid<=vd[1]", "valid/latency mismatch"),
                ("reset", "va<=0; vb<=0", "va<=3'b111; vb<=0", "valid/latency mismatch"),
            ]
            for name,old,new,reject in mutations:
                mdir=out/f"mutation-{name}"; mdir.mkdir()
                content=src[1].read_text()
                if content.count(old)!=1: raise RuntimeError("mutation anchor mismatch: "+name)
                modified=mdir/src[1].name; modified.write_text(content.replace(old,new))
                run(f"mutation-{name}-build",["verilator","--cc","--exe","--build","-j","2","--top-module","genefer_crt3_pipe","--Mdir",str(mdir/"build"),str(src[0]),str(modified),str(cpp)])
                run(f"mutation-{name}-reject",[str(mdir/"build/Vgenefer_crt3_pipe"),str(vfile)],reject=reject)
        report["status"]="passed"
    finally:
        (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__": main()
