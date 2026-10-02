"""Compare sparse RTL with existing independently generated Montgomery vectors.

Runs only on aethia. Keeps frozen helper and its original regression unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import socket
import subprocess

from .montgomery27_regression import FIELDS


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vectors", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--mutations", action="store_true")
    args = ap.parse_args()
    if socket.gethostname() != "aethia":
        raise RuntimeError("aethia only")
    root = Path(__file__).resolve().parents[1]
    rtl = root / "rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv"
    cpp = root / "rtl/tb/montgomery27_pipe.cpp"
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "running", "sources": {}, "steps": [], "identity_checks": 0}
    for p in (rtl, cpp, Path(__file__), root / "reference/montgomery27_regression.py"):
        report["sources"][str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()

    def run(name, command, rejection=None):
        r = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=180)
        (out / (name + ".log")).write_text(r.stdout)
        report["steps"].append({"name": name, "command": command,
                                "returncode": r.returncode, "expected_rejection": rejection})
        print(name, r.returncode, r.stdout[-300:], flush=True)
        if rejection is None:
            if r.returncode:
                raise RuntimeError(name + " failed")
        elif r.returncode == 0 or not any(s in r.stdout for s in rejection):
            raise RuntimeError(name + " did not reject the intended defect")

    def build(name, p, q, source=rtl):
        directory = out / ("build-" + name)
        run("build-" + name, ["verilator", "--cc", "--exe", "--build", "-j", "2",
            "--top-module", "genefer_montgomery_mul27_sparse_pipe",
            "--prefix", "Vgenefer_montgomery_mul27_pipe", "--Mdir", str(directory),
            f"-GP={p}", f"-GQ={q}", str(source), str(cpp)])
        return str(directory / "Vgenefer_montgomery_mul27_pipe")

    try:
        rng = random.Random(0x535041525345)
        for (p, q), shift in zip(FIELDS, (25, 21, 17)):
            extra = (1 << 22) if p == 104857601 else 0
            assert p == 1 + (1 << 26) + (1 << shift) + extra
            assert q == (2 - p) % (1 << 32)
            assert (p - 1)**2 % (1 << 32) == 0
            for v in [0, 1, (1 << 32)-1, *[rng.randrange(1 << 32) for _ in range(10000)]]:
                assert (v-(v << 26)-(v << shift)-v*extra) % (1 << 32) == v*q % (1 << 32)
                assert v+(v << 26)+(v << shift)+v*extra == v*p < 1 << 59
                report["identity_checks"] += 1
            vectors = args.vectors.resolve() / f"vectors-{p}.txt"
            report["sources"][str(vectors)] = hashlib.sha256(vectors.read_bytes()).hexdigest()
            exe = build(str(p), p, q)
            run(f"test-{p}", [exe, str(vectors), str(p)])
            for name, x, y in [("lhs-P",p,1), ("rhs-P",1,p),
                               ("wide-lhs",1 << 27,1), ("wide-rhs",1,0xffffffff)]:
                run(f"reject-{name}-{p}", [exe,"reject",str(p),str(x),str(y)],
                    ["noncanonical Montgomery27 input"])
            if args.mutations:
                defects = [
                    ("q-shift", "m_s2<=lo-(lo<<26)-(lo<<S)-extra_q;", "m_s2<=lo-(lo<<26)-extra_q;"),
                    ("p-shift", "mp_s3<=m_ext+(m_ext<<26)+(m_ext<<S)+extra_p;", "mp_s3<=m_ext+(m_ext<<26)+extra_p;"),
                    ("wide-m", "{27'b0,m_s2}", "{32'b0,m_s2[26:0]}"),
                    ("negative", "hi_s3+P-mp_hi", "hi_s3-mp_hi"),
                    ("latency", "out_valid<=valid_pipe[2]", "out_valid<=valid_pipe[1]"),
                    ("reset", "valid_pipe<='0", "valid_pipe<='1"),
                ]
                if extra:
                    defects.append(("p1-extra", "-extra_q;", ";"))
                for name, old, new in defects:
                    source = rtl.read_text()
                    assert source.count(old) == 1, name
                    mutant = out / f"mutant-{name}-{p}.sv"
                    mutant.write_text(source.replace(old, new))
                    report["sources"][str(mutant)] = hashlib.sha256(mutant.read_bytes()).hexdigest()
                    exe = build(f"{name}-{p}", p, q, mutant)
                    run(f"reject-mutant-{name}-{p}", [exe,str(vectors),str(p)],
                        ["Montgomery arithmetic mismatch", "valid/latency mismatch",
                         "invalid-cycle result hold mismatch"])
        for name,p,q,error in [("unsupported",3,2863311531,"unsupported sparse Montgomery27 modulus"),
                               ("inverse",FIELDS[0][0],FIELDS[0][1]^2,"invalid sparse Montgomery inverse")]:
            exe=build(name,p,q)
            run("reject-"+name,[exe,"reject",str(p)],[error])
        report["status"] = "passed"
    except BaseException as exc:
        report.update(status="failed", error=repr(exc))
        raise
    finally:
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
