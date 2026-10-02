"""Reviewed-input full-N data27 gate; execution requires an explicit CLI switch.

Only candidate RTL is compiled. Retained baseline trees are read-only: original
ELF reproduction binds their objects before bench-only diagnostic relinking.
No vector copying, output normalization, cleanup, or model-tree mutation.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
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
import tarfile
import time

if __package__:
    from . import ntt27_prefetch_relink as base
else:
    import ntt27_prefetch_relink as base

GiB=1<<30
RESERVE=900*(1<<20)
TOP="genefer_ntt_banked27_prefetch_data27_engine"
HELPER_SHA="7b3f4252018c13096e4dbefbd7ca4f3ae46bf0f2a4d23bf89cfb4f0d36e700e8"
MANIFEST_SHA="00891a4d5a4f7fc10594132e9ee5dc195f96834d19b2d74673e8763c89c9e63b"
P1_RESULT_SHA="72fae2713ce3f9a947020f1e44e69d6a9e51bcd0f55dff4ba7fac3f203d0f775"
VECTOR_SHA="83b482acdfb477188524ef0e1d0dc501439194bf83e246b92cdfe95b5082f281"
P1_EXE_SHA="3b55efdb548a202234102b3c7f62a18826bb490f3fe253db6e0c9aaa3a66b719"
CANDIDATE_SHA="45025c151a202efc64e432d274016433352c6ef3f27a49434e270b02f17d1753"
LEAF_SHA="1e86ac052d83377fac45637a1f4b2708ce0012700209333f25012b566df0f816"
COMMON=("genefer_montgomery_mul27_sparse_pipe.sv","genefer_sdp_ram32.sv",
    "genefer_sp_ram.sv","genefer_root_recurrence27.sv","genefer_ntt_banked27_engine.sv")
COUNTERS=(b"seed_setup=",b"cycles=",b"butterflies=",b"data_reads=",
    b"data_writes=",b"root_reads=",b"wait_cycles=")
TASK_ROOT=Path("/home/jtl/gfn-fpga-lab/agent-work/ntt27-prefetch-data27")
BUILD_ENV=("MAKEFLAGS","MFLAGS","CXXFLAGS","CFLAGS","CPPFLAGS","LDFLAGS",
    "CC","CXX","AR","OBJCACHE","OPT_FAST","OPT_SLOW","OPT_GLOBAL")

def verify_build_profile(directory,log,field):
    """Check actual emitted compiler commands, not merely requested make flags."""
    variables={}
    text=(directory/(base.PREFIX+"_classes.mk")).read_text().replace("\\\n","")
    for line in text.splitlines():
        if "=" in line and line.lstrip().startswith("VM_"):
            key,value=line.split("=",1);append=key.rstrip().endswith("+")
            key=key.rstrip().rstrip("+").strip();words=value.split("#",1)[0].split()
            variables[key]=(variables.get(key,[]) if append else [])+words
    groups={kind:set(sum((variables.get(f"VM_{category}_{kind}",[]) for category in ("CLASSES","SUPPORT","GLOBAL")),[])) for kind in ("FAST","SLOW")}
    if not all(groups.values()):raise RuntimeError("missing generated fast/slow classes")
    seen=set();rows=[];p=base.FIELDS[field-1][0]
    for line in log.read_text().splitlines():
        if not line.startswith("g++ "):continue
        args=shlex.split(line)
        if "-c" not in args and "c++-header" not in args:continue
        output=args[args.index("-o")+1];stem=Path(output).stem
        slow=stem in groups["SLOW"] or output.endswith(".slow.gch")
        options=[arg for arg in args if arg.startswith("-O")]
        if options!=([] if slow else ["-Os"]):raise RuntimeError("actual optimization flags mismatch: "+line)
        for define in ("-DNTT_LANES=64","-DNTT_AW=16",f"-DNTT_P={p}u"):
            if define not in args:raise RuntimeError("actual benchmark defines mismatch")
        seen.add(stem);rows.append({"output":output,"class":"slow" if slow else "fast/global/bench","command":args})
    required=groups["FAST"]|groups["SLOW"]|{"ntt_banked27_prefetch_data27_engine"}
    if not required<=seen:raise RuntimeError("compile log missing classes: "+repr(required-seen))
    top=directory/(base.PREFIX+".cpp")
    if f"unsigned {base.PREFIX}::threads() const {{ return 1; }}" not in top.read_text():
        raise RuntimeError("generated model thread count differs")
    generated={str(path):base.sha(path) for path in directory.iterdir() if path.suffix in (".cpp",".h",".mk",".dat")}
    return {"actual_compile_commands":rows,"generated_source_sha256":generated,"model_threads":1}

def source_archive(manifest,out):
    archive=out/"source-closure.tar.gz";members={}
    with tarfile.open(archive,"w:gz") as tar:
        for path,digest in manifest["input_sha256"].items():
            source=Path(path)
            if source.suffix not in (".sv",".py",".cpp",".h",".mk"):continue
            name="inputs/"+str(source).lstrip("/")
            tar.add(source,arcname=name,recursive=False);members[name]=digest
    return {"path":str(archive),"sha256":base.sha(archive),"member_sha256":members}

def allocated_bytes(root):
    """Allocated space owned by this fresh tree, without following symlinks."""
    seen=set();total=0
    for path in [root,*root.rglob("*")]:
        try:stat=path.lstat()
        except FileNotFoundError:continue  # Compiler can remove a transient dependency file.
        key=(stat.st_dev,stat.st_ino)
        if key not in seen:total+=stat.st_blocks*512;seen.add(key)
    return total

def required_free(allocated,concurrent):
    if min(allocated,concurrent)<0:raise ValueError("negative reservation")
    return 10*GiB+max(0,RESERVE-allocated)+concurrent

def equal_pair(left_log,right_log,left_dump,right_dump):
    raw=left_log.read_bytes()
    if raw!=right_log.read_bytes():raise RuntimeError("raw stdout/counter mismatch")
    runs=[line for line in raw.splitlines() if line.startswith(b"RUN ")]
    if not runs or b"PASS runs=" not in raw:raise RuntimeError("missing normal completion")
    if any(any(counter not in line for counter in COUNTERS) for line in runs):
        raise RuntimeError("missing rich operation counters")
    if left_dump.read_bytes()!=right_dump.read_bytes():raise RuntimeError("raw residue dump mismatch")
    return {"stdout_sha256":base.sha(left_log),"dump_sha256":base.sha(left_dump),"runs":len(runs)}

def candidate_command(field,directory,root,bench):
    p,q=base.FIELDS[field-1]
    return ["verilator","--cc","--exe","--build","-j","2","--threads","1",
        "--top-module",TOP,"--prefix",base.PREFIX,"--Mdir",str(directory),
        "-MAKEFLAGS","OPT_FAST=-Os OPT_SLOW= OPT_GLOBAL=-Os",
        "-GAW=16","-GLANES=64",f"-GP={p}",f"-GQ={q}","-CFLAGS",
        f"-DNTT_LANES=64 -DNTT_AW=16 -DNTT_P={p}u",
        *[str(base.OLD_ROOT/"rtl/kernel"/name) for name in COMMON],
        str(root/"rtl/kernel"/(TOP+".sv")),str(root/"rtl/kernel/genefer_sdp_ram27_residue.sv"),str(bench)]

def require_cgroup_limits():
    group=next(line.split(":",2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines() if line.startswith("0::"))
    path=Path("/sys/fs/cgroup")/group.lstrip("/")
    cpu=[];memory=[]
    while path!=Path("/sys/fs"):
        if (path/"cpu.max").exists():
            quota,period=(path/"cpu.max").read_text().split()
            if quota!="max":cpu.append(int(quota)/int(period))
        if (path/"memory.max").exists():
            limit=(path/"memory.max").read_text().strip()
            if limit!="max":memory.append(int(limit))
        path=path.parent
    if not cpu or min(cpu)>2 or not memory or min(memory)>4*GiB:
        raise RuntimeError("must run under CPUQuota<=200%, MemoryMax<=4GiB")
    return {"cpu_quota_cores":min(cpu),"memory_limit_bytes":min(memory)}

class Executor:
    def __init__(self,out,concurrent):
        self.out=out;self.concurrent=concurrent
        self.report={"status":"incomplete","steps":[],"matched_cases":[],"executables":[],
            "reservation_bytes":RESERVE,"concurrent_reservation_bytes":concurrent,
            "scope":"AW16/L64/R32 data RAM leaf only; no whole-core or physical claim"}

    def save(self):
        (self.out/"report.json").write_text(json.dumps(self.report,indent=2)+"\n")

    def guard(self,memory=False):
        used=allocated_bytes(self.out);free=shutil.disk_usage(self.out).free
        if free<required_free(used,self.concurrent):raise RuntimeError("incomplete-resource: disk floor/reservation")
        if memory:
            available=next(int(line.split()[1])*1024 for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))
            if available<6*GiB:raise RuntimeError("incomplete-resource: 6GiB available RAM required")

    @contextmanager
    def compile_lock(self):
        with open(base.LOCK,"a") as lock:
            start=time.monotonic()
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()-start>1800:raise RuntimeError("incomplete-timeout: compile lock")
                    time.sleep(.25)
            self.guard(memory=True)
            yield

    def run(self,name,command,timeout=600,reasons=()):
        self.guard();log=self.out/(name+".log");metrics=self.out/(name+".metrics")
        # Environment-derived fault/fuzz settings must not silently alter a case.
        env=os.environ.copy()
        for key in ("NTT_NONCANON","NTT_SKIP_HOST_FUZZ",*BUILD_ENV):env.pop(key,None)
        timed=["/usr/bin/time","-f","wall_seconds=%e\nmax_rss_kib=%M","-o",str(metrics),"--",*command]
        start=time.monotonic();failure=None
        with log.open("wb") as handle:
            proc=subprocess.Popen(timed,cwd=self.out,stdout=handle,stderr=subprocess.STDOUT,
                env=env,start_new_session=True)
            try:
                while proc.poll() is None:
                    if time.monotonic()-start>timeout:raise RuntimeError("incomplete-timeout: "+name)
                    self.guard();time.sleep(.5)
            except BaseException as exc:
                failure=str(exc)
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
                raise
            finally:
                self.report["steps"].append({"name":name,"command":list(command),
                    "timed_command":timed,"returncode":proc.returncode,"seconds":time.monotonic()-start,
                    "failure":failure,"log_sha256":base.sha(log),
                    "metrics_sha256":base.sha(metrics) if metrics.exists() else None,
                    "expected_rejections":list(reasons),"passed":False})
                self.save()
        content=log.read_text(errors="replace")
        passed=(proc.returncode!=0 and any(reason in content for reason in reasons)) if reasons else proc.returncode==0
        if not passed:raise RuntimeError("command rejected: "+name+"\n"+content[-1200:])
        self.report["steps"][-1]["passed"]=True;self.save()
        return log

    def relink(self,row,bench,manifest):
        field=row["field"];old=Path(row["directory"])
        fresh=self.out/f"relink-p{field}";fresh.mkdir()
        link=shlex.split(row["link_line"])
        for i,arg in enumerate(link):
            if arg.endswith((".o",".a")):link[i]=str(old/arg)
        output=link.index("-o")+1
        reproduced=fresh/"original-reproduced";link[output]=str(reproduced)
        with self.compile_lock():
            base.recheck(manifest)
            self.run(f"reproduce-p{field}",link,180)
            if base.sha(reproduced)!=row["original_executable_sha256"]:
                raise RuntimeError("retained objects fail original ELF reproduction")
            command=["-I"+str(old) if arg=="-I." else arg for arg in shlex.split(row["compile_line"])]
            command[command.index("-o")+1]=str(fresh/"diagnostic-bench.o");command[-1]=str(bench)
            self.run(f"compile-bench-p{field}",command,180)
            exe=fresh/"baseline-diagnostic";link[1]=str(fresh/"diagnostic-bench.o");link[output]=str(exe)
            self.run(f"link-diagnostic-p{field}",link,180)
            base.recheck(manifest)
        return exe

    def build(self,field,root,bench,manifest):
        directory=self.out/f"build-candidate-p{field}"
        with self.compile_lock():
            base.recheck(manifest)
            self.run(f"build-candidate-p{field}",candidate_command(field,directory,root,bench),900)
            profile=verify_build_profile(directory,self.out/f"build-candidate-p{field}.log",field)
            self.report.setdefault("actual_build_profiles",[]).append({"field":field,**profile})
            base.recheck(manifest)
        return directory/base.PREFIX

    def replay(self,manifest,models):
        for case in manifest["cases"]:
            if base.sha(case["vector"])!=case["sha256"]:raise RuntimeError("vector changed")
            outputs=[];dumps=[]
            for kind,exe in zip(("baseline","candidate"),models[case["field"]]):
                name=case["name"]+"-"+kind;dump=self.out/(name+"-dump.txt")
                prefix=[] if case["host_fuzz"] else ["env","NTT_SKIP_HOST_FUZZ=1"]
                outputs.append(self.run(name,[*prefix,str(exe),case["vector"],str(dump)]));dumps.append(dump)
            match=equal_pair(*outputs,*dumps)
            self.report["matched_cases"].append({**case,**match,"exact_stdout_and_dump":True});self.save()
        for field,pair in models.items():
            vector=next(c["vector"] for c in manifest["cases"] if c["name"]==f"transform-p{field}-aw16-n2")
            for kind,exe in zip(("baseline","candidate"),pair):
                for mode in ("scalar","vector","scalar-high","vector-high"):
                    reasons=["noncanonical NTT27 data write"]
                    if kind=="candidate" and mode.endswith("-high"):reasons.append("RAM residue write exceeds27 bits")
                    name=f"fault-p{field}-{kind}-{mode}"
                    self.run(name,["env","NTT_NONCANON="+mode,str(exe),vector,str(self.out/(name+"-dump.txt"))],180,reasons)

def validate_inputs(args):
    p1=args.p1.resolve();root=args.source_root.resolve();bench=root/"rtl/tb/ntt_banked27_prefetch_data27_engine.cpp"
    pins={p1/"manifest.json":MANIFEST_SHA,p1/"result.json":P1_RESULT_SHA,
        args.vector_receipt.resolve():VECTOR_SHA,Path(base.__file__).resolve():HELPER_SHA,
        bench:base.NEW_BENCH_SHA,p1/"baseline-diagnostic":P1_EXE_SHA,
        p1/"original-reproduced":base.OLD_EXE_SHAS[0],
        root/"rtl/kernel"/(TOP+".sv"):CANDIDATE_SHA,
        root/"rtl/kernel/genefer_sdp_ram27_residue.sv":LEAF_SHA}
    for path,digest in pins.items():
        if base.sha(path)!=digest:raise RuntimeError("pin mismatch: "+str(path))
    historical=json.loads((p1/"manifest.json").read_text());base.recheck(historical)
    vector=json.loads(args.vector_receipt.read_text())
    if vector["status"]!="passed" or vector["case_count"]!=93:raise RuntimeError("vector audit incomplete")
    manifest=base.audit(bench)
    if manifest["cases"]!=historical["cases"]:raise RuntimeError("current suite differs from source-derived suite")
    regenerated={row["name"]:(row["sha256"],row["host_fuzz"]) for row in vector["cases"]}
    expected={row["name"]:(row["sha256"],row["host_fuzz"]) for row in manifest["cases"]}
    if regenerated!=expected or len(expected)!=93:raise RuntimeError("vector contract differs")
    manifest["input_sha256"].update(historical["input_sha256"])
    manifest["input_sha256"].update({str(path):digest for path,digest in pins.items()})
    manifest["input_sha256"][str(Path(__file__).resolve())]=base.sha(__file__)
    for tool in ("verilator","g++","/usr/bin/time",sys.executable):
        path=Path(shutil.which(tool)).resolve();manifest["input_sha256"][str(path)]=base.sha(path)
    manifest["dispatch"]="explicit --execute required; three candidates only"
    return manifest,root,bench,p1/"baseline-diagnostic"

def main():
    parser=argparse.ArgumentParser()
    for name in ("output","source-root","p1","vector-receipt"):
        parser.add_argument("--"+name,required=True,type=Path)
    parser.add_argument("--concurrent-reservation-mib",required=True,type=int)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if socket.gethostname()!="aethia" or not __debug__:raise RuntimeError("aethia with assertions required")
    if args.concurrent_reservation_mib<0:parser.error("reservation cannot be negative")
    if args.output.exists():parser.error("fresh output required")
    if not args.output.resolve().is_relative_to(TASK_ROOT) or not args.source_root.resolve().is_relative_to(TASK_ROOT):
        parser.error("output and new source snapshot must remain within isolated data27 task tree")
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));sys.dont_write_bytecode=True
    limits=require_cgroup_limits()
    out=args.output.resolve();out.mkdir(parents=True)
    job=Executor(out,args.concurrent_reservation_mib*(1<<20));job.report["limits"]=limits
    try:
        job.guard(memory=True)
        manifest,root,bench,p1=validate_inputs(args)
        (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        job.report["manifest_sha256"]=base.sha(out/"manifest.json")
        job.report["build_profile"]=manifest["build_profile"]
        job.report["sanitized_environment_keys"]=list(BUILD_ENV)
        job.report["source_archive"]=source_archive(manifest,out)
        if not args.execute:
            job.report.update(status="audited-not-executed",dispatch="none");return
        models={}
        for row in manifest["builds"]:
            field=row["field"]
            baseline=p1 if field==1 else job.relink(row,bench,manifest)
            candidate=job.build(field,root,bench,manifest);models[field]=(baseline,candidate)
            for kind,exe in zip(("baseline","candidate"),models[field]):
                job.report["executables"].append({"field":field,"kind":kind,"path":str(exe),"sha256":base.sha(exe)})
            job.save()
        job.replay(manifest,models)
        # Isolated interpreter avoids a new snapshot's 'reference' package shadowing
        # the pinned old oracle and -B guarantees no old-tree bytecode writes.
        helper=str(Path(base.__file__).resolve())
        for kind in ("baseline","candidate"):
            dumps=[str(out/f"squares-p{field}-aw16-n65536-{kind}-dump.txt") for field in (1,2,3)]
            code="import runpy,json,sys; m=runpy.run_path(sys.argv[1]); print(json.dumps(m['verify_full_integer_outputs'](sys.argv[2:])))"
            log=job.run("whole-integer-"+kind,[sys.executable,"-B","-c",code,helper,*dumps],600)
            result=json.loads(log.read_text())
            if result!={"whole_integer_crt":True,"cases":["base2","recurrent0","recurrent1","max-base1e9"]}:
                raise RuntimeError("whole-integer case coverage mismatch")
        if len(job.report["matched_cases"])!=93:raise RuntimeError("incomplete pair coverage")
        base.recheck(manifest)
        for row in job.report["executables"]:
            if base.sha(row["path"])!=row["sha256"]:raise RuntimeError("executable changed")
        for profile in job.report["actual_build_profiles"]:
            for path,digest in profile["generated_source_sha256"].items():
                if base.sha(path)!=digest:raise RuntimeError("generated model source changed")
        # Retain generated models/PCHs remotely unchanged. The lightweight receipt
        # and source closure can be retrieved first; executables/models separately.
        job.report["artifact_sha256"]={str(path.relative_to(out)):base.sha(path)
            for path in out.rglob("*") if path.is_file() and path.name!="report.json" and not path.name.endswith(".gch")}
        job.guard();job.report.update(status="passed",inputs_rehashed_after=True,whole_integer_crt=True)
    except BaseException as exc:
        job.report.update(status="incomplete-or-failed",failure=str(exc));raise
    finally:
        job.report["runner_sha256"]=base.sha(__file__);job.save()

if __name__=="__main__":main()
