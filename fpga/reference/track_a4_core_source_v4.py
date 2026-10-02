"""Isolated registered NTT admission boundary after A4 P4 routed control failure.

The raw field-transfer quiet predicate may depend on image legality. Capture
that authority, then launch one edge later from a preserved token. Only already
registered child faults and external cancel/busy-begin can suppress launch;
raw ownership faults still reject transfers immediately and fail the operation
at the edge, but must not reconnect to the high-fanout start signal.
"""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PINS={
 'rtl/kernel/genefer_track_a4_square_backend_v3.sv':'3421d1b1524a70f9a5b2a432ebd2b3e4dcfa0f36a65c8b17f4aaf25c0f9eebfe',
 'rtl/kernel/genefer_track_a4_core_v3.sv':'29df85aec98243719f00fa0b30f846210b56f0fc23431b3ef22f9a0061701eee',
 'rtl/tb/track_a4_core_v3.cpp':'5b9d284578286c95b153c9594a765f36d44c99b1ab9c3b3740dec46689bca8b9',
}
TRANSFORMS={
 'rtl/kernel/genefer_track_a4_square_backend_v3.sv':(
  ('genefer_track_a4_square_backend_v3','genefer_track_a4_square_backend_v4'),
  ('DRAIN,CHECK,FAILED} state_t;','DRAIN,CHECK,FAILED,NTT_LAUNCH} state_t;'),
  ('    logic admission_error;','''    logic admission_error;
    // r17: one registered admission edge isolates raw image legality from
    // start's global field-RAM gate. Owned by this operation's latched config.
    (* preserve, dont_merge *) logic ntt_admission;'''),
  ('assign compute_configure=state==NTT_START && !was_prefilled && !fault && !cancel;',
   'assign compute_configure=start_ntt && !was_prefilled;'),
  ('    wire start_ntt=state==NTT_START && seq_ready && transfer_quiet && !fault && !cancel;',
   '''    wire admit_ntt=state==NTT_START && seq_ready && transfer_quiet && !fault && !cancel;
    // No transfer_quiet, seq_ready, raw child valid or raw admission fault here.
    wire start_ntt=ntt_admission && !fault && !cancel;'''),
  ('image_boundary_valid<=0;admission_error<=0;','image_boundary_valid<=0;admission_error<=0;ntt_admission<=0;'),
  ('            done<=0;\n            if(raw_admission_fault)',
   '            done<=0;ntt_admission<=0;\n            if(raw_admission_fault)'),
  ('                NTT_START:if(start_ntt)state<=NTT_WAIT;',
   '''                NTT_START:if(admit_ntt)begin ntt_admission<=1;state<=NTT_LAUNCH;end
                NTT_LAUNCH:if(start_ntt)state<=NTT_WAIT;'''),
  ('if(fault || raw_admission_fault)begin state<=FAILED;',
   'if(fault || raw_admission_fault)begin ntt_admission<=0;state<=FAILED;'),
  ('if(cancel)begin admission_error<=0;state<=IDLE;',
   'if(cancel)begin admission_error<=0;ntt_admission<=0;state<=IDLE;'),
 ),
 'rtl/kernel/genefer_track_a4_core_v3.sv':(
  ('genefer_track_a4_core_v3','genefer_track_a4_core_v4'),
  ('genefer_track_a4_square_backend_v3','genefer_track_a4_square_backend_v4'),
 ),
 'rtl/tb/track_a4_core_v3.cpp':(('genefer_track_a4_core_v3','genefer_track_a4_core_v4'),),
}

def successor(parent,text):
    for before,after in TRANSFORMS[parent]:
        assert before in text,(parent,before)
        text=text.replace(before,after)
    return text

def verify(root=ROOT):
    for parent,pin in PINS.items():
        raw=(root/parent).read_bytes();assert hashlib.sha256(raw).hexdigest()==pin
        assert (root/parent.replace('_v3.','_v4.')).read_text()==successor(parent,raw.decode())
    text=(root/'rtl/kernel/genefer_track_a4_square_backend_v4.sv').read_text()
    start=text.split('wire start_ntt=',1)[1].split(';',1)[0]
    assert start=='ntt_admission && !fault && !cancel'
    fault=text.split('wire fault=',1)[1].split(';',1)[0]
    assert all(x not in fault for x in ('prefill_write','post_write','transfer_quiet','input_legal'))
    assert text.index('if(fault || raw_admission_fault)')<text.index('if(cancel)begin admission_error')
    return dict(exact_successors=3,normal_backend_cycle_delta=1,normal_host_cycle_delta=1,
        child_prefill_ntt_post_cycle_delta=0,raw_bad_payload_guard='unchanged',
        control_boundary='admit at E0; sequencer receives registered launch at E1',
        raw_ownership_fault='reject transfers now; failure/cancel children after edge, never gate launch with raw data')

def admission_edge(state,token,*,ready=True,quiet=True,fault=False,raw=False,cancel=False):
    """Small event model of the exact new arm/launch and existing fail priorities."""
    launch=token and not fault and not cancel
    next_token=False
    if state=='NTT_START' and ready and quiet and not fault and not cancel:
        state='NTT_LAUNCH';next_token=True
    elif state=='NTT_LAUNCH' and launch:state='NTT_WAIT'
    if fault or raw:state='FAILED';next_token=False
    if cancel:state='IDLE';next_token=False
    return dict(state=state,token=next_token,launch=launch,
        admitted_transfer=not raw,children_cancel_after=cancel or state=='FAILED')
