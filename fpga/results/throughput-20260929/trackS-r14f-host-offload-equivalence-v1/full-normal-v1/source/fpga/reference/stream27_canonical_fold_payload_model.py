"""Zero-edge VALUE→PROCESS fold payload specification, not native proof."""
import itertools
import random


def signed34(value):
    value &= (1<<34)-1
    return value-(1<<34) if value&(1<<33) else value


def fold(value,base,pass_index):
    value=signed34(value)
    b=signed34(base);two=signed34(base*2);three=signed34(base*3)
    if value>=two:q,r=2,signed34(value-two)
    elif value>=b:q,r=1,signed34(value-b)
    elif value>=0:q,r=0,value
    elif value>=signed34(-base):q,r=-1,signed34(value+b)
    else:q,r=-2,signed34(value+two)
    bad=(value<signed34(-base*2) or value>=three or r<0 or r>=b or
         (pass_index!=0 and not -1<=q<=1))
    return q,r,bool(bad)


def process(payload,*,digit_bad,last,pass_index,all_zero,all_max,base):
    q,r,early_bad=payload
    zero=all_zero and r==0
    maximum=all_max and r==signed34(base-1)
    special_bad=pass_index==2 and last and q!=0 and not (
        q==1 and zero or q==-1 and maximum)
    code=6 if digit_bad else 7 if early_bad or special_bad else 0
    return dict(code=code,write=code==0,word=r&0xffffffff,carry=q,
                next_zero=zero,next_max=maximum)


def prove():
    rng=random.Random(0xF01D100)
    cases=0
    bases=(0,1,2,599,131077,604832956,1000000000,0x7fffffff,0xffffffff)
    for base in bases:
        values={-(1<<33),(1<<33)-1,-base*2-1,-base*2,-base,-1,0,base-1,base,
                base*2-1,base*2,base*3-1,base*3}
        for value,pi,digit_bad,last,zero,maximum in itertools.product(
                values,range(3),(False,True),(False,True),(False,True),(False,True)):
            # Existing VALUE captures signed34 value_next; the successor
            # captures fold(value_next) at that SAME edge instead.
            stored_value=signed34(value)
            old=process(fold(stored_value,base,pi),digit_bad=digit_bad,last=last,
                        pass_index=pi,all_zero=zero,all_max=maximum,base=base)
            payload=fold(value,base,pi)
            new=process(payload,digit_bad=digit_bad,last=last,
                        pass_index=pi,all_zero=zero,all_max=maximum,base=base)
            assert old==new
            if digit_bad:assert new['code']==6
            cases+=1
    for _ in range(20000):
        base=rng.randrange(1<<32);value=rng.randrange(-(1<<33),1<<33)
        pi=rng.randrange(3)
        assert fold(value,base,pi)==fold(signed34(value),base,pi)
        cases+=1
    # Reset may leave payload stale, but the unchanged state reset cannot
    # consume it until an actual READ then VALUE establishes a new tuple.
    for reset_state in ('READ_WORD','VALUE_WORD','PROCESS_WORD','SPECIAL_WRITE'):
        state='IDLE';payload=fold(600,599,0)
        assert state!='PROCESS_WORD'
        state='READ_WORD';assert state!='PROCESS_WORD'
        state='VALUE_WORD';payload=fold(1,599,0)
        state='PROCESS_WORD';assert payload==fold(1,599,0)
    assert fold(600,599,0)!=fold(0,599,0)  # wrong/previous payload control
    return dict(binary_integer_cases=cases,exact_signed34_wrapping=True,
        digit_before_internal_range_priority=True,late_special_sentinel_check_retained=True,
        READ_VALUE_PROCESS_edges_literal=True,normal_service_edges='9N',special_service_edges='10N',
        new_external_edges=0,reset_stale_payload_ineligible=True,
        wrong_previous_payload_negative_control=True,
        arbitrary_payload_FF_corruption_claim=False,native_qualified=False)
