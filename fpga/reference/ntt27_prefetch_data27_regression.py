"""Isolated data27 storage gate. Reuses the frozen independent NTT oracles.

The parent and candidate execute identical vectors and an identical benchmark,
including all operation counters. Only data RAM storage and top identity differ.
Simulation is restricted to aethia; small gates precede any full-size dispatch.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import shutil
import socket
import subprocess
import time
from .ntt27_prefetch_regression import PrefetchLab, LOCK
from .ntt27_generated_regression import PRIMES, SOURCES
from .ntt_cached_regression import cases_for, encode
from .rns_reference import centered_crt

PARENT = "genefer_ntt_banked27_prefetch_engine"
TOP = "genefer_ntt_banked27_prefetch_data27_engine"
PARENT_SHA = "9381ff17205c65f5b34ba355b845e15fa25cc7ce1370f81160c147aea51c4a9c"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check_clone(root):
    parent = root/"rtl/kernel"/(PARENT+".sv")
    assert sha(parent) == PARENT_SHA, "frozen parent source changed"
    text = parent.read_text()
    old = "genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) data_ram"
    assert text.count(old) == 1
    expected = text.replace("module "+PARENT, "module "+TOP).replace(old,
        "genefer_sdp_ram27_residue #(.AW(RW),.DEPTH(DEPTH)) data_ram")
    assert (root/"rtl/kernel"/(TOP+".sv")).read_text() == expected, "candidate has non-storage changes"

class Data27Lab(PrefetchLab):
    def __init__(self, output, optimization=0):
        super().__init__(output, "verilator")
        self.parents = {}
        self.optimization = "-O"+str(optimization)
        self.make_flags = " ".join(key+"="+self.optimization for key in ("OPT_FAST","OPT_SLOW","OPT_GLOBAL"))
        self.report["scope"] = "data RAM only; R=2^32; no whole-core or physical claim"
        self.report["build_profile"] = {"optimization":self.optimization,"make_flags":self.make_flags,
            "model_threads":1,"compile_jobs":2,"verilator":subprocess.check_output([self.verilator,"--version"],text=True).strip(),
            "rss_metric":"GNU time maximum resident set size, not aggregate concurrent cgroup memory"}
        check_clone(self.root)

    def timed_command(self,name,command):
        return ["/usr/bin/time","-f","wall_seconds=%e\nmax_rss_kib=%M","-o",str(self.output/(name+".metrics")),"--",*command]

    def metrics(self,name):
        path=self.output/(name+".metrics")
        metrics={}
        for line in path.read_text().splitlines():
            if line.startswith("wall_seconds="):metrics["wall_seconds"]=float(line.split("=",1)[1])
            elif line.startswith("max_rss_kib="):metrics["max_rss_kib"]=int(line.split("=",1)[1])
        assert set(metrics)=={"wall_seconds","max_rss_kib"},"missing GNU time metrics"
        return {**metrics,"metrics_sha256":sha(path)}

    def run(self,name,command,reject=None):
        result=super().run(name,self.timed_command(name,command),reject)
        self.report["steps"][-1]["measurements"]=self.metrics(name)
        return result

    def compile(self, name, top, sources, bench, options=(), prefix=None):
        directory = self.output/name
        command = [self.verilator,"--cc","--exe","--build","-j","2",
            "--top-module",top,"--Mdir",str(directory),"--threads","1","-MAKEFLAGS",self.make_flags,*options]
        if prefix: command += ["--prefix",prefix]
        command += [*map(str,sources),str(bench)]
        with open(LOCK,"a") as lock:
            began=time.monotonic()
            while True:
                try:
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()-began>1800:raise RuntimeError("shared compile lock wait exceeded1800seconds")
                    time.sleep(0.25)
            self.report.setdefault("compile_lock_waits",[]).append({"build":name,"seconds":time.monotonic()-began})
            if shutil.disk_usage(self.root).free<10*(1<<30):raise RuntimeError("10GiB disk guard")
            available=next(int(line.split()[1])*1024 for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))
            if available<6*(1<<30):raise RuntimeError("6GiB host memory headroom guard")
            # Compilation timeout is bounded independently of observations.
            command=self.timed_command(name,command)
            proc=subprocess.Popen(command,cwd=self.root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
            try: stdout,_=proc.communicate(timeout=900)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);stdout,_=proc.communicate()
                (self.output/(name+".log")).write_text(stdout)
                raise RuntimeError("build timeout: "+name)
            log=self.output/(name+".log");log.write_text(stdout)
            self.report["steps"].append({"name":name,"command":command,"returncode":proc.returncode,"passed":proc.returncode==0,"log_sha256":sha(log),"measurements":self.metrics(name)})
            if proc.returncode:raise RuntimeError("build failed: "+name+"\n"+stdout[-2000:])
        exe=directory/(prefix or "V"+top)
        self.report.setdefault("executables",[]).append({"path":str(exe),"sha256":sha(exe),
            "top":top,"source_sha256":{str(p.relative_to(self.root)):sha(p) for p in sources+[bench]}})
        print(name+": PASS",flush=True)
        return str(exe)

    def leaf(self):
        sources=[self.root/"rtl/kernel"/s for s in ("genefer_sdp_ram32.sv","genefer_sdp_ram27_residue.sv")]
        sources += [self.root/"rtl/tb/sdp_ram27_residue_equivalence.sv"]
        for aw in (1,9,11):
            exe=self.compile("leaf-aw"+str(aw),"sdp_ram27_residue_equivalence",sources,
                self.root/"rtl/tb/sdp_ram27_residue_equivalence.cpp",
                [f"-GAW={aw}","-CFLAGS",f"-DRAM_DEPTH={1<<aw}"])
            self.run("leaf-run-aw"+str(aw),[exe])
            if aw==9:
                for mode in ("high","bit27","collision"):
                    self.rejection("leaf-reject-"+mode,[exe,mode],
                        "RAM mixed-port collision" if mode=="collision" else "RAM residue write exceeds27 bits")

    def rejection(self,name,command,reason):
        proc=subprocess.run(command,cwd=self.root,capture_output=True,text=True,timeout=180)
        log=self.output/(name+".log");log.write_text(proc.stdout+proc.stderr)
        reasons=reason if isinstance(reason,tuple) else (reason,)
        passed=proc.returncode!=0 and any(r in proc.stdout+proc.stderr for r in reasons)
        self.report["steps"].append({"name":name,"command":command,"returncode":proc.returncode,
            "passed":passed,"expected_rejection":reason,"log_sha256":sha(log)})
        if not passed:raise RuntimeError("negative test survived: "+name)
        print(name+": PASS",flush=True)

    def build_pair(self,field,aw,lanes):
        prime=PRIMES[field]
        common=[self.root/"rtl/kernel"/s for s in SOURCES[:-1]]
        bench=self.root/"rtl/tb/ntt_banked27_prefetch_data27_engine.cpp"
        opts=[f"-GAW={aw}",f"-GLANES={lanes}",f"-GP={prime.p}",f"-GQ={prime.q}",
            "-CFLAGS",f"-DNTT_LANES={lanes} -DNTT_AW={aw} -DNTT_P={prime.p}u {self.optimization}"]
        results=[]
        for kind,top in (("parent",PARENT),("candidate",TOP)):
            sources=common+[self.root/"rtl/kernel"/(top+".sv")]
            if top==TOP:sources += [self.root/"rtl/kernel/genefer_sdp_ram27_residue.sv"]
            results.append(self.compile(f"build-{kind}-p{field+1}-aw{aw}-l{lanes}",top,sources,bench,opts,"V"+PARENT))
        self.parents[results[1]]=results[0]
        return results[1]

    def execute(self,name,exe,lines,fuzz=False):
        path=self.output/(name+".txt");path.write_text("\n".join(lines)+"\n")
        outputs=[];dumps=[]
        for kind,model in (("candidate",exe),("parent",self.parents[exe])):
            dump=self.output/(name+"-"+kind+"-dump.txt")
            command=(["env","NTT_SKIP_HOST_FUZZ=1"] if not fuzz else [])+[model,str(path),str(dump)]
            outputs.append(self.run(name+"-"+kind,command));dumps.append(dump.read_bytes())
        assert outputs[0]==outputs[1], "parent/candidate status, cycle or counter difference: "+name
        assert dumps[0]==dumps[1], "parent/candidate residue difference: "+name
        self.report.setdefault("matched_cases",[]).append({"name":name,"input_sha256":sha(path),
            "stdout_sha256":hashlib.sha256(outputs[0].encode()).hexdigest(),
            "dump_sha256":hashlib.sha256(dumps[0]).hexdigest(),"cycle_counter_output_equal":True})
        return list(map(int,dumps[0].split()))

    def canonical_faults(self,field,aw,exe):
        path=self.output/f"transform-p{field+1}-aw{aw}-n2.txt"
        for kind,model in (("candidate",exe),("parent",self.parents[exe])):
            for mode in ("scalar","vector","scalar-high","vector-high"):
                self.rejection(f"reject-p{field+1}-{kind}-{mode}",
                    ["env","NTT_NONCANON="+mode,model,str(path),str(self.output/"negative-dump.txt")],
                    ("noncanonical NTT27 data write","RAM residue write exceeds27 bits") if "high" in mode else "noncanonical NTT27 data write")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--aw",type=int,choices=range(1,17),default=4)
    ap.add_argument("--lanes",type=int,choices=(16,64),default=64)
    ap.add_argument("--leaf-only",action="store_true")
    ap.add_argument("--optimization",type=int,choices=(0,1,2),default=0)
    args=ap.parse_args()
    if socket.gethostname()!="aethia":raise RuntimeError("simulation only on aethia")
    if args.output.exists():ap.error("new output directory required")
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    lab=Data27Lab(args.output,args.optimization)
    try:
        lab.leaf()
        if not args.leaf_only:
            planes=[];cases=cases_for(args.aw)
            for field in range(3):
                exe=lab.build_pair(field,args.aw,args.lanes)
                for lg in range(1,args.aw+1):lab.transforms(field,args.aw,lg,args.lanes,exe,lg==args.aw)
                planes.append(lab.squares(field,args.aw,args.aw,args.lanes,exe,cases))
                lab.resets(field,args.aw,args.lanes,exe)
                lab.size_reload(field,args.aw,args.lanes,exe)
                lab.canonical_faults(field,args.aw,exe)
            for i,(_,digits,base) in enumerate(cases):
                coeff=[centered_crt((planes[f][i][j] for f in range(3)),PRIMES) for j in range(1<<args.aw)]
                modulus=pow(base,1<<args.aw)+1
                assert encode(coeff,base)%modulus==pow(encode(digits,base),2,modulus)
            lab.report["whole_integer_crt"]=True
        check_clone(lab.root)
        for path,digest in lab.report["source_sha256"].items():
            assert sha(lab.root/path)==digest,"source changed during gate: "+path
        lab.report["source_hashes_rechecked"]=True
        lab.report["status"]="passed"
    except Exception as exc:
        lab.report["status"]="failed";lab.report["failure"]=str(exc);raise
    finally:
        for step in lab.report["steps"]:
            log=lab.output/(step["name"]+".log")
            if log.exists():step["log_sha256"]=sha(log)
        (lab.output/"report.json").write_text(json.dumps(lab.report,indent=2)+"\n")

if __name__=="__main__":main()
