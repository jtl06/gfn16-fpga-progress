"""Small P8/P16 correction model only; never executes a full-N transform."""
from fpga.reference.stream_ntt_model import FIELDS, bit_reverse
from fpga.reference.stream27_field_compile_param_v1 import compile_transform
from fpga.reference.stream27_field_plan import root_word


def plan(lanes, field):
    assert lanes in (8, 16) and field in (0, 1, 2)
    return compile_transform(lanes, field, lanes)['topology']


def roots(lanes, field):
    p = plan(lanes, field)
    return [root_word(p, s['stage'], s['root_stream_for_pair'][j], 0, field)
            for s in p['stages'] for j in range(lanes // 2)]


def transform(physical, field):
    lanes = len(physical)
    p = plan(lanes, field)
    prime = FIELDS[field][0]
    assert all(0 <= x < prime for x in physical)
    data = list(physical)
    ri = pow(1 << 32, -1, prime)
    table = roots(lanes, field)
    for s in p['stages']:
        old = data[:]
        for j, (a, b) in enumerate(s['pairs']):
            data[a] = (old[a] + old[b]) % prime
            data[b] = (old[a] - old[b]) * table[s['stage'] * (lanes // 2) + j] * ri % prime
    return [data[i] for i in p['terminal_wire']]


def direct(physical, field):
    lanes = len(physical)
    prime, generator = FIELDS[field]
    pw = lanes.bit_length() - 1
    natural = [physical[bit_reverse(i, pw)] for i in range(lanes)]
    omega = pow(generator, (prime - 1) // lanes, prime)
    result = [sum(natural[j] * pow(omega, j*k, prime) for j in range(lanes)) % prime for k in range(lanes)]
    return [result[bit_reverse(i, pw)] for i in range(lanes)]


def calendar(lanes, bfs=2):
    """Literal two-vector controller calendar; BF issue->registered capture=6."""
    assert lanes in (8, 16) and bfs == 2
    waves = lanes // bfs
    stages = lanes.bit_length() - 1
    start = 2  # input A edge0, input B edge1, first issue edge2
    events = []
    for stage in range(stages):
        for wave in range(waves):
            events.append(dict(stage=stage, wave=wave, issue=start+wave, capture=start+wave+6))
        start += waves + 6  # next issue follows the final capture
    output_a, output_b = start, start+1
    old_first = stages*6-1
    return dict(lanes=lanes, bfs=bfs, accepted_edges=[0,1], events=events,
                output_edges=[output_a,output_b], next_pair_earliest=start+2,
                old_transform_latency=old_first, new_transform_latency=output_a,
                transform_latency_delta=output_a-old_first,
                fullsize_cache_latency=stages*6+18+output_a-old_first,
                scope='Two canonical vectors; exact proposed controller schedule, native confirmation required')


def check():
    cases = 0
    for lanes in (8,16):
        for field in range(3):
            prime = FIELDS[field][0]
            for case in range(32):
                physical = [((case+7)*(i+13)*7919 + (prime-1 if i & 1 else 0)) % prime for i in range(lanes)]
                assert transform(physical,field) == direct(physical,field)
                cases += 1
            p = plan(lanes,field)
            for stage,spec in enumerate(p['stages']):
                expected=[((j & ((1<<stage)-1)) | ((j>>stage)<<(stage+1))) for j in range(lanes//2)]
                assert [(a,a|(1<<stage)) for a in expected] == spec['pairs']
    return dict(status='PASS_small_reference_and_symbolic_calendar_ONLY', cases=cases,
                calendars=[calendar(p) for p in (8,16)], native_executed=False)


if __name__ == '__main__':
    import json
    print(json.dumps(check(),indent=2))
