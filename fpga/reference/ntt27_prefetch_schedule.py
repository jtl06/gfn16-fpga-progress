"""Pure integer schedule proof; does not compile or simulate RTL.

Model the profile port's request/response edges independently of the exposed
cycle formula. The caller must still validate RTL and physical implementation.
"""
from __future__ import annotations
import json
from .ntt27_prefetch_regression import setup_cycles

def event_setup(lg, lanes, reverse):
    groups = ((1 << lg)+2*lanes-1)//(2*lanes)
    kw = (2*lanes).bit_length()-1
    stages = list(range(lg-1,-1,-1) if reverse else range(lg))
    words = []
    for stage in stages:
        period = 1 if stage < kw else 1 << (stage-kw+1)
        words.append(min(4,groups,period)*min(lanes,1 << stage))
    exposed = words[0]+4
    for required in words[1:]:
        # Previous ROOT_START is edge0. Clear at edge1. Profile issues
        # U seeds at edges2..U+1, step at U+2, captures step at U+3.
        ready_after = required+3
        stage_setup_edge = groups+8
        edge = stage_setup_edge
        # STAGE_SETUP must observe READY from a strictly earlier edge.
        if ready_after >= edge:
            edge += 1
            while ready_after >= edge:
                exposed += 1
                edge += 1
            exposed += 1  # final ROOT_WAIT consumes the ready descriptor
        exposed += 1  # recurrence ROOT_START remains explicit
    return exposed

def main():
    checks = 0
    for lanes in (1,2,4,8,16,32,64):
        for lg in range(1,17):
            for reverse in (False,True):
                measured = event_setup(lg,lanes,reverse)
                assert measured == setup_cycles(lg,lanes,reverse), (lg,lanes,reverse,measured)
                checks += 1
    model = {}
    for lanes in (16,64):
        n = 65536; lg = 16; groups = n//(2*lanes)
        body = 2*lg*(groups+8)+3*(n//lanes+7)
        setup = sum(event_setup(lg,lanes,d) for d in (False,True))+2*(4*lanes+4)
        model[str(lanes)] = {"body_cycles":body,"exposed_setup_cycles":setup,"warm_arithmetic_cycles":body+setup}
    print(json.dumps({"status":"integer_schedule_passed","checks":checks,"not_rtl_simulation":True,"full_n_model":model},indent=2))

if __name__ == "__main__": main()
