"""Small canonical-controller case corpus, direct whole-integer expected words."""
import hashlib
import random

from fpga.reference.track_a4_control_model_v1 import canonicalize, canonical_plan
from fpga.reference.track_a4_blockcarry_model import arithmetic


def corpus(aw):
    if aw not in (5, 8):
        raise ValueError("canonical native preparation is AW5/AW8")
    n, t = 1 << aw, (1 << aw)//16
    minimum = arithmetic.minimum_base(n, 16)
    rng = random.Random(0xA4CA2026+aw)
    cases = []
    def add(base, values, mode=0, age=0, code=0):
        if mode == 0:
            result = canonicalize(values, base)
            modulus = base**n+1
            integer = sum(v*base**i for i,v in enumerate(values)) % modulus
            if integer == modulus-1:
                expected = [-1]+[0]*(n-1)
            else:
                expected = []
                for _ in range(n):
                    integer, digit = divmod(integer, base)
                    expected.append(digit)
            if expected != result["digits"]:
                raise AssertionError("independent canonical oracle mismatch")
            clocks = canonical_plan(n, result["passes"], result["special"])["clocks"]
            passes, special, maximum = result["passes"], int(result["special"]), max(expected)
        else:
            expected, clocks, passes, special, maximum = [0]*n, 3*(n+3)+t+20, 0, 0, 0
        cases.append((base, mode, age, code, clocks, passes, special, maximum,
                      tuple(v & 0xffffffff for v in values), tuple(v & 0xffffffff for v in expected)))
    for base in (minimum, 10**9):
        for values in ([0]*n, [base-1]*n, [-1]+[0]*(n-1), [0]*(n-1)+[base]):
            add(base, values)
        k = 2*n+384
        for _ in range(8):
            state = arithmetic.proposal.BlockState(tuple(rng.randrange(base) for _ in range(n)), base,
                tuple(rng.randrange(1-base,base) for _ in range(16)), tuple(rng.randrange(-k,k+1) for _ in range(16)))
            add(base, state.effective())
    # Declared-envelope counterexample requiring3passes, not asserted square-reachable.
    add(minimum, [0]*(n-1)+[2*minimum])
    for mode, code in ((1,3),(2,4),(3,4),(4,2)):
        add(minimum, [minimum-1]*n, mode=mode, age=3, code=code)
    for age in (1, n//2, n+1, n+2):
        add(minimum, [minimum-1]*n, mode=5, age=age)
    add(minimum-1, [0]*n, mode=6, code=8)
    add(minimum, [-2147483648]+[0]*(n-1), mode=7, code=2)
    lines = [f"A4CANON1 {aw} {len(cases)}"]
    for header in cases:
        lines.append(" ".join(map(str, header[:8])))
        lines.append(" ".join(map(str, header[8])))
        lines.append(" ".join(map(str, header[9])))
    text = "\n".join(lines)+"\n"
    return text, dict(aw=aw,cases=len(cases),normal=sum(c[1]==0 for c in cases),
        injected_errors=sum(c[1] in (1,2,3,4,6,7) for c in cases),resets=sum(c[1]==5 for c in cases),
        three_pass_cases=sum(c[5]==3 for c in cases),sha256=hashlib.sha256(text.encode()).hexdigest(),
        scope="case expectations only; sparse correction frontend excluded")
