"""Isolated inactive-bank NTT seed prefetch; simulation is restricted to aethia.

Reuse the frozen independent pow/DFT/CRT oracles, not their cycle formula.
No frozen RTL or default engine selection is modified.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import resource
import shutil
import socket
import subprocess
import time
from pathlib import Path
from .ntt27_generated_regression import GeneratedLab, PRIMES, SOURCES, profile
from .ntt_cached_regression import cases_for, encode
from .ntt_difdit_regression import bitreverse
from .engine_regression import dif
from .rns_reference import RADIX, centered_crt

TOP = "genefer_ntt_banked27_prefetch_engine"
LOCK = "/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock"

def setup_cycles(lg: int, lanes: int, reverse: bool) -> int:
    """Exact exposed setup: first profile, each start, unhidden later loads.

    U active seed words plus step/read-response/clear requires U+3 clocks.
    G issue + 7 drain clocks overlap it. Stage setup remains separate.
    """
    groups = ((1 << lg) + 2*lanes-1) // (2*lanes)
    kw = (2*lanes).bit_length()-1
    stages = range(lg-1, -1, -1) if reverse else range(lg)
    result = 0
    for index, stage in enumerate(stages):
        period = 1 if stage < kw else 1 << (stage-kw+1)
        words = min(4, groups, period)*min(lanes, 1 << stage)
        result += words+4 if index == 0 else 1+max(0, words-groups-4)
    return result

class PrefetchLab(GeneratedLab):
    def build_ntt(self, field, aw, lanes, override=None):
        if shutil.disk_usage(self.root).free < 10*(1<<30):
            raise RuntimeError("aethia free space below 10 GiB; no new build dispatched")
        prime = PRIMES[field]
        paths = [self.root/"rtl/kernel"/s for s in SOURCES[:-1]]
        paths.append(override or self.root/"rtl/kernel"/(TOP+".sv"))
        name = f"build-p{field+1}-aw{aw}-l{lanes}"+("-"+override.parent.name if override else "")
        directory = self.output/name
        command = [self.verilator, "--cc", "--exe", "--build", "-j", "2",
            "--top-module", TOP, "--Mdir", str(directory), f"-GAW={aw}", f"-GLANES={lanes}",
            f"-GP={prime.p}", f"-GQ={prime.q}", "-CFLAGS",
            f"-DNTT_LANES={lanes} -DNTT_AW={aw} -DNTT_P={prime.p}u",
            *map(str, paths), str(self.root/"rtl/tb/ntt_banked27_prefetch_engine.cpp")]
        # Lock waiting is separately bounded and does not consume Lab.run's
        # 180-second compilation timeout. At most one waiter from this runner.
        with open(LOCK, "a") as lock:
            began = time.monotonic()
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic()-began > 900:
                        raise RuntimeError("shared compile lock wait exceeded 900 seconds")
                    time.sleep(0.25)
            self.report.setdefault("compile_lock_waits", []).append({"build":name,"seconds":time.monotonic()-began})
            self.run(name, command)
        exe = directory/("V"+TOP)
        self.report.setdefault("executables", []).append({"path":str(exe),
            "sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
            "field":field+1,"P":prime.p,"Q":prime.q,"montgomery_radix_bits":32,
            "AW":aw,"LANES":lanes,"sources":[str(p) for p in paths]})
        return str(exe)

    def resets(self, field, aw, lanes, exe):
        lg = min(5, aw); n = 1 << lg; p = PRIMES[field].p; r = RADIX % p
        words = profile(field, aw, lg, lanes); lines = []
        values = [(i*7919+17) % p for i in range(n)]
        def emit(command, data): lines.append(command+"\n"+" ".join(map(str, data)))
        groups = (n+2*lanes-1)//(2*lanes)
        point = (n+lanes-1)//lanes+7
        for reverse in (0, 1):
            transform = lg*(groups+8)+setup_cycles(lg, lanes, bool(reverse))
            # Every edge at small N exercises background clear/read/response,
            # active-bank changes, exposed waits and final pipeline drain.
            for phase, op, inv in ((1,0,0), (2,0,1), (0,2,0), (3,2,0), (0,1,0), (0,3,0)):
                # Each exhaustive operation sweep has its own unchanged 180s
                # bound; profile reuploads dominate wide-lane reset testing.
                lines = [str(lg), f"ORDER {reverse}"]
                limit = transform+(point if inv else 0) if op == 0 else point+(min(4,(n+lanes-1)//lanes)*min(lanes,n)+4 if op == 2 else 0)
                for when in range(1, limit):
                    emit("PROFILE", words); emit("LOAD", values)
                    lines += [f"PHASE {phase}", f"ABORT_AT {op} {inv} {r} {when}", f"REJECT {lg} 0 1"]
                emit("PROFILE", words); emit("LOAD", values)
                lines += ["PHASE 1", "ORDER 1", "RUN 0 0 0"]
                emit("CHECK", bitreverse(dif(values, p, PRIMES[field].generator)))
                self.execute(f"reset-p{field+1}-aw{aw}-d{reverse}-phase{phase}-op{op}-inv{inv}", exe, lines)
        lines = [str(lg)]
        emit("PROFILE", words); emit("LOAD", values)
        lines += ["PHASE 1", "ORDER 1", "RUN 0 0 0"]
        emit("CHECK", bitreverse(dif(values, p, PRIMES[field].generator)))
        self.execute(f"reset-p{field+1}-aw{aw}", exe, lines)

    def prefetch_mutants(self, aw, lanes):
        source = self.root/"rtl/kernel"/(TOP+".sv")
        variants = [
            ("active-bank", "prefetch_bank<=!seed_bank_reg;", "prefetch_bank<=seed_bank_reg;"),
            ("wrong-stage", "1+32'(AW)+32'(next_stage)", "1+32'(AW)+32'(stage_bit)"),
            ("wrong-step", "prefetch_step<=profile_q;", "prefetch_step<=32'd1;"),
            ("stale-response", "seed_tag<=seed_issue;", "seed_tag<=seed_issue+(prefetch_state==PF_LOAD ? 9'd1 : 9'd0);"),
            ("early-ready", "prefetch_state<=PF_LOAD;", "prefetch_state<=PF_READY;"),
        ]
        for name, old, new in variants:
            text = source.read_text(); assert old in text, name
            folder = self.output/("mutant-"+name); folder.mkdir()
            path = folder/source.name; path.write_text(text.replace(old,new))
            exe = self.build_ntt(0, aw, lanes, path)
            command = self.output/f"transform-p1-aw{aw}-n{1<<aw}.txt"
            invocation = ["env", "NTT_SKIP_HOST_FUZZ=1", exe, str(command), str(folder/"dump")]
            result = subprocess.run(invocation, capture_output=True, text=True, timeout=180)
            log = result.stdout+result.stderr; (folder/"result.log").write_text(log)
            passed = result.returncode != 0 and any(word in log for word in ("mismatch", "FAIL", "seed loader error", "prefetch", "timeout"))
            self.report["steps"].append({"name":"mutant-"+name, "passed":passed, "returncode":result.returncode,
                "command":invocation,"mutant_source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                "input_sha256":hashlib.sha256(command.read_bytes()).hexdigest(),
                "replacement":{"old":old,"new":new},"rejection_log":str(folder/"result.log")})
            if not passed: raise RuntimeError("surviving mutant "+name)
            print("mutant-"+name+": PASS", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--aw", type=int, choices=range(1,17), default=10)
    ap.add_argument("--lanes", type=int, choices=(1,2,4,8,16,32,64), default=16)
    ap.add_argument("--fields", type=int, choices=(1,3), default=1)
    ap.add_argument("--mutants", action="store_true")
    args = ap.parse_args()
    if socket.gethostname() != "aethia": raise RuntimeError("simulation only on aethia")
    if args.mutants and (args.aw < 10 or args.fields != 1): ap.error("mutants require AW>=10 and --fields 1")
    if args.output.exists(): ap.error("--output must be a new directory; preserve prior evidence")
    resource.setrlimit(resource.RLIMIT_AS, (6<<30, 6<<30))
    lab = PrefetchLab(args.output, "verilator")
    try:
        planes = []; cases = cases_for(args.aw)
        if args.aw == 16: cases.append(("max-base1e9", [999999999]*(1<<args.aw), 1000000000))
        for field in range(args.fields):
            exe = lab.build_ntt(field, args.aw, args.lanes)
            for lg in range(1, args.aw+1):
                lab.transforms(field, args.aw, lg, args.lanes, exe, lg==args.aw)
            planes.append(lab.squares(field,args.aw,args.aw,args.lanes,exe,cases))
            lab.resets(field,args.aw,args.lanes,exe)
            lab.size_reload(field,args.aw,args.lanes,exe)
        if args.fields == 3:
            for i, (_,digits,base) in enumerate(cases):
                coeff = [centered_crt((planes[f][i][j] for f in range(3)),PRIMES) for j in range(1<<args.aw)]
                modulus = pow(base,1<<args.aw)+1
                assert encode(coeff,base)%modulus == pow(encode(digits,base),2,modulus)
            lab.report["whole_integer_crt"] = True
        if args.mutants: lab.prefetch_mutants(args.aw,args.lanes)
        for path, digest in lab.report["source_sha256"].items():
            if hashlib.sha256((lab.root/path).read_bytes()).hexdigest() != digest:
                raise RuntimeError("source changed during gate: "+path)
        lab.report["source_hashes_rechecked"] = True
        lab.report["status"] = "passed"
    except Exception as exc:
        lab.report["status"] = "failed"
        lab.report["failure"] = str(exc)
        raise
    finally:
        (lab.output/"report.json").write_text(json.dumps(lab.report,indent=2)+"\n")

if __name__ == "__main__": main()
