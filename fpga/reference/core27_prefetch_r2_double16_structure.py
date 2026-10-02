"""Exact double16 source delta and abstract FF/mux model; NOT HDL execution.

Sixteen same-edge selectors replace one accepted-start register. Five control
substitutions plus module identity are the entire permitted RTL delta. Reset,
accepted/rejected start behavior, arithmetic, masks, latency, FSM and counters
are unchanged. +15 declared FF bits does not imply a fitted FF/ALM delta.
"""
import hashlib
from pathlib import Path

ANCESTOR = 'genefer_square_core27_stream_prefetch_r2_host_broadcast'
CANDIDATE = ANCESTOR + '_double16'
ANCESTOR_SHA = 'ea2b518880cb1c3191c71d35a232d2483aee82046ecd4d930d7ac7ffa07a80e1'
CANDIDATE_SHA = '8b5253a6325c48999045838d775973d084b3f4e78dc87c39a0cc76e288d21519'
FROZEN_PINS = {
    ANCESTOR: ANCESTOR_SHA,
    'genefer_ntt_banked27_prefetch_r2_host_broadcast_engine':
        '0960922332ea919a72a1ee591a70006bba76af7f26bc5308b68f50e327583e29',
    'genefer_ntt_banked27_prefetch_r2_engine':
        '552d273972af97c3363b77df0798e08a962d283869bcc95159f378a0f0070b17',
    'genefer_carry_prefix_stream_precision':
        'ba7ce9d0c1a99ad959bfe9909c62f341fabd537c76f196c5bcb6394c161296d3',
}
SUBSTITUTIONS = (
    ('module ' + ANCESTOR + ' #(', 'module ' + CANDIDATE + ' #('),
    ('logic double_reg;',
     '(* preserve, dont_merge *) logic [IO_WIDTH-1:0] double_lane_q;'),
    ('double_reg ? (coefficient_words[h] <<< 1)',
     'double_lane_q[h] ? (coefficient_words[h] <<< 1)'),
    ('double_reg ? (coefficient <<< 1)', 'double_lane_q[0] ? (coefficient <<< 1)'),
    ('double_reg<=0;', "double_lane_q<='0;"),
    ('double_reg<=double_bit;', 'double_lane_q<={IO_WIDTH{double_bit}};'),
)
IO_WIDTH = 16


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def expected(original):
    require(sha(original) == ANCESTOR_SHA, 'frozen ancestor identity')
    result = original
    for old, new in SUBSTITUTIONS:
        require(result.count(old) == 1, 'ambiguous source anchor: ' + old)
        result = result.replace(old, new)
    return result


def validate_files(root):
    kernel = Path(root) / 'rtl/kernel'
    for name, pin in FROZEN_PINS.items():
        require(sha((kernel / (name + '.sv')).read_text()) == pin,
                'frozen dependency identity: ' + name)
    original = (kernel / (ANCESTOR + '.sv')).read_text()
    actual = (kernel / (CANDIDATE + '.sv')).read_text()
    require(actual == expected(original), 'unreviewed double16 source delta')
    require(sha(actual) == CANDIDATE_SHA, 'candidate identity')
    return {'rtl/kernel/' + CANDIDATE + '.sv': sha(actual)}


def accepts_start(base, aw=16, ntt_lanes=64):
    """Pure model of the unchanged IDLE/start parameter guard, not the FSM."""
    require(type(base) is int and 0 <= base <= 0xffffffff, '32-bit base')
    require(type(aw) is int and 1 <= aw <= 16, 'supported elaboration AW')
    require(type(ntt_lanes) is int, 'integer lane parameter')
    return 2 <= base <= 1_000_000_000 and ntt_lanes == 64 and base > 2 * (1 << aw) + 4


def control_trace(events, *, wrong_delay=False, wrong_free_running=False):
    """Abstract transition model only: no controller/RAM/HDL simulation.

    assert/release are asynchronous events. Each edge event is the tuple
    ('edge', idle, start, valid_configuration, double_bit). Busy/rejected starts
    hold the selector. Configuration is supplied by the caller, not inferred
    from an incomplete FSM. Both intentionally wrong models are test witnesses.
    """
    old = 0
    copies = [0] * IO_WIDTH
    reset = False
    trace = []
    for event in events:
        require(isinstance(event, tuple) and event, 'event tuple')
        if event == ('assert',):
            reset = True; old = 0; copies = [0] * IO_WIDTH
        elif event == ('release',):
            reset = False
        else:
            require(len(event) == 5 and event[0] == 'edge' and
                    all(type(value) is int and value in (0, 1) for value in event[1:]),
                    'edge control bits')
            _, idle, start, valid_configuration, source = event
            previous = old
            accepted = idle and start and valid_configuration
            if reset:
                old = 0; copies = [0] * IO_WIDTH
            else:
                if accepted:
                    old = source
                if accepted or wrong_free_running:
                    copies = [previous if wrong_delay else source] * IO_WIDTH
        trace.append((old, tuple(copies)))
    return trace


def carry_mux(coefficient, double_selector):
    """Signed96 mux and shift truncation; not a new coefficient-domain proof."""
    require(type(coefficient) is int and -(1 << 95) <= coefficient < (1 << 95),
            'signed96 coefficient')
    require(type(double_selector) is int and double_selector in (0, 1), 'selector bit')
    raw = (coefficient << double_selector) & ((1 << 96) - 1)
    return raw - (1 << 96) if raw & (1 << 95) else raw
