"""Tiny-N targeted native vectors from direct ordinary integer arithmetic.

Deliberately no candidate/NTT/carry-model imports. AW5 only in this preparer.
"""
import random


def square(digits, base, bit=0):
    n = len(digits)
    value = sum(int(x)*base**i for i, x in enumerate(digits))
    value = value*value*(1 << bit) % (base**n+1)
    if value == base**n: return [-1]+[0]*(n-1)
    result = []
    for _ in digits:
        value, digit = divmod(value, base)
        result.append(digit)
    assert value == 0
    return result


def target_vectors(aw=5):
    if aw != 5: raise ValueError('targeted first gate is AW5 only')
    n, a, b = 1 << aw, 604832956, 10**9
    rng = random.Random(20260930)
    original = [rng.randrange(a) for _ in range(n)]
    first = square(original, a)
    second = square(first, b)
    third = square(second, b, 1)
    return f'{n} {a} {b}\n'+'\n'.join(' '.join(map(str, x)) for x in (original, first, second, third))+'\n'
