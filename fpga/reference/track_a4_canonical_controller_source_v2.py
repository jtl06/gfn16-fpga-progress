"""Exact standalone probe successor for the already guarded controller-v2 fix."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TICKET=ROOT/"docs/briefs/replies/2026-10-01-B20260930A-A4-canonical-controller-preparation-v1.json"
TICKET_SHA="80107b91bd03873f5950a9cb72e247b608e933a7ac5bcfc43f74b00e3403d4c1"
CONTROLLER_SHA="f8d8e523ac934dfd3df2b697fe03be14250a584da2aaca761779feaf03f3fbba"


def expected(path):
    if hashlib.sha256(TICKET.read_bytes()).hexdigest()!=TICKET_SHA:raise ValueError("v1 canonical ticket drift")
    pins=json.loads(TICKET.read_text())["source_sha256"]
    text=(ROOT/path).read_text()
    if hashlib.sha256(text.encode()).hexdigest()!=pins[path]:raise ValueError("v1 canonical probe drift")
    new=path.replace("_v1.","_v2.")
    if path.endswith(".sv"):
        for old,replacement,count in (
            ("module track_a4_canonical_controller_probe_v1", "module track_a4_canonical_controller_probe_v2",1),
            ("genefer_track_a4_canonical_controller_v1 #(","genefer_track_a4_canonical_controller_v2 #(",1),
            ("    wire host_access=!busy && !begin_canonical;\n", "    wire host_access=!busy && !begin_canonical;\n    wire [3:0] canonical_request_bank=4'(mem_read_address>>RW);\n    wire [3:0] host_request_bank=4'(host_address>>RW);\n",1),
            ("int'(mem_read_address>>RW)","int'(canonical_request_bank)",1),
            ("int'(host_address>>RW)","int'(host_request_bank)",2),
        ):
            if text.count(old)!=count:raise ValueError("canonical v2 exact delta anchor")
            text=text.replace(old,replacement)
    else:
        if text.count("Vtrack_a4_canonical_controller_probe_v1")!=2:raise ValueError("canonical bench name anchors")
        text=text.replace("Vtrack_a4_canonical_controller_probe_v1","Vtrack_a4_canonical_controller_probe_v2")
    return new,text


def verify():
    controller=ROOT/"rtl/kernel/genefer_track_a4_canonical_controller_v2.sv"
    if hashlib.sha256(controller.read_bytes()).hexdigest()!=CONTROLLER_SHA:raise ValueError("controller v2 drift")
    result={}
    for path in ("rtl/tb/track_a4_canonical_controller_probe_v1.sv","rtl/tb/track_a4_canonical_controller_v1.cpp"):
        new,text=expected(path)
        if (ROOT/new).read_text()!=text:raise ValueError("canonical successor edit beyond exact delta")
        result[new]=hashlib.sha256(text.encode()).hexdigest()
    return result
