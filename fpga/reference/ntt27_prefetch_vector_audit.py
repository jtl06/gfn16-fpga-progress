"""Regenerate the frozen full64 vector suite without building/running models.

Current vector files are fresh hash pins, not historical hashes. Exact in-memory
regeneration from the old report's pinned reference closure closes that gap.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys

MANIFEST_SHA="00891a4d5a4f7fc10594132e9ee5dc195f96834d19b2d74673e8763c89c9e63b"
OLD_ROOT=Path("/home/jtl/gfn-fpga-lab/agent-work/ntt27-prefetch/fpga")

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--manifest",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path);args=ap.parse_args()
    if socket.gethostname()!="aethia":raise RuntimeError("audit restricted to aethia")
    if not __debug__:raise RuntimeError("Python assertions disabled")
    if args.output.exists():ap.error("fresh output required")
    assert sha(args.manifest)==MANIFEST_SHA
    manifest=json.loads(args.manifest.read_text())
    def recheck():
        for path,digest in manifest["input_sha256"].items():assert sha(path)==digest,path
    recheck()
    # Do not create __pycache__ files in the retained reference tree.
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(OLD_ROOT))
    from reference.ntt27_prefetch_regression import PrefetchLab
    from reference.ntt27_generated_regression import PRIMES
    from reference.ntt_cached_regression import cases_for,encode
    from reference.rns_reference import centered_crt

    class AuditLab(PrefetchLab):
        def __init__(self):
            self.expected={row["name"]:row for row in manifest["cases"]}
            self.seen=set();self.rows=[]
        def run(self,*args,**kwargs):raise RuntimeError("model execution prohibited in vector audit")
        def build_ntt(self,*args,**kwargs):raise RuntimeError("model compilation prohibited in vector audit")
        def execute(self,name,exe,lines,fuzz=False):
            assert name in self.expected and name not in self.seen,name
            row=self.expected[name]
            serialized=("\n".join(lines)+"\n").encode()
            digest=hashlib.sha256(serialized).hexdigest()
            assert digest==row["sha256"],"source-derived vector mismatch: "+name
            assert sha(row["vector"])==digest and fuzz==row["host_fuzz"],name
            # GeneratedLab.squares expects execute() to return DUMP residues.
            # Return its independent preceding CHECK oracle, never a model.
            dumped=[]
            for i,line in enumerate(lines):
                if line=="DUMP":
                    assert i>0 and lines[i-1].startswith("CHECK\n")
                    dumped.extend(map(int,lines[i-1].split("\n",1)[1].split()))
            self.rows.append({"name":name,"sha256":digest,"bytes":len(serialized),"host_fuzz":fuzz})
            self.seen.add(name)
            print(name+": exact source-derived match",flush=True)
            return dumped

    result={"status":"failed","scope":"source-derived vector equivalence; no model compilation or execution"}
    lab=AuditLab()
    try:
        cases=cases_for(16)+[("max-base1e9",[999999999]*65536,1000000000)]
        planes=[]
        for field in range(3):
            for lg in range(1,17):lab.transforms(field,16,lg,64,"NO_MODEL",lg==16)
            planes.append(lab.squares(field,16,16,64,"NO_MODEL",cases))
            lab.resets(field,16,64,"NO_MODEL")
            lab.size_reload(field,16,64,"NO_MODEL")
        assert lab.seen==set(lab.expected) and len(lab.seen)==93
        for i,(_,digits,base) in enumerate(cases):
            coeff=[centered_crt((planes[f][i][j] for f in range(3)),PRIMES) for j in range(65536)]
            modulus=pow(base,65536)+1
            assert encode(coeff,base)%modulus==pow(encode(digits,base),2,modulus)
        recheck()
        result.update(status="passed",cases=lab.rows,case_count=93,
            serialized_vector_bytes=sum(row["bytes"] for row in lab.rows),
            full_square_cases=[name for name,_,_ in cases],whole_integer_crt=True,
            input_hashes_rechecked=True,historical_binding="Source-derived exact regeneration, not historical vector hashes")
    except Exception as exc:result["failure"]=str(exc);raise
    finally:
        result["manifest_sha256"]=sha(args.manifest);result["runner_sha256"]=sha(Path(__file__))
        args.output.write_text(json.dumps(result,indent=2)+"\n")
    print("PASS: all93 source-derived vectors; four whole-integer cases; no model execution",flush=True)

if __name__=="__main__":main()
