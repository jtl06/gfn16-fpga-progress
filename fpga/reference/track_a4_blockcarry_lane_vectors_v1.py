"""Source-only A4 lane corpus. Independent serial-divmod oracle and edge queue.

No HDL invocation. AW5 and AW8 only; exact model is used for scalar proof bounds,
not to calculate expected output digits or the final boundary quotient.
"""
import hashlib
import random

from fpga.reference import track_a4_blockcarry_model as model


def corpus(aw, random_frames=32):
    if aw not in (5, 8) or not 1 <= random_frames <= 256:
        raise ValueError("bounded AW5/AW8 source-preparation corpus")
    n, t = 1 << aw, (1 << aw)//16
    minimum = model.arithmetic.minimum_base(n, 16)
    max_a = model.bounds(n, 10**9)["doubled_coefficient_bound"]
    rng = random.Random(0xA420261001 + aw)
    events, due = [], {}
    state, error_code, accepted, q = "idle", 0, 0, 0
    active_base, active_limit = minimum, 1
    counts = dict(frames=0, completed=0, errors=0, resets=0, digits=0, boundaries=0)

    def emit(*, rst=1, begin=0, valid=0, base=minimum, value=0, offset=0,
             start=0, end=0, limit=None, reciprocal=None):
        nonlocal state, error_code, accepted, q, active_base, active_limit
        edge = len(events)
        if limit is None:
            limit = model.bounds(n, base if minimum <= base <= 10**9 else minimum)["doubled_coefficient_bound"]
        if reciprocal is None:
            reciprocal = (1 << 96)//max(base, 2)
        fault = 0
        done = dv = bv = digit = digit_offset = low = high = 0
        if not rst:
            state, error_code, accepted, q = "idle", 0, 0, 0
            due.clear()
            counts["resets"] += 1
        else:
            if state == "idle":
                if valid:
                    fault = 1
                elif begin and not (minimum <= base <= 10**9 and 0 < limit <= max_a and reciprocal != 0):
                    fault = 2
                elif begin:
                    state, accepted, q = "active", 0, 0
                    active_base, active_limit = base, limit
                    counts["frames"] += 1
            elif state == "active":
                if begin:
                    fault = 3
                elif valid:
                    if not (accepted < t and offset == accepted and start == (accepted == 0)
                            and end == (accepted == t-1) and abs(value) <= active_limit):
                        fault = 4
                    else:
                        q, digit_value = divmod(value+q, active_base)
                        due.setdefault(edge+25, {})["digit"] = (offset, digit_value)
                        accepted += 1
                        if accepted == t:
                            high_value, low_value = divmod(q, active_base)
                            due.setdefault(edge+28, {})["boundary"] = (low_value, high_value)
                            due.setdefault(edge+29, {})["done"] = True
            if fault:
                state, error_code = "failed", fault
                due.clear()
                counts["errors"] += 1
            if state == "active":
                token = due.pop(edge, {})
                if "digit" in token:
                    digit_offset, digit = token["digit"]
                    dv = 1
                    counts["digits"] += 1
                if "boundary" in token:
                    low, high = token["boundary"]
                    bv = 1
                    counts["boundaries"] += 1
                if token.get("done"):
                    done, state = 1, "idle"
                    counts["completed"] += 1
        events.append((rst, begin, valid, start, end, base,
                       f"{reciprocal:024x}", f"{limit:024x}", f"{value & ((1<<96)-1):024x}", offset,
                       int(state == "active"), done, int(state == "failed"), error_code,
                       dv, digit, digit_offset, bv, low, high & 0xffffffff))

    def frame(base, values, *, gaps=False, reset_age=None):
        emit(begin=1, base=base)
        for offset, value in enumerate(values):
            if gaps and rng.randrange(3) == 0:
                emit(base=0xffffffff, value=-(1 << 95), offset=(1 << aw)-1)
            emit(valid=1, base=base, value=value, offset=offset,
                 start=int(offset == 0), end=int(offset == t-1))
        for age in range(31):
            emit(rst=int(age != reset_age))

    emit(rst=0)
    for base in (minimum, minimum+1, 604832956, 10**9):
        a = model.bounds(n, base)["doubled_coefficient_bound"]
        for pattern in ((0,), (a,), (-a,), (a, -a), (-a, a), (base-1,)):
            frame(base, list(pattern)*(t//len(pattern)))
    for index in range(random_frames):
        base = rng.choice((minimum, 10**9, 604832956))
        a = model.bounds(n, base)["doubled_coefficient_bound"]
        frame(base, [rng.randrange(-a, a+1) for _ in range(t)], gaps=True)
    # Every pipeline age, boundary normalization, pair publication and done check.
    for age in range(30):
        frame(minimum, [minimum*minimum+3]*t, reset_age=age)
        frame(minimum, [-(minimum*minimum+1)]*t)
    # Reset mid-input, then next-edge begin with no stale history/tags.
    emit(begin=1)
    emit(valid=1, start=1, value=1)
    emit(rst=0)
    frame(minimum, [minimum-1]*t)
    # Input/config faults and persistent quarantine, each followed by reset.
    for config in ({"base": minimum-1}, {"base": 10**9+1}, {"limit": 0},
                   {"limit": max_a+1}, {"reciprocal": 0}):
        emit(begin=1, **config)
        for _ in range(32):
            emit(begin=1)
        emit(rst=0)
    emit(valid=1)
    emit(rst=0)
    for bad in ({"begin": 1}, {"valid": 1, "offset": 1, "start": 1},
                {"valid": 1, "start": 0}, {"valid": 1, "start": 1, "end": 1},
                {"valid": 1, "start": 1, "value": model.bounds(n, minimum)["doubled_coefficient_bound"]+1},
                {"valid": 1, "start": 1, "value": -(1 << 95)}):
        emit(begin=1)
        emit(**bad)
        for _ in range(32):
            emit(valid=1)
        emit(rst=0)
    frame(minimum, [0]*t)
    text = f"A4LANE1 {aw} {len(events)}\n" + "\n".join(" ".join(map(str, row)) for row in events) + "\n"
    return text, dict(aw=aw, events=len(events), **counts,
                     sha256=hashlib.sha256(text.encode()).hexdigest(),
                     scope="source corpus only, no native result")
