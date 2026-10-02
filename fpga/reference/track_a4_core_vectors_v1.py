"""Small whole-integer oracle for the real A4 core; never performs an NTT."""
import hashlib
import random


def canonical(value, base, n):
    modulus = base**n + 1
    value %= modulus
    if value == modulus - 1:
        return [-1] + [0] * (n-1)
    words = []
    for _ in range(n):
        value, word = divmod(value, base)
        words.append(word)
    assert value == 0
    return words


def integer(words, base):
    return sum(word * base**i for i, word in enumerate(words))


def corpus(aw=5):
    if aw not in (5, 8):
        raise ValueError("small-N whole integer oracle only")
    n = 1 << aw
    minimum = max(2*n+5, (2*(2*n+384)+2)//3+1)
    rows = []
    rng = random.Random(0xA400+aw)
    squares = []
    base = minimum
    words = [0]*n
    prefilled = False
    roots = False

    def add(op, address=0, word=0, double=0, expected=0, valid=1, cold=-1, load=-1):
        rows.append((op, address, word & 0xffffffff, base, double, expected & 0xffffffff,
                     valid, int(prefilled), cold, load))

    def reload(new_base, values):
        nonlocal base, words, prefilled, roots
        base = new_base
        prefilled = roots = False
        add(0, valid=0)
        for i, value in enumerate(values):
            add(1, i, value, valid=int(i==n-1))
        words = canonical(integer(values, base), base, n)

    def square(double=0):
        nonlocal words, prefilled, roots
        cold, load = int(not prefilled), int(not roots)
        words = canonical((integer(words, base)**2) << double, base, n)
        prefilled = roots = True
        add(5, double=double, cold=cold, load=load)
        squares.append((cold, load, double))

    def read_all():
        nonlocal prefilled
        prefilled = False
        for i, value in enumerate(words):
            add(2, i, expected=value)

    for new_base, values in (
        (minimum, [-1]+[0]*(n-1)),
        (minimum, [minimum-1]*n),
        (1000000000, [rng.randrange(1000000000) for _ in range(n)]),
    ):
        reload(new_base, values)
        square(); square(1); square()
        read_all()
        square(1)  # canonical readback invalidates prefill but preserves roots
        read_all()
    # Host mutation and base reinterpretation between actual squares.
    prefilled = False
    words[n-1] = -1
    words = canonical(integer(words, base), base, n)
    add(3, n-1, -1)
    square(); read_all()
    reload(minimum, [i % minimum for i in range(n)])
    base = minimum+1000
    add(4)
    square(1); read_all()
    text = f"A4CORE1 {aw} {len(rows)}\n" + "\n".join(" ".join(map(str, row)) for row in rows) + "\n"
    return text, dict(aw=aw,commands=len(rows),squares=len(squares),readbacks=sum(r[0]==2 for r in rows),
        cold_squares=sum(s[0] for s in squares),profile_loads=sum(s[1] for s in squares),
        hold_checks=2*len(rows),sha256=hashlib.sha256(text.encode()).hexdigest(),
        scope="Real whole-square commands; integer modulo b**N+1 oracle, no numeric NTT")
