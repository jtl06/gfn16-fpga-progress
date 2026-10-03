"""MODEL ONLY: synchronous term payload prefetch with accepted-write forwarding.

No RTL, protocol rewrite, new collision fault or RDW waiver is proposed here.
The current FIELD100 raw next lookup is independent of ready/accept/fault.
The default lookup address is cell0; retaining that cell's last written value
is necessary to reproduce reset/origin-tail behavior without an async RAM read.
Arithmetic products are opaque same-data events, not a Montgomery/NTT proof.
"""
import hashlib
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[1]
CAPTURES={256:('aw8-normal','dd8d9196a5ac79381b8e701d021d19a067dde4d319b15799b13f8d8f61441a00'),
          65536:('full-normal-v2','f5f0617d989b64bb965b612a0d0cb8b6074c1ecd4f85f01ed66f970dfbf521f2')}


def capture(n):
    name,pin=CAPTURES[n]
    path=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1'/name/'production-bundle.json'
    raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==pin
    b=json.loads(raw)
    protocol=next(t for k,t in b['files'].items() if 'epoch_protocol_contexts' in k)
    term=next(t for k,t in b['files'].items() if 'term_context_param' in k)
    root=next(t for k,t in b['files'].items() if 'shared_warm' in k and '_f0_' in k)
    for literal in ("pointwise_payload_owner_next='0;pointwise_payload_row_next='0;",
                    "payload_age_next[i]=(cycle_count+32'd1)-pw_first[i];",
                    "if(valid[i] && payload_age_next[i]<32'(ROWS))begin",
                    'if(cache_ready && cache_found && received[cache_index] && !ready[cache_index])ready[cache_index]<=1;'):
        assert literal in protocol
    assert 'else begin term_payload_owner<=protocol_payload_owner_next;term_payload_row<=protocol_payload_row_next;end' in root
    for literal in ('current_term=context_data[payload_owner[24]][payload_row[1:0]];',
                    'if(bypass_payload)current_term=product_data;',
                    'if(product_slot && bank_owner[prod_bank]==product_owner)begin',
                    'context_data[prod_bank][product_row[1:0]]<=product_data;',
                    'wire stop=quarantine || out_error;'):
        assert literal in term
    return b,pin


def address(owner,row):
    return ((owner>>24)&1)*4+(row&3)


def accepted_write(product,bank_owner,rst_n,stop):
    # Exact preedge original eligibility, NOT an invented age/row validator.
    return (bool(rst_n and not stop and product is not None and
                 bank_owner[(product['owner']>>24)&1]==product['owner']))


