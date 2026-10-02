"""Offline verification of a completed full replay receipt and copied artifacts.

No simulation, model build, old-tree write, or source extraction. Copy the entire
fresh output tree except *.gch. Retained P1 diagnostic is independently pinned.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

if __package__:
    from . import ntt27_prefetch_full_replay as gate
else:
    import ntt27_prefetch_full_replay as gate

RUNNER_SHA="38dd04e30a7fd7ce9d26b387407566f848b1534581828804008cc1da0d368675"
RTL_PINS={
    "genefer_montgomery_mul27_sparse_pipe.sv":"501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b",
    "genefer_sdp_ram32.sv":"993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0",
    "genefer_sp_ram.sv":"b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df",
    "genefer_root_recurrence27.sv":"c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e",
    "genefer_ntt_banked27_engine.sv":"7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9",
    gate.TOP+".sv":gate.CANDIDATE_SHA,"genefer_sdp_ram27_residue.sv":gate.LEAF_SHA}

def structure(report,manifest):
    executables={(row["field"],row["kind"]):row for row in report["executables"]}
    expected={(field,kind) for field in (1,2,3) for kind in ("baseline","candidate")}
    assert len(report["executables"])==6 and set(executables)==expected,"duplicate/missing executable fields"
    profiles=report["actual_build_profiles"]
    assert len(profiles)==3 and {row["field"] for row in profiles}=={1,2,3},"duplicate/missing profiles"
    names=sum((gate.base.expected_cases(field) for field in (1,2,3)),[])
    vectors={row["name"]:row for row in manifest["cases"]}
    assert len(manifest["cases"])==93 and set(vectors)==set(names),"duplicate/missing vector cases"
    steps={row["name"]:row for row in report["steps"]}
    assert len(steps)==len(report["steps"]),"duplicate steps"
    out=Path(report["source_archive"]["path"]).parent
    for case in manifest["cases"]:
        name=case["name"];field=case["field"]
        assert name in gate.base.expected_cases(field)
        assert case["vector"]==str(gate.base.OLD_GATE/(name+".txt")),"unexpected vector path"
        assert manifest["input_sha256"][case["vector"]]==case["sha256"]
        assert case["host_fuzz"]==(name==f"transform-p{field}-aw16-n65536"),"host fuzz contract"
        for kind in ("baseline","candidate"):
            expected_argv=[] if case["host_fuzz"] else ["env","NTT_SKIP_HOST_FUZZ=1"]
            expected_argv += [executables[field,kind]["path"],case["vector"],str(out/f"{name}-{kind}-dump.txt")]
            assert steps[name+"-"+kind]["command"]==expected_argv,"normal argv/executable/fuzz mismatch"
    for field,kind in expected:
        for mode in ("scalar","vector","scalar-high","vector-high"):
            name=f"fault-p{field}-{kind}-{mode}"
            argv=["env","NTT_NONCANON="+mode,executables[field,kind]["path"],
                str(gate.base.OLD_GATE/f"transform-p{field}-aw16-n2.txt"),str(out/(name+"-dump.txt"))]
            assert steps[name]["command"]==argv,"fault mode/executable mismatch"
    return executables

def digest(data):return hashlib.sha256(data).hexdigest()

def verify(root,p1,vector_receipt):
    root=root.resolve();report=json.loads((root/"report.json").read_text())
    assert report["status"]=="passed" and report["inputs_rehashed_after"] and report["whole_integer_crt"]
    assert report["runner_sha256"]==RUNNER_SHA
    assert gate.base.sha(root/"manifest.json")==report["manifest_sha256"]
    manifest=json.loads((root/"manifest.json").read_text())
    structure(report,manifest)
    assert gate.base.sha(vector_receipt)==gate.VECTOR_SHA
    source_vectors=json.loads(vector_receipt.read_text())
    assert source_vectors["status"]=="passed" and source_vectors["case_count"]==93
    assert {row["name"]:(row["sha256"],row["host_fuzz"]) for row in source_vectors["cases"]}=={row["name"]:(row["sha256"],row["host_fuzz"]) for row in manifest["cases"]}
    assert report["build_profile"]=={"OPT_FAST":"-Os","OPT_SLOW":"","OPT_GLOBAL":"-Os","model_threads":1}
    assert report["limits"]["cpu_quota_cores"]<=2 and report["limits"]["memory_limit_bytes"]<=4*gate.GiB
    for relative,expected in report["artifact_sha256"].items():
        path=root/relative
        assert not Path(relative).is_absolute() and path.resolve().is_relative_to(root)
        assert gate.base.sha(path)==expected,relative
    archive=root/Path(report["source_archive"]["path"]).name
    assert gate.base.sha(archive)==report["source_archive"]["sha256"]
    with tarfile.open(archive) as tar:
        members=report["source_archive"]["member_sha256"]
        assert len(tar.getmembers())==len(members) and set(tar.getnames())==set(members)
        for name,expected in members.items():
            assert tar.getmember(name).isfile()
            assert digest(tar.extractfile(name).read())==expected,name
            original="/"+name.removeprefix("inputs/")
            assert manifest["input_sha256"][original]==expected,"archive/manifest mismatch"
        source_pins={**RTL_PINS,"ntt27_prefetch_full_replay.py":RUNNER_SHA,
            "ntt27_prefetch_relink.py":gate.HELPER_SHA,
            "ntt_banked27_prefetch_data27_engine.cpp":gate.base.NEW_BENCH_SHA}
        for basename,expected in source_pins.items():
            matching=[name for name in members if Path(name).name==basename]
            assert matching,"missing pinned source: "+basename
            assert all(digest(tar.extractfile(name).read())==expected for name in matching),basename
    steps={step["name"]:step for step in report["steps"]}
    assert len(steps)==len(report["steps"])
    expected_names={f"build-candidate-p{field}" for field in (1,2,3)}
    expected_names|={f"{operation}-p{field}" for field in (2,3) for operation in ("reproduce","compile-bench","link-diagnostic")}
    expected_names|={f"whole-integer-{kind}" for kind in ("baseline","candidate")}
    names=sum((gate.base.expected_cases(field) for field in (1,2,3)),[])
    expected_names|={f"{name}-{kind}" for name in names for kind in ("baseline","candidate")}
    fault_names={f"fault-p{field}-{kind}-{mode}" for field in (1,2,3) for kind in ("baseline","candidate") for mode in ("scalar","vector","scalar-high","vector-high")}
    expected_names|=fault_names
    assert set(steps)==expected_names and len(steps)==221
    for name,step in steps.items():
        assert step["passed"] and step["failure"] is None,name
        log=root/(name+".log")
        assert gate.base.sha(log)==step["log_sha256"]
        assert gate.base.sha(root/(name+".metrics"))==step["metrics_sha256"]
        if name in fault_names:
            expected=["noncanonical NTT27 data write"]
            if "-candidate-" in name and name.endswith("-high"):expected.append("RAM residue write exceeds27 bits")
            assert step["expected_rejections"]==expected and step["returncode"]!=0
            assert any(reason in log.read_text() for reason in expected)
        else:assert step["returncode"]==0 and not step["expected_rejections"]
    matches={row["name"]:row for row in report["matched_cases"]}
    vectors={row["name"]:row for row in manifest["cases"]}
    assert set(matches)==set(names) and len(report["matched_cases"])==93
    for name,row in matches.items():
        assert row["sha256"]==vectors[name]["sha256"]
        assert row["host_fuzz"]==vectors[name]["host_fuzz"]
        paths=[root/f"{name}-{kind}.log" for kind in ("baseline","candidate")]
        paths+=[root/f"{name}-{kind}-dump.txt" for kind in ("baseline","candidate")]
        actual=gate.equal_pair(*paths)
        assert row["exact_stdout_and_dump"] and all(row[key]==value for key,value in actual.items())
    expected_math={"whole_integer_crt":True,"cases":["base2","recurrent0","recurrent1","max-base1e9"]}
    for kind in ("baseline","candidate"):
        assert json.loads((root/f"whole-integer-{kind}.log").read_text())==expected_math
    assert gate.base.sha(p1)==gate.P1_EXE_SHA
    assert len(report["executables"])==6
    for row in report["executables"]:
        field=row["field"]
        local=(p1 if field==1 else root/f"relink-p{field}/baseline-diagnostic") if row["kind"]=="baseline" else root/f"build-candidate-p{field}"/gate.base.PREFIX
        assert gate.base.sha(local)==row["sha256"]
        remote_root=Path(report["source_archive"]["path"]).parent
        expected_remote=(Path("/home/jtl/gfn-fpga-lab/agent-work/ntt27-prefetch-data27/relink-review-v2/fpga/artifacts/p1-v2/baseline-diagnostic") if field==1 else remote_root/f"relink-p{field}/baseline-diagnostic") if row["kind"]=="baseline" else remote_root/f"build-candidate-p{field}"/gate.base.PREFIX
        assert row["path"]==str(expected_remote),"unexpected recorded model path"
    for field in (2,3):assert gate.base.sha(root/f"relink-p{field}/original-reproduced")==gate.base.OLD_EXE_SHAS[field-1]
    assert len(report["actual_build_profiles"])==3
    for profile in report["actual_build_profiles"]:
        field=profile["field"];directory=root/f"build-candidate-p{field}"
        actual=gate.verify_build_profile(directory,root/f"build-candidate-p{field}.log",field)
        assert actual["actual_compile_commands"]==profile["actual_compile_commands"]
        assert actual["model_threads"]==profile["model_threads"]==1
        assert {Path(path).name:sha for path,sha in actual["generated_source_sha256"].items()}=={Path(path).name:sha for path,sha in profile["generated_source_sha256"].items()}
    return {"status":"verified","report_sha256":gate.base.sha(root/"report.json"),
        "artifact_count":len(report["artifact_sha256"]),"source_archive_members":len(members),
        "strict_pairs":93,"faults":24,"steps":221,"whole_integer_receipts":2,
        "scope":"Offline hashes, raw equality, compile-profile checks and math-receipt validation; no fresh simulation or independent re-execution of whole-integer math"}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("root",type=Path)
    parser.add_argument("--p1",required=True,type=Path)
    parser.add_argument("--vector-receipt",required=True,type=Path);args=parser.parse_args()
    if not __debug__:raise RuntimeError("assertions required")
    print(json.dumps(verify(args.root,args.p1,args.vector_receipt),indent=2))

if __name__=="__main__":main()
