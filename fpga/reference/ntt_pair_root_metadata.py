"""Isolated proposal: remove validity comparisons from pair root metadata.

Only root_read grants meaning to root_group/root_second. Invalid-cycle metadata
may differ. The event schedule, latency, issue/hold/commit tags and fault controls
remain unchanged. This model/source delta is not an integrated RTL qualification.
"""
import hashlib

SCHEDULE_SHA = '89c17cad846d9db0fa44e768a2f052b193d657fe633f425c77e9441b0512aa81'


def root_event(tick, groups, busy=True):
    """Reference contract from explicit A=2g, B=2g+7 events."""
    if not busy:
        return None
    if tick % 2 == 0 and 0 <= tick // 2 < groups:
        return tick // 2, 0
    if tick % 2 == 1 and 0 <= (tick - 7) // 2 < groups:
        return (tick - 7) // 2, 1
    return None


def direct_metadata(tick, width):
    """Unsigned fixed-width SV subtraction, including invalid warmup ticks."""
    if not 1 <= width <= 16 or not 0 <= tick < 1 << (width + 5):
        raise ValueError('unsupported scheduler width/tick')
    tw_mask = (1 << (width + 5)) - 1
    group = (((tick - 7) & tw_mask) >> 1) if tick & 1 else tick >> 1
    return group & ((1 << width) - 1), tick & 1


def schedule_source(original):
    if hashlib.sha256(original.encode()).hexdigest() != SCHEDULE_SHA:
        raise ValueError('frozen scheduler changed')
    old = """        root_second=read_b;
        root_group='0;
        if(read_a) root_group=GROUP_AW'(tick>>1);
        if(read_b) root_group=GROUP_AW'((tick-TW'(7))>>1);"""
    new = """        // Metadata is meaningful only when root_read is asserted.
        // Keep count/validity comparisons off the root-address data cone.
        root_second=tick[0];
        root_group=tick[0] ? GROUP_AW'((tick-TW'(7))>>1) : GROUP_AW'(tick>>1);"""
    if original.count(old) != 1:
        raise ValueError('ambiguous metadata delta')
    return original.replace('module genefer_ntt_pair_schedule #(',
                            'module genefer_ntt_pair_schedule_metadata #(').replace(old, new)
