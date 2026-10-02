"""R93 bounded source inventory, NOT a lean transformer or removal estimate.

Default-protected source remains immutable. Each rule names a semantic seam;
identifier matches never authorize blind deletion of the matching statement.
"""
import argparse,hashlib,json,re
from pathlib import Path

RULES=[
 ('host_framing','host_contexts','retain_functional',r'command_ready|feed_push|feed_pop|levels\[|head_double|phase\[|copy_committed|published\[',
  'Keep ready/valid acceptance, descriptor FIFO capacity/pop/ordering, double bit, per-context phases, N acknowledged commits and publication. Remove identity/range rejection only in lean branch; do not erase occupancy/state.'),
 ('host_identity','host_contexts','split_role',r'live_owner|job_generation|job_epoch|command_generation|ingress_bad|response_bad|capture_bad|read_owner',
  'Epoch/generation/full56 comparisons are approved lean removals. Preserve context/image routing and sequence/count deciding final versus feedback. Public identity presentation may remain for host ABI, with verification-only checks disabled explicitly.'),
 ('scratch_arbitration','host_contexts','retain_functional',r'canonical_owner|canonical_owned|shadow_row_context|source_context',
  'canonical_owner is the shared scratch owner/context selector, not an expendable identity tag. Keep cold reader arbitration, response context/row delay, read-valid and copy-to-shadow ordering; host offload B is a separate boundary change.'),
 ('lease_checks','epoch_protocol_contexts','split_role',r'epoch\[|generation\[|next_epoch|next_completed|pw_tuple_ok|sink_tuple_ok|sink_order_ok|frame_owner_exists|protocol_checks',
  'Remove typed tuple/order/malformed checks, but replace correction/cache identity lookups with proven deterministic lean selectors. Context-only lookup is ambiguous while same-context leases overlap; no blanket tieoff.'),
 ('lease_calendar','epoch_protocol_contexts','retain_functional',r'valid\[|received\[|ready\[|owner\[|base\[|pw_first|sink_first|free_index|correction_base|correction_bank|pointwise_bank|sink_bank',
  'Preserve allocation/lifetime, correction-base and payload bank selection, readiness and PW/sink row calendars or prove a functionally equivalent replacement. Logical scheduling is not verification-only lease metadata.'),
 ('field_payload_route','shared_warm','split_role',r'payload_owner|payload_ready|payload_reserved|A_table\[|B_table\[|fwd_generation\[24\]|small_owner\[24\]|seed_owner\[24\]|term_join_valid',
  'Storage2 uses context bit24 for A/B and term banks. Remove full-owner/range diagnostics only while retaining bank reservations, readiness, term availability and correct consumer-context selection.'),
 ('term_recurrence','term_context','split_role',r'pw_bank|prod_bank|seed_bank|bypass=|current_term|context_row|context_valid|bank_owner|product_owner|issue_tag|cache_ready',
  'Owner comparisons occur in functional E4 bypass/write/cache selection as well as faults. Keep context/bank and row identity needed to select product_data versus stored term; preserve 4-row recurrence, seed priority, E4/II1.'),
 ('transform_metadata','merged_','split_role',r'generation_pipe|owner_generation|cadence_bad|row_generation|slot_pipe|start_pipe|remaining',
  'Epoch/generation validation and high metadata bits can be removed in lean mode. Preserve occupied/start latency, lane permutation/advance, functional context routing and any counter also driving data/root addresses.'),
 ('commutator_metadata','commutator_shared','split_role',r'upper_tags|lower_tags|owner_|generation|eligible|advance|phase|fill|out_slot|out_frame',
  'Remove verification owner comparisons/full identity transport, not valid occupancy, phase/fill/advance or frame/context routing. Lockstep tags shared per stage; no per-lane saving assumption.'),
 ('fault_aggregation','*','approved_lean_removal',r'fault_pending|local_bad|admission_bad|join_bad|cadence_bad|out_error|controller_error',
  'Typed fault/range/malformed aggregation may be removed only under LEAN_PRODUCTION. Do not erase surrounding numerical assignments, acceptance/flow state or safety-needed arithmetic muxes. Replace global quarantine with minimal stuck/timeout watchdog semantics; default protected branch exact.'),
 ('observers','*','split_role',r'synthesis translate_off|\$fatal|canonical_cycles|context_canonical_cycles|context_copy_cycles|cycle_count|frame_count',
  'Translate-off assertions/native observer fixture already cost no synthesized area. Profiling-only counters may drop; calendar cycle_count/row/frame counters with functional consumers must remain. No register-count credit.'),
]

def sha(raw):return hashlib.sha256(raw).hexdigest()
def inventory(files,pins,source):
    assert files and set(files)==set(pins)
    assert all(sha(s.encode())==pins[n] for n,s in files.items())
    assert any('storage2' in n for n in files),'Scope is protected storage2 C2'
    selected=[]
    for key,selector,decision,pattern,reason in RULES:
        hits=[]
        for name,text in files.items():
            if selector!='*' and selector not in name:continue
            # F0 suffices for structural map; keep exact all-prime source pins.
            if '_f1_' in name or '_f2_' in name:continue
            lines=[dict(line=i,text=s.strip()) for i,s in enumerate(text.splitlines(),1) if re.search(pattern,s)]
            if lines:hits.append(dict(file=name,sha256=pins[name],anchors=lines[:16],additional_matches=max(0,len(lines)-16)))
        assert hits,(key,'missing source seam')
        selected.append(dict(seam=key,classification=decision,reason=reason,sources=hits))
    return dict(status='SOURCE_INVENTORY_NOT_IMPLEMENTED',source=source,production_files=len(files),rules=selected,
      requirement='One defaultOFF LEAN_PRODUCTION switch; protected bytes exact; lean AW8/PRP/full-chain output-word twin proof; verification twin retains every fault/crosstalk gate.',
      record_label='lean build; host GL assumed',host_Gerbicz_Li_rollback_implemented=False,
      measured_removable_ALM=None,measured_removable_LAB=None,physical_rule='Only source-matched whole placement/STA measurements, no declaration/register-times-count credit.')
def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path);p.add_argument('--bundle',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();assert bool(a.manifest)!=bool(a.bundle)
    path=(a.manifest or a.bundle).resolve();m=json.loads(path.read_text())
    if a.manifest:
        pins=m['storage2']['production_generated_sha256'];root=path.parent/'source/fpga/rtl'
        files={n:(root/n).read_text() for n in pins}
        assert all(m['sources']['rtl/'+n]==pin for n,pin in pins.items())
    else:pins=m['generated_sha256'];files=m['files']
    result=inventory(files,pins,dict(path=str(path),sha256=sha(path.read_bytes())))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(dict(status=result['status'],source_files=len(files),seams=len(result['rules']),output=str(a.output))))
if __name__=='__main__':main()
