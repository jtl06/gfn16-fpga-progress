"""Exact S-M1 commutator delta; source-only queue equivalence accounting."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT='rtl/kernel/genefer_stream27_mdc_commutator_slots_v2.sv'
PARENT_SHA='3484e192967d6295dd6dc7f6a325dfd31e1573a327c881be9f9e10558c458da5'
CHILD='rtl/kernel/genefer_stream27_mdc_commutator_slots_sm1_v1.sv'


def verify(root=ROOT):
    raw=(root/PARENT).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==PARENT_SHA
    expected=raw.decode().replace('genefer_stream27_mdc_commutator_slots_v2','genefer_stream27_mdc_commutator_slots_sm1_v1').replace('genefer_stream27_mdc_fifo_sync','genefer_stream27_mdc_fifo_smallreg_v1')
    assert (root/CHILD).read_text()==expected
    return dict(commutator_control_delta=0,normal_latency_delta=0,fault_latency_delta=0,
        changed='Only FIFO binding and module name; <=32 explicit logic shift chain, >32 frozen helper',
        registered_fault_successor='Not included. Legacy pending-fault behavior preserved for isolated S-M1.')


def pilot_counts():
    random=0x534d31;resets=advances=holds=0
    for edge in range(4096):
        random=(random*6364136223846793005+1442695040888963407)&((1<<64)-1)
        if edge in (0,19,137,1023,3071):resets+=1
        elif random>>62:advances+=1
        else:holds+=1
    return dict(edges=4096,depths=7,head_checks=28672,resets=resets,advances=advances,holds=holds)
