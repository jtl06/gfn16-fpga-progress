"""Independent exact expectations for shared setup and host canonical cell."""
import hashlib
import random

from fpga.reference.track_a4_control_model_v1 import shared_setup
from fpga.reference.track_a4_blockcarry_model import arithmetic


def corpus(aw):
    if aw not in (5, 16):
        raise ValueError("explicit AW5/AW16 scalar primitive gate")
    n, k = 1 << aw, 2*(1 << aw)+384
    minimum = arithmetic.minimum_base(n, 16)
    rng = random.Random(0xA4C020261001+aw)
    state, age = "idle", 0
    accepted_base = generation = limit = reciprocal = cfg = 0
    cd = cc = ct = 0
    rows = []
    counts = dict(setup_success=0, setup_errors=0, setup_cancels=0, cell_valid=0, cell_errors=0, resets=0)

    def emit(*, rst=1, cancel=0, begin=0, base=minimum, cell=None):
        nonlocal state, age, accepted_base, generation, limit, reciprocal, cfg, cd, cc, ct
        index = len(rows)
        gen = (0x12340000+index) & 0xffffffff
        if cell is None:
            cb = rng.choice((minimum, minimum+1, 10**9))
            lower, upper = -max(cb-1, k), max(2*(cb-1), cb-1+k)
            y = rng.choice((lower, upper, -cb, -1, 0, cb-1, cb, 2*cb, rng.randrange(lower, upper+1)))
            carry = rng.randrange(-2, 3)
            cv = int(index % 11 != 0)
            if index % 13 == 0:
                y = lower-1
            cell = (cv, cb, y, carry)
        cv, cb, y, carry = cell
        tag = (index*40503+17)&65535
        done = error = ov = oe = 0
        if not rst:
            state, age = "idle", 0
            accepted_base = generation = limit = reciprocal = cfg = cd = cc = ct = 0
            counts["resets"] += 1
        else:
            old_state = state
            if old_state == "idle" and begin:
                cfg, accepted_base, generation = 0, base, gen
                if not minimum <= base <= 10**9:
                    done = error = 1
                else:
                    state, age, reciprocal = "divide", 0, 0
            if old_state == "divide":
                age += 1
                reciprocal = (1 << age)//accepted_base
                if age == 4:
                    limit = shared_setup(n, accepted_base)["coefficient_limit"]
                if age == 96:
                    state = "check"
            if old_state == "check":
                state, done, cfg = "idle", 1, 1
            if old_state != "idle" and begin:
                state, done, error, cfg = "idle", 1, 1, 0
            if cancel:
                state, done, error, cfg = "idle", 0, 0, 0
                counts["setup_cancels"] += 1
            if cv:
                ct = tag
                lower, upper = -max(cb-1, k), max(2*(cb-1), cb-1+k)
                legal = minimum <= cb <= 10**9 and -2 <= carry <= 2 and lower <= y <= upper and -2*cb <= y+carry < 3*cb
                if legal:
                    cc, cd = divmod(y+carry, cb)
                    ov = 1
                else:
                    oe = 1
        counts["setup_success"] += bool(done and not error)
        counts["setup_errors"] += error
        counts["cell_valid"] += ov
        counts["cell_errors"] += oe
        rows.append((rst, cancel, begin, base, gen, cv, cb, y & ((1 << 33)-1), carry & 7, tag,
                     int(state != "idle"), done, error, cfg, accepted_base, generation,
                     f"{limit:024x}", f"{reciprocal:024x}", ov, oe, cd, cc & 7, ct))

    emit(rst=0)
    for base in (minimum, minimum+1, 604832956, 10**9):
        emit(begin=1, base=base)
        for _ in range(100):
            emit()
    for base in (0, 1, minimum-1, 10**9+1, 0xffffffff):
        emit(begin=1, base=base)
        emit()
    for age in (0, 1, 3, 11, 95, 96):
        emit(begin=1)
        for _ in range(age):
            emit()
        emit(cancel=1)
        emit(begin=1, base=10**9)
        for _ in range(99):
            emit()
    emit(begin=1)
    for _ in range(30):
        emit()
    emit(begin=1)
    emit()
    emit(begin=1)
    for _ in range(12):
        emit()
    emit(rst=0)
    emit(begin=1)
    for _ in range(99):
        emit()
    for base in (minimum-1, minimum, 10**9, 10**9+1):
        for y in (-4294967296, -max(base-1, k)-1, -max(base-1, k), -base, -1, 0,
                  base-1, base, 2*base, max(2*(base-1), base-1+k), 4294967295):
            for carry in range(-4, 4):
                emit(cell=(1, base, y, carry))
    text = f"A4CONTROL1 {aw} {len(rows)}\n"+"\n".join(" ".join(map(str, row)) for row in rows)+"\n"
    return text, dict(aw=aw, events=len(rows), **counts, sha256=hashlib.sha256(text.encode()).hexdigest(),
                     scope="scalar source expectations, not native evidence")
