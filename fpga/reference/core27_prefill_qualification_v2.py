"""Additive qualification recipes. Frozen AW5 runners and HDL stay unchanged."""
from functools import lru_cache
import random
import re

REMAINING = ('base_tag', 'late_host_error', 'omitted_tee', 'corrupted_tee')
AW16_GROUPS = tuple(f'{fault}-{row}' for fault in ('reset', 'host-error', 'carry-error')
                   for row in ('first', 'middle', 'final')) + ('base-change', 'reload-control')


def require(ok, why):
    if not ok: raise ValueError(why)


def batch_sources(root, recipe, names):
    require(tuple(names) == REMAINING, 'exact remaining four mutation contracts')
    # Tee mutants require removal of the producer's interception assertion.
    # Normalize this SAME simulation-only assertion removal across all roles;
    # each mutation still differs from the shared control by its own sole fault.
    control = None
    mutants = {}
    for name in names:
        fresh, mutant, contract = recipe.pair_sources(root, name)
        if name not in recipe.TEE_MUTANTS:
            fresh[recipe.CARRY] = recipe.tee_control(fresh[recipe.CARRY])
            mutant[recipe.CARRY] = recipe.tee_control(mutant[recipe.CARRY])
        require(control is None or fresh == control, 'byte-identical shared control contract')
        control = fresh
        changed = [key for key in fresh if fresh[key] != mutant[key]]
        require(set(changed) == ({recipe.CARRY} if name in recipe.TEE_MUTANTS else {recipe.CORE, recipe.BRIDGE}),
                'one intended fault plus exact bridge derivation')
        require(recipe.bridge(mutant[recipe.CORE]) == mutant[recipe.BRIDGE], 'mutant bridge derivation')
        contract = dict(contract, shared_control_stripped_guard='T5_EMIT_SIGNED32_REPRESENTATION',
                        changed_sources=changed)
        mutants[name] = (mutant, contract)
    return control, mutants


def aw16_harness(source):
    """Exact small derivation, recorded as a source artifact before compilation."""
    replacements = (
        ('// AW5-first targeted T5 qualification;', '// AW16 targeted T5 qualification;'),
        ('n==32 && a==604832956 && b==1000000000', 'n==65536 && a==604832956 && b==1000000000'),
        ('exact AW5 targeted profile', 'exact AW16 targeted profile'),
        ('need(changed || row=="final" || age==0,"non-final emission probes target commit E0 only");',
         'need(n/16>2 && (n/16)/2<n/16-1,"AW16 middle must be distinct from final");'),
        ('while(!d.done && elapsed<20000)', 'while(!d.done && elapsed<200000)'),
        ('while(!triggered && elapsed<20000)', 'while(!triggered && elapsed<200000)'),
        ('d.conversion_cycles==(fast?0:8)', 'd.conversion_cycles==(fast?0:4102)'),
    )
    for old, new in replacements:
        require(source.count(old) == 1, 'exact AW16 harness derivation anchor: '+old)
        source = source.replace(old, new, 1)
    return source


def group_commands(exe, vector, group):
    require(group in AW16_GROUPS, 'one bounded AW16 group')
    if group == 'base-change':
        return [(name, [str(exe), '--'+name, str(vector), 'control']) for name in ('changed-base', 'base-reject')]
    if group == 'reload-control':
        return [(group, [str(exe), '--reload-control', str(vector), 'control'])]
    fault, row = group.rsplit('-', 1)
    mode = {'reset':'--tail-reset', 'host-error':'--tail-error', 'carry-error':'--tail-carry-error'}[fault]
    return [(f'{group}-e{age}', [str(exe), mode, str(vector), str(age), row, 'control']) for age in range(7)]


def check_aw16_footer(output, argv):
    require(len(argv) in (4, 6) and argv[-1] == 'control', 'AW16 targeted command shape')
    mode = argv[1]
    simple = mode in ('--changed-base', '--base-reject', '--reload-control')
    require((simple and len(argv) == 4) or (not simple and len(argv) == 6 and
            mode in ('--tail-reset', '--tail-error', '--tail-carry-error')), 'AW16 targeted mode')
    age, row = ('0', 'none') if simple else (argv[3], argv[4])
    require(simple or (age in tuple(map(str, range(7))) and row in ('first', 'middle', 'final')), 'AW16 event coordinates')
    counts = (3, 3, 0) if mode == '--changed-base' else (2, 2, 1) if mode == '--base-reject' else (2, 2, 0) if mode == '--reload-control' else (1, 1, 1)
    expected = dict(mode=mode, age=age, row=row, row_index=str({'first':0, 'middle':2048}.get(row, 4095)),
                    middle_aliases_final='0', event_hits='1', successful=str(counts[0]),
                    readbacks=str(counts[1]), recoveries=str(counts[2]))
    matches = re.findall(r'^T5_TARGET_PASS (.*)$', output, re.M)
    require(len(matches) == 1, 'one AW16 footer')
    tokens = [x.split('=', 1) for x in matches[0].split()]
    require(all(len(x) == 2 for x in tokens) and len({x[0] for x in tokens}) == len(tokens), 'unique AW16 footer fields')
    require(dict(tokens) == expected, 'command-bound AW16 footer')
    return expected


def integer_square(digits, base, bit=0):
    """Ordinary integer modulo b**N+1, with divide-and-conquer radix conversion.

    No NTT, candidate carry model, floating point, or quadratic per-digit powers.
    The terminal b**N representative is the canonical [-1, 0, ...] encoding.
    """
    n = len(digits)
    require(n > 0 and n & (n-1) == 0 and base > 1 and bit in (0, 1), 'integer oracle profile')
    @lru_cache(None)
    def power(size): return base**size
    def pack(lo, size):
        if size <= 32:
            value = 0
            for x in reversed(digits[lo:lo+size]): value = value*base+int(x)
            return value
        half = size//2
        return pack(lo, half)+power(half)*pack(lo+half, half)
    value = pack(0, n)
    value = value*value*(1 << bit) % (power(n)+1)
    if value == power(n): return [-1]+[0]*(n-1)
    result = [0]*n
    def unpack(value, lo, size):
        if size <= 32:
            for i in range(lo, lo+size): value, result[i] = divmod(value, base)
            require(value == 0, 'integer oracle leaf range')
        else:
            half = size//2
            high, low = divmod(value, power(half))
            unpack(low, lo, half); unpack(high, lo+half, half)
    unpack(value, 0, n)
    return result


def target_vectors(aw=16):
    require(aw in (5, 16), 'bounded oracle address width')
    n, a, b = 1 << aw, 604832956, 10**9
    rng = random.Random(20260930)
    original = [rng.randrange(a) for _ in range(n)]
    first = integer_square(original, a)
    second = integer_square(first, b)
    third = integer_square(second, b, 1)
    require(first[0] >= 2*n+5, 'base-reject vector violates the smaller base at the first digit')
    return f'{n} {a} {b}\n'+'\n'.join(' '.join(map(str, row)) for row in (original, first, second, third))+'\n'


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    import socket
    parser = argparse.ArgumentParser(description='Bounded-dispatch AW16 ordinary-integer oracle worker')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(__debug__ and socket.gethostname() == 'aethia', 'native-dispatch oracle worker only')
    require(not args.output.exists(), 'fresh oracle output')
    with args.output.open('x') as stream: stream.write(target_vectors(16))
