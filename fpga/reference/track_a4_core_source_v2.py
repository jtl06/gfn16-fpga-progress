"""Exact additive removal of destination-fault combinational feedback.

Destination error is sampled into sticky bridge error. It must not gate the
outgoing request combinationally: sequencer block_error contains start+request,
while start depends on bridge quiet. Destination writes remain proposals; the
outer CHECK edge observes the sticky error before publishing eligibility.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TICKET = "docs/briefs/replies/2026-10-01-B20260930A-A4-core-exploratory-ticket-v1.json"
TICKET_SHA = "c8b266c6edc05d57cff60802703e598145926157058f235c64914f53f801bafc"
TRANSFORMS = {
    "rtl/kernel/genefer_track_a4_field_transfer_v1.sv": (
        ("genefer_track_a4_field_transfer_v1", "genefer_track_a4_field_transfer_v2"),
        ("!cancel && !error && !field_error && !protocol_fault", "!cancel && !error && !protocol_fault")),
    "rtl/kernel/genefer_track_a4_square_backend_v1.sv": (
        ("genefer_track_a4_square_backend_v1", "genefer_track_a4_square_backend_v2"),
        ("genefer_track_a4_field_transfer_v1", "genefer_track_a4_field_transfer_v2")),
    "rtl/kernel/genefer_track_a4_core_v1.sv": (
        ("genefer_track_a4_core_v1", "genefer_track_a4_core_v2"),
        ("genefer_track_a4_square_backend_v1", "genefer_track_a4_square_backend_v2")),
    "rtl/tb/track_a4_core_v1.cpp": (("genefer_track_a4_core_v1", "genefer_track_a4_core_v2"),),
}


def successor(parent, text):
    for before, after in TRANSFORMS[parent]:
        assert before in text
        text = text.replace(before, after)
    return text


def verify(root=ROOT):
    raw = (root/TICKET).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == TICKET_SHA
    pins = json.loads(raw)["source_sha256"]
    for parent in TRANSFORMS:
        raw = (root/parent).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == pins[parent]
        child = parent.replace("_v1.", "_v2.")
        assert (root/child).read_text() == successor(parent, raw.decode())
    bridge = (root/"rtl/kernel/genefer_track_a4_field_transfer_v2.sv").read_text()
    assert "else if(field_error || protocol_fault || error)" in bridge
    assert "request_read<=0;request_write<=0;response_valid<=0;read_due<=0;error<=1;" in bridge
    return {"exact_successors": 4, "destination_fault_sticky": True, "predecessor_ticket": TICKET_SHA}
