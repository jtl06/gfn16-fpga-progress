"""Independent preedge D16 metadata reference; no RTL authority override."""
import random


def check(width, cycles=10000, seed=1503):
    rng = random.Random(seed + width)
    # Arbitrary payload initialization is deliberate: neither implementation
    # resets data, and only the original reset valid pipe authorizes a sample.
    stages = [rng.getrandbits(width) for _ in range(16)]
    memory = [rng.getrandbits(width) for _ in range(16)]
    held = stages[0]
    prefetched = rng.getrandbits(width)
    valid = [False] * 16
    ptr = filled = accepted = compared = 0
    for edge in range(cycles):
        reset = edge < 3 or edge % 257 in (0, 1) or edge % 509 == 0
        joined = rng.randrange(5) != 0
        stopped = edge % 71 in range(6)
        word = rng.getrandbits(width)
        if reset:
            # Asynchronous reset affects eligibility/pointer, not RAM/held.
            ptr = filled = 0
            valid = [False] * 16
        if valid[15] and not reset:
            assert filled == 16 and prefetched == stages[15], (width, edge)
            compared += 1
        read = (ptr + 1) % 16
        assert read != ptr  # Unconditional, including malformed/held reset.
        incoming = word if joined else held
        next_prefetched = memory[read]
        memory[ptr] = incoming
        stages = [incoming] + stages[:15]
        if joined:
            held = word
        prefetched = next_prefetched
        if not reset:
            ptr = read
            filled = min(16, filled + 1)
            valid = [joined and not stopped] + valid[:15]
            accepted += int(joined and not stopped)
    assert compared > cycles // 2
    return dict(width=width, edges=cycles, accepted=accepted,
                eligible_preedge_samples=compared, collisions=0,
                reset_payload_retained=True, latency_delta=0)


def run():
    return [check(w) for w in (30, 38)]


def check_numeric(width, delay, cycles=20000):
    """Check raw all-bit data after D fresh edges, not masking-only agreement.

    Independent literal shift and ring models start with unrelated payload.
    Async reset resets the ring counter only; writes continue while held reset.
    The actual CRT first eligible consumers are separately represented below.
    """
    assert (width, delay) in ((27,5),(27,6),(53,6))
    rng = random.Random(151503 + width + delay)
    stages = [rng.getrandbits(width) for _ in range(delay)]
    memory = [rng.getrandbits(width) for _ in range(8)]
    q = rng.getrandbits(width)
    pointer = filled = fresh = comparisons = eligible = 0
    validity = [False] * 16
    offset = 9-delay
    for edge in range(cycles):
        reset = edge < 4 or edge % 311 < 4 or edge % 503 == 7
        if reset:
            pointer = filled = fresh = 0
            validity = [False] * 16
        # CRT preedge consumer is E7 for r1/d3 and E14 for x12.
        consumer_age = 13 if width == 53 else 6
        if validity[consumer_age]:
            assert filled == delay and q == stages[-1]
            eligible += 1
        if fresh >= delay:
            assert q == stages[-1]
            comparisons += 1
        read = (pointer + offset) % 8
        assert read != pointer  # Covers every pointer, including held reset.
        pattern = edge % (width+4)
        word = ((1<<width)-1 if pattern==width else 0 if pattern==width+1
                else 1<<pattern if pattern<width else rng.getrandbits(width))
        q = memory[read]
        memory[pointer] = word
        stages = [word] + stages[:-1]
        if not reset:
            pointer = (pointer+1) % 8
            filled = min(delay,filled+1)
            fresh += 1
            validity = [bool(rng.randrange(3)) and edge%73<65] + validity[:-1]
            if fresh >= delay:
                assert q == stages[-1]
                comparisons += 1
    assert comparisons > cycles and eligible > cycles // 3
    return dict(width=width,delay=delay,ring_depth=8,read_offset=offset,
                edges=cycles,raw_head_comparisons=comparisons,
                eligible_CRT_preedge_samples=eligible,collisions=0,
                payload_reset=False,latency_delta=0)


def numeric_run():
    return [check_numeric(w,d) for w,d in ((27,6),(27,5),(53,6))]
