"""Read-only R5 fault-feedback hypotheses; no RTL transform or job launcher."""
from dataclasses import dataclass
import hashlib
import itertools
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[1]
CAPTURE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-loadlocal-native-v1/full-normal/production-bundle.json'
LEAF='genefer_stream27_mdc_commutator_shared_packed_v1.sv'
PROTOCOL='genefer_stream27_epoch_protocol_contexts_v1_payload_lookahead_v1.sv'


@dataclass(frozen=True)
class Tag:
    valid: bool
    owner: bool
    generation: int


def pair_bad(upper, lower):
    return upper.valid != lower.valid or (upper.valid and
        (upper.owner != lower.owner or upper.generation != lower.generation))


def continuity_bad(upper, offset, owner, generation):
    return upper.valid and offset != 0 and (upper.owner != owner or upper.generation != generation)


def original(phase, upper, lower, current, offset, owner, generation):
    selected=current if phase else lower
    return bool(pair_bad(upper,selected) or continuity_bad(upper,offset,owner,generation))


def compare_before_select(phase, upper, lower, current, offset, owner, generation):
    input_bad=pair_bad(upper,current)
    delayed_bad=pair_bad(upper,lower)
    return bool((input_bad if phase else delayed_bad) or continuity_bad(upper,offset,owner,generation))


def prove():
    # Superset equality-variable model: no reliance on healthy replica equality,
    # tag correctness or reset-initialized numeric payload.
    boolean_cases=0
    for phase,uv,iv,lv,io,ig,lo,lg,offset,oo,og in itertools.product((0,1),repeat=11):
        a=(uv!=iv) or (uv and (not io or not ig))
        b=(uv!=lv) or (uv and (not lo or not lg))
        continuity=uv and offset and (not oo or not og)
        selected_valid=iv if phase else lv
        selected_owner_equal=io if phase else lo
        selected_generation_equal=ig if phase else lg
        old=(uv!=selected_valid) or (uv and (not selected_owner_equal or not selected_generation_equal)) or continuity
        new=(a if phase else b) or continuity
        assert bool(old)==bool(new)
        boolean_cases+=1
    rng=random.Random(95)
    full_tuple_cases=0
    for _ in range(100000):
        tags=[Tag(bool(rng.randrange(2)),bool(rng.randrange(2)),rng.randrange(1<<25)) for _ in range(3)]
        if rng.randrange(2): tags[rng.randrange(1,3)]=tags[0]
        phase=bool(rng.randrange(2));offset=rng.choice((0,1,63,4095))
        owner=bool(rng.randrange(2));generation=rng.randrange(1<<25)
        assert original(phase,*tags,offset,owner,generation)==compare_before_select(phase,*tags,offset,owner,generation)
        full_tuple_cases+=1
    protocol_cases=0
    for controller,protocol_error,bad,external,other in itertools.product((0,1),repeat=5):
        stop=controller or protocol_error
        pending=protocol_error or (not stop and (bad or external))
        local=protocol_error or (not stop and bad)
        old=(not controller) and (external or other or pending or protocol_error)
        new=(not controller) and (external or other or local or protocol_error)
        assert bool(old)==bool(new)
        protocol_cases+=1
    return dict(boolean_owner_cases=boolean_cases,full25_tuple_cases=full_tuple_cases,
                protocol_absorption_cases=protocol_cases,two_state_only=True,
                no_unknown_input_equivalence_claim=True,rtl_implemented=False,native_or_physical_gain=False)


def source():
    raw=CAPTURE.read_bytes();bundle=json.loads(raw)
    leaf=bundle['files'][LEAF];protocol=bundle['files'][PROTOCOL]
    anchors=["phase=in_slot_valid && !frame_start && offset[SHIFT];",
             "result_lower_tag=phase?input_tag:head_lower_tag;",
             "owner_bad=(head_upper_tag.valid!=result_lower_tag.valid)",
             "fault_pending=out_error || (!quarantine && (malformed||owner_bad));"]
    assert all(leaf.count(a)==1 for a in anchors)
    assert protocol.count('assign fault_pending=out_error || (!stop && (bad || external_fault_pending));')==1
    fields=[text for name,text in bundle['files'].items() if 'shared_warm_' in name]
    assert len(fields)==3 and all('.external_fault_pending(admission_bad || join_bad || (|child_pending) || inverse_pending)' in s for s in fields)
    return dict(capture_sha256=hashlib.sha256(raw).hexdigest(),leaf_sha256=hashlib.sha256(leaf.encode()).hexdigest(),
                protocol_sha256=hashlib.sha256(protocol.encode()).hexdigest(),production_files=len(bundle['files']),
                source_anchor_checks=True,scope='Read-only frozen R5 source; R6 keeps these54 downstream files exact')


if __name__=='__main__':
    print(json.dumps(dict(source=source(),model=prove()),indent=2))
