"""Model-only R11 synchronous numeric term prefetch hypothesis.

Uses exact captured lease/seed/PW calendars. Deterministic canonical symbols
stand for the UNCHANGED E4 multiplier, not a new Montgomery arithmetic proof.
No RTL edit, OLD_DATA waiver, native qualification or inferred RAM saving.
"""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-native-v1'
PRIME=104857601


def capture(n):
    path=BASE/('aw8-normal' if n==256 else 'full-normal')/'production-bundle.json'
    data=path.read_bytes();bundle=json.loads(data)
    assert bundle['geometry']['n']==n and bundle['parameters']['LEAN_PRODUCTION']==1
    protocol=next(t for k,t in bundle['files'].items() if 'epoch_protocol_contexts' in k)
    term=next(t for k,t in bundle['files'].items() if 'term_context_param' in k)
    for literal in ("payload_age_next[i]=(cycle_count+32'd1)-pw_first[i];",
                    "if(valid[i] && payload_age_next[i]<32'(ROWS))begin"):
        assert literal in protocol
    for literal in ('current_term=context_data[payload_owner[24]][payload_row[1:0]];',
                    'if(bypass_payload)current_term=product_data;',
                    'if(product_slot && bank_owner[prod_bank]==product_owner)',
                    'if(!stop)begin',"context_valid[bank]<='0;"):
        assert literal in term
    return bundle,hashlib.sha256(data).hexdigest()


def frames(bundle):
    g=bundle['geometry'];plan=bundle['two_context_schedule']
    answer=[]
    for correction,lease in zip(plan['correction'],plan['lease_allocation']):
        ctx,gen,epoch,ordinal=correction['tag'];assert ctx==lease['context'] and ordinal==lease['ordinal']
        owner=(lease['bank']<<25)|(ctx<<24)|(epoch<<8)|gen
        answer.append(dict(ctx=ctx,owner=owner,start=lease['start'],seed=correction['seed_first'],
                           pw=correction['pointwise_first'],retire=lease['start']+g['sink_accept']+g['rows']-1))
    return answer


def symbol(value,owner,row,lane):
    # Deliberately sensitive to every owner/row/lane bit and recurrence input.
    return ((value+1)*65537+owner*31+row*8191+lane*131071)%PRIME


