"""Prepare/run A10 full-N SOFTWARE gate. No HDL build, native compile, fit or SSH.

Run is host-gated to aethia and source-gated by an explicitly supplied manifest
hash. The main coordinator owns later dispatch. Small source tests run locally.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import platform
import resource
import sys
import time

FILES = ("reference/__init__.py", "reference/merged_negacyclic27_model.py",
         "reference/stream_ntt_model.py", "reference/core27_prefill_aw16_offline_review.py",
         "tests/test_merged_negacyclic27_model.py",
         "tools/run_merged_negacyclic27_software_gate.py",
         "rtl/kernel/genefer_ntt_banked27_engine.sv",
         "rtl/kernel/genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine.sv",
         "rtl/kernel/genefer_root_profile27_r2_rom.sv",
         "rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill.sv",
         "rtl/kernel/genefer_crt3_27_mont_pipe.sv")
VECTOR = "results/throughput-20260929/core27-prefill-aw16-normal-v1/vectors.txt"
VECTOR_SHA = "3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d"
FAULTS = ("forward-inverse-root", "inverse-forward-root", "wrong-root-index",
          "natural-spectrum", "ordinary-root", "r2-first-stage",
          "missing-normalization", "normalization-r", "upper-unscaled")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pins(root):
    out = {}
    for name in (*FILES, VECTOR):
        path = root / name
        need(not path.is_symlink() and path.resolve().is_relative_to(root), "source path escape/link")
        out[name] = sha(path)
    need(out[VECTOR] == VECTOR_SHA, "frozen AW16 vector identity")
    return out


def prepare(root):
    need(not (root / "docs/briefs/PAUSE").exists(), "briefs/PAUSE exists")
    return dict(status="prepared_not_executed", profile="merged-negacyclic27-ctgs-ordinary-v1",
                kind="full-N Python software arithmetic comparison", sources=pins(root),
                vectors=VECTOR, vectors_sha256=VECTOR_SHA, n=65536, cases=12,
                fields=3, expected_readback_commands=10,
                max_memory_bytes=6*(1 << 30), timeout_seconds=1200,
                requested_physical_cores=2,
                gates=["all 12 AW16 residues vs current bit-exact R2 parent in all fields",
                       "all 12 AW16 carry outputs vs existing frozen vectors",
                       "independent whole-integer replay of those vectors",
                       "nine typed small-N mutants with fresh controls in each field"],
                exclusions=["no HDL/native simulation", "no timing/port/root-schedule proof",
                            "no resource fit or cycle record", "no profile adoption"])


def run(root, manifest_path, manifest_sha, output):
    need(platform.system() == "Linux" and platform.node() == "aethia", "run on aethia only")
    need(not (root / "docs/briefs/PAUSE").exists(), "briefs/PAUSE exists")
    need(manifest_sha and sha(manifest_path) == manifest_sha, "approved manifest identity")
    manifest = json.loads(manifest_path.read_text())
    need(manifest == prepare(root), "closed manifest/source/plan changed")
    output.mkdir(parents=True, exist_ok=False)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (6*(1 << 30), 6*(1 << 30)))
    resource.setrlimit(resource.RLIMIT_CPU, (1200, 1200))
    sys.path.insert(0, str(root))
    m = importlib.import_module("reference.merged_negacyclic27_model")
    frozen = importlib.import_module("reference.stream_ntt_model")
    independent = importlib.import_module("reference.core27_prefill_aw16_offline_review")
    started = time.monotonic()
    report = dict(status="running", profile=m.PROFILE, manifest_sha256=manifest_sha,
                  evidence_class="Python software arithmetic only", sources=manifest["sources"],
                  host=platform.node(), python=sys.version, cases=[], negative_controls=[],
                  cycle_model=m.cycle_work(), exclusions=manifest["exclusions"])
    try:
        _, coverage = independent.vector_oracle((root / VECTOR).read_text())
        report["independent_vector_coverage"] = coverage
        for case in frozen.normal_cases(root / VECTOR):
            need(len(case["digits"]) == 65536, "full AW16 frame required")
            planes = []
            for field in m.FIELDS:
                candidate = m.field_square(case["digits"], field)
                parent = m.current_parent_square(case["digits"], field)
                m.compare(candidate, parent, "full-residue:" + case["name"])
                planes.append(candidate)
            coefficients = []
            for row in zip(*planes):
                value = sum(r*w for r, w in zip(row, m.CRT_WEIGHTS)) % m.MODULUS
                coefficients.append((value-m.MODULUS if value > m.HALF else value)*(1 << case["double_bit"]))
            actual = frozen.exact_carry(coefficients, case["base"])
            m.compare(actual, case["expected"], "full-vector:" + case["name"])
            report["cases"].append(dict(name=case["name"], base=case["base"], fields=3,
                                        double_bit=case["double_bit"], residues_checked=3*65536,
                                        digits_checked=65536, status="passed"))
            print("passed " + case["name"], flush=True)
        need(len(report["cases"]) == manifest["cases"], "exact 12-case coverage")
        digits = [(i*7919+37) % 104857601 for i in range(32)]
        expected = m.direct_coefficients(digits)
        for field in m.FIELDS:
            residues = [x % field.p for x in expected]
            for fault in FAULTS:
                m.compare(m.field_square(digits, field), residues, "fresh-control")
                try:
                    m.compare(m.field_square(digits, field, mutant=fault), residues, fault)
                except m.Mismatch as error:
                    need(error.kind == fault, "typed negative control mismatch")
                else:
                    raise ValueError("mutant escaped: " + fault)
                report["negative_controls"].append(dict(field=field.p, fault=fault, status="detected"))
        need(pins(root) == manifest["sources"], "post-run source drift")
        report["status"] = "passed_software_arithmetic_only"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic()-started
        (output / "receipt.json").write_text(json.dumps(report, indent=2)+"\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.prepare:
        need(not args.manifest and not args.manifest_sha, "prepare has no run arguments")
        need(not args.output.exists(), "fresh manifest path required")
        args.output.write_text(json.dumps(prepare(root), indent=2)+"\n")
    else:
        need(args.manifest is not None, "explicit manifest required")
        run(root, args.manifest, args.manifest_sha, args.output)


if __name__ == "__main__":
    main()
