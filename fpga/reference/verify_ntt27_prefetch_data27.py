"""Verify a saved data27 gate against its archived source/log/vector snapshot."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(root,output,executables=False):
    report_path=output/"report.json";report=json.loads(report_path.read_text())
    assert report["status"]=="passed" and report["source_hashes_rechecked"]
    assert report["whole_integer_crt"]
    for name,digest in report["source_sha256"].items():assert sha(root/name)==digest,name
    for row in report["steps"]:
        assert row["passed"],row["name"]
        assert sha(output/(row["name"]+".log"))==row["log_sha256"],row["name"]
        if "measurements" in row:
            assert sha(output/(row["name"]+".metrics"))==row["measurements"]["metrics_sha256"]
    counts={"runs":0,"checks":0,"aborts":0}
    for row in report["matched_cases"]:
        name=row["name"]
        assert sha(output/(name+".txt"))==row["input_sha256"]
        for kind in ("candidate","parent"):
            log=output/(name+"-"+kind+".log")
            assert sha(log)==row["stdout_sha256"]
            assert sha(output/(name+"-"+kind+"-dump.txt"))==row["dump_sha256"]
        assert row["cycle_counter_output_equal"]
        summary=re.findall(r"PASS runs=(\d+) checks=(\d+) aborts=(\d+)",log.read_text())
        assert len(summary)==1
        for key,value in zip(counts,summary[0]):counts[key]+=int(value)
    if executables:
        for row in report["executables"]:assert sha(Path(row["path"]))==row["sha256"],row["path"]
    return {"status":"verified","report_sha256":sha(report_path),
        "source_files":len(report["source_sha256"]),"steps":len(report["steps"]),
        "matched_cases":len(report["matched_cases"]),"per_design_totals":counts,
        "executables_rehashed":len(report["executables"]) if executables else 0}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True);ap.add_argument("--executables",action="store_true")
    args=ap.parse_args();print(json.dumps(verify(args.root,args.output,args.executables),indent=2))

if __name__=="__main__":main()