def simulate(n=65536,*,canceled_ctx=None,fault_at=None,stale_payload=False,reset_at=None):
    bundle,pin=capture(n);g=bundle['geometry'];program=frames(bundle);rows=g['rows']
    if reset_at is not None:
        # Host stops canceled old events at async reset, retains numeric RAM,
        # then restarts the exact captured calendar with fresh owner generation.
        recovery=[]
        for f in program:
            fresh=dict(f)
            for key in ('start','seed','pw','retire'):fresh[key]+=reset_at+50
            fresh['owner']^=1
            recovery.append(fresh)
        all_program=program+recovery
    else:all_program=program
    start_events={f['start']:f for f in all_program if reset_at is None or f in recovery or f['start']<reset_at}
    seed_events={};pw_events={}
    for f in all_program:
        for row in range(4):
            assert f['seed']+row not in seed_events
            if reset_at is None or f in recovery or f['seed']+row<reset_at:
                seed_events[f['seed']+row]=(f,row)
        for row in range(rows):
            assert f['pw']+row not in pw_events
            if reset_at is None or f in recovery or f['pw']+row<reset_at:
                pw_events[f['pw']+row]=(f,row)
    # Separate memories; metadata/ownership remain shared literal FF state.
    old=[[tuple(symbol(7,c,r,l) for l in range(16)) for r in range(4)] for c in range(2)]
    ram=[[tuple(symbol(7,c,r,l) for l in range(16)) for r in range(4)] for c in range(2)]
    if not stale_payload:old=[[None]*4 for _ in range(2)];ram=[[None]*4 for _ in range(2)]
    q=tuple(symbol(99,3,9,l) for l in range(16));owner_q=None;row_q=None
    owner=[None,None];metadata=[[None]*4 for _ in range(2)];pending={};leases=[]
    reads=writes=comparisons=bypasses=reseed=collisions=cancel_raw=0
    finish=max(f['retire'] for f in all_program)+2
    for cycle in range(finish):
        if cycle==reset_at:
            # No reset of old/ram/q payload. Kill accepted-product/lease valid
            # and metadata; the next first row must be freshly seeded/prefetched.
            leases=[];pending.clear();owner=[None,None];metadata=[[None]*4 for _ in range(2)]
            owner_q=row_q=None
            continue
        if cycle in start_events:leases.append(start_events[cycle])
        stop=fault_at is not None and cycle>fault_at # legal detecting-edge tail remains
        candidates=[f for f in leases if f['start']<=cycle<=f['retire'] and 0<=cycle+1-f['pw']<rows]
        assert len(candidates)<=1,'model cannot label overlapping prospective leases valid'
        predict=(candidates[0],cycle+1-candidates[0]['pw']) if candidates else None
        product=pending.pop(cycle,None)
        accepted=product is not None and not stop and owner[product[0]['ctx']]==product[0]['owner']
        # READ occurs before any sameedge WRITE, exactly synchronous MLAB q.
        read_address=(predict[0]['ctx'],predict[1]&3) if predict else None
        write_address=(product[0]['ctx'],product[1]&3) if accepted else None
        if read_address is not None and read_address==write_address:
            collisions+=1
        assert not (read_address is not None and read_address==write_address),'LEGAL_RDW_COLLISION'
        prefetched=ram[read_address[0]][read_address[1]] if read_address else q
        current=pw_events.get(cycle)
        if current and not stop:
            f,row=current;ctx=f['ctx'];slot=row&3
            old_word=old[ctx][slot];new_word=q
            assert owner_q==f['owner'] and row_q==row,'missing/coherent nextconsumer prediction'
            bypass=product is not None and product[0]['owner']==f['owner'] and product[1]==row
            if bypass:
                old_word=new_word=product[2];bypasses+=1
            else:
                assert owner[ctx]==f['owner'] and metadata[ctx][slot]==row,'old consumer_missing'
            assert old_word==new_word and old_word is not None,'NUMERIC_PREFETCH_PAIR'
            comparisons+=16
            if ctx==canceled_ctx:cancel_raw+=16 # live cancellation is NOT a raw stop
            if row+4<rows:
                is_reseed=(row+4)//(rows//16)!=row//(rows//16)
                reseed+=is_reseed
                lhs=tuple(symbol(0,f['owner'],row+4,l) for l in range(16)) if is_reseed else old_word
                out=tuple(symbol(lhs[l],f['owner'],row+4,l) for l in range(16))
                assert cycle+4 not in pending
                pending[cycle+4]=(f,row+4,out)
        if cycle in seed_events and not stop:
            f,row=seed_events[cycle];assert not current,'shared seed/PW issue port conflict'
            if row==0:owner[f['ctx']]=f['owner'];metadata[f['ctx']]=[None]*4
            out=tuple(symbol(0,f['owner'],row,l) for l in range(16))
            assert cycle+4 not in pending
            pending[cycle+4]=(f,row,out)
        if accepted:
            f,row,word=product;ctx=f['ctx'];slot=row&3
            old[ctx][slot]=ram[ctx][slot]=word;metadata[ctx][slot]=row;writes+=1
        if predict:
            q=prefetched;owner_q=predict[0]['owner'];row_q=predict[1];reads+=1
    return dict(n=n,rows=rows,captured_bundle_sha256=pin,frames=len(program),symbolic_lane_comparisons=comparisons,
                enabled_prefetch_reads=reads,accepted_e4_writes=writes,exact_e4_bypass_rows=bypasses,
                reseed_updates=reseed,rdw_collisions=collisions,canceled_raw_lane_comparisons=cancel_raw,
                sticky_fault_origin=fault_at,unreset_stale_payload=stale_payload,
                async_reset_at=reset_at,recovery_frames=8 if reset_at is not None else 0)


