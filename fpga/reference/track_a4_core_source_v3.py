"""Exact v2->v3 repair for the native UNOPTFLAT admission/fault loop.

Child write valids cannot feed start_post through a combinational fault term.
Raw ownership violations reject both source transfers, latch admission_error,
and enter FAILED at that edge. Starts use registered faults only. An invalid
child may coincide with a start, but is quarantined/cancelled after that edge;
no image eligibility is published. Ordinary edge counts are unchanged.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TICKET="docs/briefs/replies/2026-10-01-B20260930A-A4-core-exploratory-ticket-v2.json"
TICKET_SHA="ca783103f6378a2909c9fb7b30825688fc7b5a7566f6cdbedfe478627ee8ce6d"
ADMISSION='''    // Starts depend on registered child errors, never child combinational valid.
    // Reject both source requests on ownership/conflict violation; already
    // accepted destination tokens are proposals until the final CHECK edge.
    logic admission_error;
    wire prefill_owner=state==COLD_WAIT;
    wire post_owner=state==POST_WAIT;
    wire raw_admission_fault=(prefill_write && !prefill_owner) ||
        (post_write && !post_owner) ||
        (post_read && state!=NTT_WAIT && state!=POST_WAIT);
    wire admitted_read=post_read && !raw_admission_fault;
    wire admitted_write=(prefill_write || post_write) && !raw_admission_fault;
'''
TRANSFORMS={
    "rtl/kernel/genefer_track_a4_square_backend_v2.sv":(
        ("genefer_track_a4_square_backend_v2","genefer_track_a4_square_backend_v3"),
        ("    wire child_cancel=cancel || state==FAILED;",ADMISSION+"    wire child_cancel=cancel || state==FAILED;"),
        ("(begin_square && state!=IDLE) || (prefill_write && post_write);","(begin_square && state!=IDLE) || admission_error;"),
        (".read_en(post_read),.write_en(prefill_write || post_write)",".read_en(admitted_read),.write_en(admitted_write)"),
        ("image_write_valid<=0;image_boundary_valid<=0;\n        end else begin", "image_write_valid<=0;image_boundary_valid<=0;admission_error<=0;\n        end else begin"),
        ("            done<=0;\n            image_write_valid", "            done<=0;\n            if(raw_admission_fault)admission_error<=1;\n            image_write_valid"),
        ("            if(fault)begin state<=FAILED;", "            if(fault || raw_admission_fault)begin state<=FAILED;"),
        ("            if(cancel)begin state<=IDLE;", "            if(cancel)begin admission_error<=0;state<=IDLE;"),
    ),
    "rtl/kernel/genefer_track_a4_core_v2.sv":(
        ("genefer_track_a4_core_v2","genefer_track_a4_core_v3"),
        ("genefer_track_a4_square_backend_v2","genefer_track_a4_square_backend_v3"),
    ),
    "rtl/tb/track_a4_core_v2.cpp":(("genefer_track_a4_core_v2","genefer_track_a4_core_v3"),),
}


def successor(parent,text):
    for before,after in TRANSFORMS[parent]:
        assert before in text,(parent,before)
        text=text.replace(before,after)
    return text


def verify(root=ROOT):
    raw=(root/TICKET).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==TICKET_SHA
    pins=json.loads(raw)["source_sha256"]
    for parent in TRANSFORMS:
        raw=(root/parent).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==pins[parent]
        assert (root/parent.replace("_v2.","_v3.")).read_text()==successor(parent,raw.decode())
    backend=(root/"rtl/kernel/genefer_track_a4_square_backend_v3.sv").read_text()
    fault=backend.split("    wire fault=",1)[1].split(";",1)[0]
    assert "post_write" not in fault and "prefill_write" not in fault
    assert "admission_error" in fault
    return dict(exact_successors=3,normal_cycle_delta=0,
        invalid_request="reject both source transfers; registered fault at same edge",
        destination_tail="unchanged DRAIN then CHECK; raw admission fault wins CHECK success")
