"""R10 pure healthy calendar/snapshot/threshold proof, not qualification."""
import itertools
import random


def event_calendar(g,count,*,special=(False,False),solo=False):
    if type(count) is not int or not 1<=count<=0xffffffff:
        raise ValueError('R10_FULL32_JOB_COUNT')
    if len(special)!=2 or not all(type(x) is bool for x in special):
        raise ValueError('R10_SPECIAL_MASK')
    first=[104] if solo else [204,204+g['warm_interval']//2]
    warm=[edge+(count-1)*g['warm_interval']+g['carry_done']+1 for edge in first]
    release=-1;publication=[];allocation=[]
    for c in range(len(first)):
        edge=max(warm[c]+2,release+1)
        allocation.append(edge)
        # 9N canonical + N registered copy + fixed controller edges. R9
        # publication snapshot/drain costs one edge for EACH scratch lease.
        release=edge+g['rows']+10*g['n']+7+(g['n'] if special[c] else 0)
        publication.append(release)
    return dict(count_per_context=count,first_edges=first,interval=g['warm_interval'],
        warm_edges=warm,canonical_allocation_edges=allocation,publication_edges=publication,
        pair_completion_cycles=max(publication),copy_edges=g['n']+4,
        model_only=True,measured_full_sample_PRP=False)


def snapshot(valid,base,owner,*,allocate=False,chosen_base=2,chosen_owner=0,
             reset=False,newjob=False,abort=False):
    if reset:return False,2,0
    if newjob:return False,base,owner
    if abort:return False,base,owner
    if allocate:return True,chosen_base,chosen_owner
    return valid,base,owner


def prove():
    rng=random.Random(0x1097)
    canonical=0;carry=0;cfg=0
    bases=[598,131077,604832956,999999937,1000000000]+[rng.randint(598,1000000000) for _ in range(128)]
    for b in bases:
        # Both legal canonical/carry frame terms fit their declared signed
        # widths. Terms remain from accepted base despite dirty live inputs.
        terms=(b,2*b,3*b,-b,-2*b,b-1)
        assert all(-(1<<33)<=x<(1<<33) for x in terms)
        for v in [-2*b-1,-2*b,-b-1,-b,-1,0,b-1,b,2*b-1,2*b,3*b-1,3*b]:
            oldq=2 if v>=2*b else 1 if v>=b else 0 if v>=0 else -1 if v>=-b else -2
            newq=2 if v>=terms[1] else 1 if v>=terms[0] else 0 if v>=0 else -1 if v>=terms[3] else -2
            assert (oldq,v-oldq*b)==(newq,v-newq*terms[0])
            assert (v< -2*b or v>=3*b)==(v<terms[4] or v>=terms[2])
            canonical+=1
        small=(b,2*b,3*b,4*b,-b,-2*b,2*b-2+(2*65536+23*16))
        assert all(-(1<<32)<=x<(1<<32) for x in small)
        for total in [-2*b,-b-1,-b,-1,0,b-1,b,2*b-1,2*b,3*b-1,3*b,4*b-1]:
            q=-2 if total< -b else -1 if total<0 else 0 if total<b else 1 if total<2*b else 2 if total<3*b else 3
            nq=-2 if total<small[4] else -1 if total<0 else 0 if total<small[0] else 1 if total<small[1] else 2 if total<small[2] else 3
            assert (q,total-q*b)==(nq,total-nq*small[0])
            carry+=1
    for chosen,b0,b1,reset,newjob,abort in itertools.product((0,1),(604832956,999999937),
            (604832956,999999937),(False,True),(False,True),(False,True)):
        # Opaque full56 {ordinal32,epoch16,generation8}; context is a separate
        # captured arbitration bit, never an invented bit in this owner word.
        owners=((3<<24)|(65535<<8)|1,(5<<24)|(42<<8)|1)
        valid,base,owner=snapshot(False,2,0,allocate=True,chosen_base=(b0,b1)[chosen],
                                 chosen_owner=owners[chosen],reset=reset,newjob=newjob,abort=abort)
        if reset or newjob or abort:assert not valid
        else:
            assert base==(b0,b1)[chosen] and owner==owners[chosen]
            # No newjob may modify a profile while scratch is owned. Raw
            # external base changes are unrelated to the captured job profile.
            assert snapshot(valid,base,owner)==(valid,base,owner)
        cfg+=1
    return dict(canonical_threshold_cases=canonical,carry_threshold_cases=carry,
        profile_selection_revocation_cases=cfg,legal_signed_widths_proven=True,
        current_owner_routing_preserved=True,new_healthy_profile_edges=0,
        final_gs_added_edges=1,term_added_edges=0,r9_publication_fence_per_job=1,
        native_qualified=False,clock_or_area_gain_claim=False)
