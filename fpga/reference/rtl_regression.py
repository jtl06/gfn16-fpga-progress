"""Bounded, simulation-only regression and provenance report. Run on Linux.

This is a development test runner, not the future untrusted-candidate sandbox
or hardware admission broker. It deliberately invokes no vendor FPGA tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .rtl_vectors import write_vectors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--output", type=Path, default=Path("artifacts/regression"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    build = output / "build"
    seeds = [0x47464E16, 1, 0xDEADBEEF]
    report: dict = {
        "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "verilator_root": os.environ.get("VERILATOR_ROOT"),
        "scope": "simulation only; no timing, fit, full RTL NTT or primality claim",
        "seeds": seeds,
        "steps": [],
        "source_sha256": {},
    }
    sources = [root / "Makefile"]
    for folder in ("reference", "tests", "autolab", "rtl", "config", "vectors"):
        sources.extend(p for p in (root / folder).rglob("*")
                       if p.is_file() and "__pycache__" not in p.parts)
    report["source_sha256"] = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(sources)
    }

    def run(name: str, command: list[str], *, reject: str | None = None) -> None:
        result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=120, check=False)
        (output / f"{name}.log").write_text(result.stdout, encoding="utf-8")
        passed = result.returncode == 0 if reject is None else (
            result.returncode == 1 and reject in result.stdout)
        report["steps"].append({"name": name, "command": command,
                                "returncode": result.returncode, "passed": passed,
                                "expected_rejection": reject})
        print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)
        if not passed:
            raise RuntimeError(f"{name} failed; see {output / (name + '.log')}")

    try:
        run("verilator-version", [args.verilator, "--version"])
        run("python-reference", ["make", "verify", "full-check"])
        make = ["make", f"VERILATOR={args.verilator}", f"RTL_BUILD={build}"]
        run("rtl-baseline", make + ["rtl-baseline"])
        run("rtl-stream-build", make + ["rtl-check", f"RTL_SEED={seeds[0]}"])
        executable = str(build / "obj" / "Vgenefer_arithmetic_top")
        for seed in seeds:
            vectors = output / f"vectors-{seed:x}.txt"
            count = write_vectors(vectors, seed)
            if count != 13317:
                raise RuntimeError("unexpected vector count")
            run(f"rtl-stream-{seed:x}", [executable, str(vectors)])
        lines = (output / f"vectors-{seeds[0]:x}.txt").read_text().splitlines()
        bad = lines.copy()
        row = bad[-1].split()
        row[4] = str(int(row[4]) ^ 1)
        bad[-1] = " ".join(row)
        negative_cases = {
            "corrupt-multiply": (bad, "baseline value mismatch"),
            "missing-vector": (lines[:-1], "incomplete vector set"),
            "partial-row": (lines[:-1] + ["0 1 2"], "malformed vector row"),
        }
        bad_butterfly = lines.copy()
        row = bad_butterfly[-1].split()
        row[5] = str(int(row[5]) ^ 1)
        bad_butterfly[-1] = " ".join(row)
        negative_cases["corrupt-butterfly"] = (bad_butterfly, "butterfly value mismatch")
        for name, (content, rejection) in negative_cases.items():
            path = output / f"negative-{name}.txt"
            path.write_text("\n".join(content) + "\n", encoding="ascii")
            run(f"negative-{name}", [executable, str(path)], reject=rejection)
        report["status"] = "pass"
    except Exception as error:
        report["status"] = "fail"
        report["error"] = str(error)
        raise
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Report: {output / 'report.json'}")


if __name__ == "__main__":
    main()