def random_state_relation(edges=100000):
    rng=random.Random(150315)
    # These represent previously written/reached payload values. Uninitialized
    # power-up cells are don't-care and no equality/initialization is promised.
    old=[rng.getrandbits(432) for _ in range(8)]
    ram=list(old);shadow0=old[0]
    q=rng.getrandbits(432);prefetch_valid=False;payload_addr=0
    owners=[rng.getrandbits(27)&~(1<<24),rng.getrandbits(27)|(1<<24)]
    collisions=forwards=checks=canceled=origin=reset_edges=bad_owner=0
    for edge in range(edges):
        rst_n=edge%311 not in (0,1,2)
        stop=edge%127 in range(5)
        if not rst_n:
            # Same async reset as original payload-owner/row FFs, while data
            # and the known cell0 shadow are deliberately retained.
            payload_addr=0;prefetch_valid=False;reset_edges+=1
        head=q if prefetch_valid else shadow0
        assert head==old[payload_addr],('PREEDGE',edge)
        # Original current E4 bypass remains an independent identical mux.
        bypass=bool(rng.randrange(5)==0)
        bypass_word=rng.getrandbits(432)
        assert (bypass_word if bypass else head)==(bypass_word if bypass else old[payload_addr])
        checks+=1
        canceled+=int(edge%83==0)  # Live disable changes eligibility, not raw payload lookup.
        origin+=int(not stop and edge%97==0)  # Same-edge fault never inhibits admitted data writes.
        next_valid=bool(rng.randrange(3)) if rst_n else False
        next_owner=rng.getrandbits(27) if next_valid else 0
        next_row=rng.randrange(4096) if next_valid else 0
        read_addr=address(next_owner,next_row)
        product=None
        if rng.randrange(4):
            ctx=rng.randrange(2);owner=owners[ctx]
            if rng.randrange(7)==0:owner^=1<<(rng.randrange(24))
            product=dict(owner=owner,row=rng.randrange(4096),data=rng.getrandbits(432))
            # Deliberately make arbitrary admitted row/address collisions.
            if edge%3==0:
                product['owner']=owners[read_addr//4]
                product['row']=(product['row']&~3)|(read_addr&3)
        write=accepted_write(product,owners,rst_n,stop)
        if product is not None and not write and rst_n and not stop:bad_owner+=1
        write_addr=address(product['owner'],product['row']) if write else None
        if next_valid:
            collision=write and write_addr==read_addr
            q=product['data'] if collision else ram[read_addr]
            forwards+=int(collision);collisions+=int(collision)
        if write:
            old[write_addr]=ram[write_addr]=product['data']
            if write_addr==0:shadow0=product['data']
        if rst_n:
            payload_addr=read_addr;prefetch_valid=next_valid
        # q from the read OR accepted write forward equals post-edge FF state.
        assert (q if prefetch_valid else shadow0)==old[payload_addr],('POSTEDGE',edge)
        assert old==ram and shadow0==old[0]
        checks+=1
        if edge%113==0:owners=[rng.getrandbits(27)&~(1<<24),rng.getrandbits(27)|(1<<24)]
    assert forwards>10000 and bad_owner>1000
    return dict(edges=edges,raw_pre_post_comparisons=checks,accepted_collisions=collisions,
                accepted_write_forwards=forwards,rejected_wrong_full27_owner_writes=bad_owner,
                reset_edges=reset_edges,canceled_raw_samples=canceled,detecting_edge_raw_samples=origin,
                numeric_changed=False,new_fault_authority=False)


def first_pw_and_cache_cases():
    b,pin=capture(256);first=b['two_context_schedule']['correction'][0]
    assert first['cache_capture']==78 and first['pointwise_first']==79
    owner=(65534<<8)|11
    seed0,seed3=0x125,0x3ab
    # PreE78 ready0, accepted real cache token sets ready1 postE78. A predictor
    # gated on current ready would miss the first PW79 read, despite legal work.
    ready=False;raw_next_valid=True;received=True
    old=[seed0,0x22,0x33,0];ram=list(old)
    write_addr=3;read_addr=0
    q=seed3 if write_addr==read_addr else ram[read_addr]
    old[write_addr]=ram[write_addr]=seed3
    ready=received and not ready
    assert ready and raw_next_valid and q==old[0]==seed0
    # Same full owner, admitted mutated seed3 row3->row0: no new write check.
    old=[seed0,0x22,0x33,0];ram=list(old)
    old_data=ram[0];q_forward=seed3;old[0]=ram[0]=seed3
    assert q_forward==old[0] and old_data!=old[0]
    # Original missing cache-ready at79 still faults; forwarding preserves its
    # origin-edge numeric data rather than adding a stronger collision fault.
    return dict(capture=pin,full27_owner=owner,
        legal_seed3_cache_edge=78,first_PW_edge=79,
        current_ready_at_prefetch=False,next_ready_at_consumer=True,
        required_predictor='raw valid lease/next age; NOT current ready or owner!=0',
        current_ready_gated_predictor_misses_first_PW=True,
        mutated_seed3_row_to_zero=dict(original_FF_word=seed3,OLD_DATA_q=old_data,
            forwarded_q=q_forward,numeric_equal_with_forward=True,
            original_missing_cache_fault_edge=79,new_collision_fault_added=False),
        early_matching_token_replaces_late=dict(age_predicate_present=False,
            old_ready_can_set_early=True,protection_claim=False),
        duplicate_matching_late_token=dict(original_ready_already_true_causes_bad=True,
            source_age_validation_claim=False))


def reset_default_counterexample():
    # Concrete previously written payload, not an uninitialized don't-care.
    cell0=0x123;last_selected_q=0xabc
    assert cell0!=last_selected_q
    return dict(original_known_cell0=cell0,q_before_async_reset=last_selected_q,
        original_payload_address_after_reset=0,
        prefetch_q_hold_only_changes_first_malformed_origin_RAW=True,
        proposed_unreset_cell0_shadow=cell0,shadow_fallback_raw_equal=True,
        initialized_payload_equivalence_required=True,powerup_dontcare_initialization_not_claimed=True)


def captured_calendar(n):
    b,pin=capture(n)
    events=[]
    for c,lease in zip(b['two_context_schedule']['correction'],b['two_context_schedule']['lease_allocation']):
        ctx,gen,epoch,ordinal=c['tag']
        assert (ctx,ordinal)==(lease['context'],lease['ordinal'])
        owner=(lease['bank']<<25)|(ctx<<24)|(epoch<<8)|gen
        assert 0<=owner<1<<27 and c['cache_capture']>=c['seed_last']+4
        # New lease cannot reach a PW consumer on the next acceptance edge.
        assert c['pointwise_first']-lease['start']>1
        events.append(dict(owner=owner,seed0=c['seed_first'],seed3=c['seed_last'],
            cache=c['cache_capture'],firstPW=c['pointwise_first']))
    return dict(n=n,rows=b['geometry']['rows'],source_bundle_sha256=pin,frames=events,
        raw_lookup_not_publication_eligibility=True,scalar_calendar_only=True)


def report():
    return dict(schema='r15-term-sync-prefetch-forward-model-v1',status='MODEL_ONLY_STATE_RELATION_PASS_NOT_RTL_READY',
        generic_state_relation=random_state_relation(),first_PW=first_pw_and_cache_cases(),
        reset_counterexample=reset_default_counterexample(),calendars=[captured_calendar(n) for n in CAPTURES],
        interface_hypothesis='numeric raw-nextlookup-valid +existing nextowner/row; sync q, acceptedwrite forward, unresetcell0 shadow; unchanged currentE4 bypass',
        existing_full27_owner_row_valid_writeeligibility_and_fault_authority_must_remain_literal=True,
        source_transform_native_mapping_ready=False,new_RTL_authored=False,
        original_current_ready_read_gate_and_qhold_rejected=True,
        declared_payload_registers_per_lane=216,proposed_q_plus_shadow_registers_per_lane=54,
        declared_reduction_upper_bound=7776,actual_register_LAB_RAM_clock_delta=None,
        no_Montgomery_or_NTT_numerical_proof=True,no_whole_fit_or_fault_immunity_claim=True,
        missing_before_RTL=['Exact FIELD100 root/protocol numeric-valid and reset-shadow source seam review',
            'Reachable initialized-payload invariant and complete original detecting-edge term-data/bypass/control pairing',
            'Actual native normal/reset/cancel/seed-owner/collision/early+duplicate controls',
            'Physical MLAB inference and matched resource measurement with explicit outside-RAM forwarding'],
        prior_async_OLD_DATA_mapping_failures_preserved=True,promotion_allowed=False)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();assert out.is_relative_to(ROOT) and not out.exists()
    value=report();out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps(dict(path=str(out),status=value['status'],RTL_ready=False)))
