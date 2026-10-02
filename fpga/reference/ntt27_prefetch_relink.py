"""Audit retained full-N prefetch models; optionally relink one diagnostic bench.

Never run make or Verilator in retained directories. The only executable action
exposed here is a P1 bench-only relink plus bounded normal/fault smoke. Full-suite
dispatch is deliberately absent pending parent review and disk-headroom approval.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time

OLD_ROOT=Path("/home/jtl/gfn-fpga-lab/agent-work/ntt27-prefetch/fpga")
OLD_GATE=OLD_ROOT/"artifacts/full64-v1"
PREFIX="Vgenefer_ntt_banked27_prefetch_engine"
OLD_REPORT_SHA="1e4a3868f3cf26da36e955acb177e11d3423ecd6e8016179ae8faaa165d96d59"
OLD_BENCH_SHA="7fadaaa7d32c80f91be878055300c9496412ace40f254d003e0d9dc2a281e585"
NEW_BENCH_SHA="56e3e277dde7ed4393d9b6833fbe7e28b936a5d6cf56ad98b8d834072f8d3d76"
OLD_EXE_SHAS=("c6853d8205b71806767c9dc84ee0dbb944e5880f731a7710ee89fd30fbb7b2b9",
    "88519fb459a5bf4bbbdfd79642d4300357e3000382275bfb47f3210e1cb85acc",
    "3812811b3a4aa05231ef036ab0b0dd053615525d1d543f5023bdeee7395c7302")
FIELDS=((104857601,4190109697),(69206017,4225761281),(67239937,4227727361))
KIT=Path("/home/jtl/gfn-fpga-lab/tools/verilator/usr/share/verilator")
LOCK=Path("/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock")

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def expected_cases(field):
    stem=f"p{field}-aw16"
    names=[f"transform-{stem}-n{1<<lg}" for lg in range(1,17)]
    names+=[f"squares-{stem}-n65536"]
    ops=((1,0,0),(2,0,1),(0,2,0),(3,2,0),(0,1,0),(0,3,0))
    names += [f"reset-{stem}-d{direction}-phase{phase}-op{op}-inv{inv}"
        for direction in (0,1) for phase,op,inv in ops]
    return names+[f"reset-{stem}",f"size-reload-{stem}"]

def audit(bench):
    assert __debug__,"Python oracle assertions must be enabled"
    assert sha(OLD_GATE/"report.json")==OLD_REPORT_SHA
    report=json.loads((OLD_GATE/"report.json").read_text())
    assert report["status"]=="passed" and report["source_hashes_rechecked"]
    inputs={str(OLD_GATE/"report.json"):OLD_REPORT_SHA,str(bench):NEW_BENCH_SHA,
        str(Path(__file__).resolve()):sha(Path(__file__))}
    assert sha(bench)==NEW_BENCH_SHA
    for relative,digest in report["source_sha256"].items():
        path=OLD_ROOT/relative;assert sha(path)==digest,relative;inputs[str(path)]=digest
    assert report["source_sha256"]["rtl/tb/ntt_banked27_prefetch_engine.cpp"]==OLD_BENCH_SHA
    builds=[];cases=[]
    for field,(p,q) in enumerate(FIELDS,1):
        directory=OLD_GATE/f"build-p{field}-aw16-l64"
        exe=directory/PREFIX
        row=report["executables"][field-1]
        assert (row["field"],row["P"],row["Q"],row["AW"],row["LANES"],row["montgomery_radix_bits"])==(field,p,q,16,64,32)
        assert row["path"]==str(exe) and row["sha256"]==OLD_EXE_SHAS[field-1]
        assert sha(exe)==OLD_EXE_SHAS[field-1]
        build=next(s for s in report["steps"] if s["name"]==f"build-p{field}-aw16-l64")
        for param in ("-GAW=16","-GLANES=64",f"-GP={p}",f"-GQ={q}"):assert param in build["command"]
        log=OLD_GATE/(build["name"]+".log")
        lines=log.read_text().splitlines()
        compile_line=next(line for line in lines if line.startswith("g++ ") and " -c -o ntt_banked27_prefetch_engine.o " in line)
        link_line=next(line for line in lines if line.startswith("g++ ") and "ntt_banked27_prefetch_engine.o verilated.o" in line and " -o "+PREFIX in line)
        assert "-Os" in shlex.split(compile_line)
        compile_tokens=shlex.split(compile_line)
        assert compile_tokens[-1]==str(OLD_ROOT/"rtl/tb/ntt_banked27_prefetch_engine.cpp")
        for define in ("-DNTT_LANES=64","-DNTT_AW=16",f"-DNTT_P={p}u"):assert define in compile_tokens
        assert shlex.split(link_line)==["g++","ntt_banked27_prefetch_engine.o","verilated.o","verilated_threads.o",PREFIX+"__ALL.a","-pthread","-lpthread","-latomic","-o",PREFIX]
        assert "--threads" not in build["command"],"unexpected retained model threading configuration"
        generated_top=directory/(PREFIX+".cpp")
        assert f"unsigned {PREFIX}::threads() const {{ return 1; }}" in generated_top.read_text()
        paths=[exe,log,directory/(PREFIX+".mk"),directory/(PREFIX+"_classes.mk"),
            directory/(PREFIX+"__ALL.a"),directory/"ntt_banked27_prefetch_engine.o",
            directory/"verilated.o",directory/"verilated_threads.o",generated_top,*sorted(directory.glob("*.h"))]
        for path in paths:inputs[str(path)]=sha(path)
        builds.append({"field":field,"P":p,"Q":q,"AW":16,"LANES":64,"radix_bits":32,
            "model_threads":1,"directory":str(directory),"original_executable_sha256":row["sha256"],
            "compile_line":compile_line,"link_line":link_line})
        for name in expected_cases(field):
            step=next(s for s in report["steps"] if s["name"]==name)
            vector=OLD_GATE/(name+".txt")
            fuzz=name==f"transform-p{field}-aw16-n65536"
            expected=([str(exe),str(vector),str(OLD_GATE/(name+"-dump.txt"))] if fuzz else
                ["env","NTT_SKIP_HOST_FUZZ=1",str(exe),str(vector),str(OLD_GATE/(name+"-dump.txt"))])
            assert step["passed"] and step["command"]==expected,name
            digest=sha(vector);inputs[str(vector)]=digest
            cases.append({"name":name,"field":field,"vector":str(vector),"sha256":digest,"host_fuzz":fuzz})
        square=(OLD_GATE/f"squares-p{field}-aw16-n65536.txt").read_text().splitlines()
        assert square.count("DUMP")==4,"missing full-N maximum-base square case"
        loads=[square[i+1] for i,line in enumerate(square) if line=="LOAD"]
        assert len(loads)==4
        maximum=(999999999%p)*((1<<32)%p)%p
        assert loads[-1].split()==[str(maximum)]*65536,"last square is not max-base1e9"
    assert len(cases)==93
    for path in sorted((KIT/"include").rglob("*.h")):inputs[str(path)]=sha(path)
    inputs[str(KIT/"include/verilated.mk")]=sha(KIT/"include/verilated.mk")
    version=subprocess.check_output(["verilator","--version"],text=True).strip()
    assert version=="Verilator 5.032 2025-01-01 rev (Debian 5.032-1)",version
    gcc_version=subprocess.check_output(["g++","-dumpfullversion","-dumpversion"],text=True).strip()
    for row in builds:
        comment=subprocess.check_output(["readelf","-p",".comment",str(Path(row["directory"])/"ntt_banked27_prefetch_engine.o")],text=True)
        assert "GCC:" in comment and gcc_version in comment,"compiler ABI/version mismatch"
    compiler=Path(shutil.which("g++")).resolve();inputs[str(compiler)]=sha(compiler)
    return {"status":"audited","source_report_sha256":OLD_REPORT_SHA,"builds":builds,"cases":cases,
        "input_sha256":inputs,"bench_sha256":NEW_BENCH_SHA,"verilator":version,"compiler_version":gcc_version,
        "build_profile":{"OPT_FAST":"-Os","OPT_SLOW":"","OPT_GLOBAL":"-Os","model_threads":1},
        "full_gate_requirement":"Strict rich stdout/dump equality on all93 cases, four independent whole-integer CRT checks including max-base1e9, and scalar/vector canonical/high-bit faults for every field",
        "dispatch":"none; full candidate models and full replay require separate approval"}

def recheck(manifest):
    for path,digest in manifest["input_sha256"].items():assert sha(path)==digest,"input changed: "+path

def run(out,name,command,timeout=180,reason=None):
    began=time.monotonic()
    proc=subprocess.Popen(command,cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
    try:log,_=proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid,signal.SIGKILL);log,_=proc.communicate();(out/(name+".log")).write_text(log)
        raise RuntimeError("bounded command timeout: "+name)
    path=out/(name+".log");path.write_text(log)
    passed=proc.returncode==0 if reason is None else proc.returncode!=0 and reason in log
    if not passed:raise RuntimeError(name+": "+log[-1800:])
    return {"name":name,"command":list(command),"returncode":proc.returncode,"passed":passed,
        "seconds":time.monotonic()-began,"log_sha256":sha(path),"expected_rejection":reason}

def p1_smoke(manifest,bench,out):
    row=manifest["builds"][0];old=Path(row["directory"]);steps=[]
    with open(LOCK,"a") as lock:
        began=time.monotonic()
        while True:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()-began>1800:raise RuntimeError("compile lock wait expired")
                time.sleep(.25)
        assert shutil.disk_usage(out).free>=10*(1<<30),"10GiB disk guard"
        available=next(int(line.split()[1])*1024 for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))
        assert available>=6*(1<<30),"6GiB available-memory guard"
        recheck(manifest)
        # Read-only original objects must first recreate the trusted old ELF.
        link=shlex.split(row["link_line"]);output_index=link.index("-o")+1
        for i,arg in enumerate(link):
            if arg.endswith((".o",".a")):link[i]=str(old/arg)
        reproduced=out/"original-reproduced";link[output_index]=str(reproduced)
        steps.append(run(out,"reproduce-original",link))
        assert sha(reproduced)==row["original_executable_sha256"],"retained link inputs do not reproduce trusted baseline"
        compile_cmd=shlex.split(row["compile_line"])
        compile_cmd=["-I"+str(old) if item=="-I." else item for item in compile_cmd]
        compile_cmd[compile_cmd.index("-o")+1]=str(out/"diagnostic-bench.o")
        compile_cmd[-1]=str(bench)
        steps.append(run(out,"compile-diagnostic-bench",compile_cmd))
        diagnostic=out/"baseline-diagnostic"
        link[1]=str(out/"diagnostic-bench.o");link[output_index]=str(diagnostic)
        steps.append(run(out,"link-diagnostic",link))
        recheck(manifest)
    # N1024 smoke only; full93-case replay is intentionally not dispatched here.
    case=next(c for c in manifest["cases"] if c["name"]=="transform-p1-aw16-n1024")
    steps.append(run(out,"normal-smoke",["env","NTT_SKIP_HOST_FUZZ=1",str(diagnostic),case["vector"],str(out/"normal-dump.txt")]))
    normal=(out/"normal-smoke.log").read_text()
    assert "PASS runs=" in normal
    for counter in ("seed_setup=","cycles=","butterflies=","data_reads=","data_writes=","root_reads=","wait_cycles="):
        assert counter in normal,"diagnostic field absent: "+counter
    for mode in ("scalar","vector","scalar-high","vector-high"):
        steps.append(run(out,"reject-"+mode,["env","NTT_NONCANON="+mode,str(diagnostic),case["vector"],str(out/(mode+"-dump.txt"))],reason="noncanonical NTT27 data write"))
    recheck(manifest)
    return {"status":"passed","scope":"P1 bench-only relink, N1024 normal smoke and four canonical/high-bit faults; not a full-N candidate gate",
        "steps":steps,"original_reproduced_sha256":sha(reproduced),"diagnostic_executable_sha256":sha(diagnostic),
        "bench_object_sha256":sha(out/"diagnostic-bench.o"),"inputs_rehashed_after":True}

def verify_full_integer_outputs(dumps):
    """Fresh four-case CRT/big-int oracle for the later approved full replay.

    Caller must audit/recheck the pinned old reference closure before and after.
    No files are written and no simulation is launched by this function.
    """
    sys.path.insert(0,str(OLD_ROOT))
    from reference.ntt_cached_regression import cases_for,encode
    from reference.ntt27_generated_regression import PRIMES
    from reference.rns_reference import centered_crt
    assert [(p.p,p.q) for p in PRIMES]==list(FIELDS)
    cases=cases_for(16)+[("max-base1e9",[999999999]*65536,1000000000)]
    planes=[list(map(int,Path(path).read_text().split())) for path in dumps]
    assert len(planes)==3 and all(len(plane)==4*65536 for plane in planes)
    for field,plane in enumerate(planes):assert all(0<=value<FIELDS[field][0] for value in plane)
    for i,(_,digits,base) in enumerate(cases):
        coeff=[centered_crt((planes[f][i*65536+j] for f in range(3)),PRIMES) for j in range(65536)]
        modulus=pow(base,65536)+1
        assert encode(coeff,base)%modulus==pow(encode(digits,base),2,modulus)
    return {"whole_integer_crt":True,"cases":[name for name,_,_ in cases]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--bench",required=True,type=Path);ap.add_argument("--smoke-p1",action="store_true")
    args=ap.parse_args()
    if socket.gethostname()!="aethia":raise RuntimeError("audit/relink restricted to aethia")
    if not __debug__:raise RuntimeError("Python assertions disabled")
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    out=args.output.resolve();bench=args.bench.resolve()
    if out.exists():ap.error("fresh output directory required")
    out.mkdir(parents=True)
    result={"status":"failed"}
    try:
        manifest=audit(bench);(out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        result=p1_smoke(manifest,bench,out) if args.smoke_p1 else {"status":"audited","dispatch":"none"}
    except Exception as exc:
        result["failure"]=str(exc);raise
    finally:
        if (out/"manifest.json").exists():result["manifest_sha256"]=sha(out/"manifest.json")
        result["runner_sha256"]=sha(Path(__file__))
        (out/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