def address_counterexamples():
    # AW8 first seed product at75: no prospective consumer yet; unconditional
    # fallback-to-owner0/row0 read collides with seed-row0 write. Nextvalid needed.
    invalid_fallback=dict(edge=75,read=(0,0),write=(0,0),predicted_valid=False)
    # Deliberately corrupt seed3 E4 product row to0 at78, retaining correct owner.
    # At78 the legal predictor reads futurePWrow0. Source write-owner equality
    # alone does not reject this address. Cache-ready is also suppressed by row0.
    corrupt_tag=dict(edge=78,read=(0,0),write=(0,0),predicted_valid=True,
                     original_seed_product_row=3,mutated_product_row=0)
    assert invalid_fallback['read']==invalid_fallback['write']
    assert corrupt_tag['read']==corrupt_tag['write']
    return dict(required_explicit_numeric_predicted_valid=invalid_fallback,
                no_universal_collision_proof_for_arbitrary_product_row_mutation=corrupt_tag)


def malformed_seed_behavior():
    # Direct internal seed-product row3->row0 mutation at AW8 edge78. Correct
    # owner passes existing write-owner guard; numeric read wantedrow0 E79.
    # Old FF nextedge sees newly written seed3, whereas sync OLD_DATA q saw
    # seed0. A read inhibit would hold arbitrary earlier q, also not seed3.
    owner=(65534<<8)|11
    seed0=tuple(symbol(0,owner,0,l) for l in range(16))
    seed3=tuple(symbol(0,owner,3,l) for l in range(16))
    assert seed0!=seed3
    return dict(injection='Internal E4 seed3 product tag row mutated3->0, full27owner remains correct',
        edge=78,existing_write_owner_guard_passes=True,collision=True,
        metadata_after_edge='context_valid[0][0]=1; context_row[0][0]=0; slot3 remains invalid',
        old_FF_raw_current_term_E79=list(seed3),sync_OLD_DATA_prefetch_E79=list(seed0),
        numeric_equal=False,cache_ready_at78=False,
        model_existing_protocol_origin='PWfirst79 expectsready; genuine cache3 token missing so protocol bad at79',
        numeric_read_inhibit_alone_equivalent=False,
        preserved_publication_not_proved_by_this_symbolic_diagnostic=True,
        stronger_same_origin_collision_fault='Would be a new source/authority contract, not current bit/cycle equivalence')


def report():
    return dict(status='LEGAL_CALENDAR_PAYLOAD_MODEL_PASS_NOT_RTL_READY',
        simulations=[simulate(256),simulate(65536),simulate(65536,canceled_ctx=1),
                     simulate(256,stale_payload=True),simulate(256,fault_at=85),
                     simulate(256,reset_at=85,stale_payload=True)],
        address_counterexamples=address_counterexamples(),
        admitted_malformed_tag_behavior=malformed_seed_behavior(),
        declared_payload_ff_parent=3*16*2*4*27,declared_prefetch_ff=3*16*27,
        declared_reduction_upper_bound=9072,measured_ff_or_lab_delta=None,
        unchanged='Full27 owner/row/valid, bank owner equality, pending/stop authority,E4 bypass/II1 remain literal FF/original logic.',
        missing_before_RTL=['Exact R11 schedule/predictor-valid interface',
                            'All-state no-RDW enable proof or numeric-only collision-safe implementation',
                            'Native paired normal plus same-origin fault/reset and physical MLAB mapping'],
        evidence='Source-bound event/address/uninterpreted numeric-symbol model, NOT Montgomery/NTT/native/hardware qualification.',
        prior_async_OLD_DATA_failures_parked=True)


if __name__=='__main__':print(json.dumps(report(),indent=2))
