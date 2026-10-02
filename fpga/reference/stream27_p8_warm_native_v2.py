"""Independent lease ledger successor; frozen v1 failures stay failures.

P8 AW8 warm spacing outlasts the previous lease; full-size spacing overlaps.
No RTL, frame vectors, arithmetic oracle, timing or fault expectation changes.
"""
from collections import deque
from pathlib import Path
from fpga.reference import stream27_p8_warm_native_v1 as parent

ROOT = parent.ROOT
CPP, HEADER, REFERENCE = parent.CPP, parent.HEADER, parent.REFERENCE
BENCH, BENCH_PARENT = parent.BENCH, parent.BENCH_PARENT
FIT_MANIFEST, FIT_RECEIPT = parent.FIT_MANIFEST, parent.FIT_RECEIPT
PINS = parent.PINS
need, sha, role_arguments = parent.need, parent.sha, parent.role_arguments
PARENT_SHA = '509d9a9b602bb17d0112f63d573983a32f3bee1750693c4c60cbda235b66fc2c'
# Independently transcribed from pinned actual epoch-protocol instantiations.
CALENDARS = {8: dict(sink=178, rows=32, interval=221),
             16: dict(sink=16610, rows=8192, interval=16653)}


def verify(root=ROOT):
    path = Path(root)/'reference/stream27_p8_warm_native_v1.py'
    need(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == PARENT_SHA,
         'P8_WARM_FROZEN_NATIVE_V1_DRIFT')
    return parent.verify(root)


def lease_ledger(starts, sink, rows):
    """Post-edge valid bits, selected from pre-edge occupancy like actual RTL.

    Epoch protocol valid clears on last sink sampling edge start+sink+rows-1.
    A same-edge new admission uses a previously free bank; a release cannot
    make an occupied bank available for that edge's prospective lookup.
    """
    need(type(sink) is int and sink > 0 and type(rows) is int and rows >= 2 and
         all(type(s) is int and s >= 0 for s in starts) and len(starts) == len(set(starts)),
         'P8_WARM_LEASE_ARGUMENTS')
    starts = set(starts); owners = deque(); peak = 0; accepted = []; rejected = []; released = []
    terminal = max(starts, default=0) + sink + rows
    for edge in range(terminal):
        old = tuple(owners)
        incoming = edge in starts
        accept = incoming and len(old) < 2
        if incoming: (accepted if accept else rejected).append(edge)
        owners = deque(end for end in old if end != edge)
        if edge in old: released.extend([edge]*old.count(edge))
        if accept: owners.append(edge+sink+rows-1)
        peak = max(peak, len(owners))
    need(not owners, 'P8_WARM_LEASE_DRAIN')
    return dict(peak=peak, accepted=accepted, rejected=rejected, released=released)


def ownership_contract(aw, field):
    role_arguments(aw, field); c = CALENDARS[aw]
    groups = [[0], [0, c['interval']], [0, c['interval']+16]]
    ledgers = [lease_ledger(group, c['sink'], c['rows']) for group in groups]
    need(all(not row['rejected'] for row in ledgers), 'P8_WARM_NORMAL_LEASE_ADMISSION')
    return dict(calendar=c, post_edge_peak=max(row['peak'] for row in ledgers),
                first_release=c['sink']+c['rows']-1, starts=groups, ledgers=ledgers,
                semantics='Pre-edge free-bank selection; post-edge valid clear on last sink, simultaneous admission/release atomic.')


def counts(aw, field):
    result = parent.counts(aw, field)
    result['peak_owners'] = ownership_contract(aw, field)['post_edge_peak']
    return result


def footer(aw, field):
    return f'S4_P8_WARM_PASS aw={aw} p=8 field={field} ' + ' '.join(
        f'{key}={value}' for key, value in counts(aw, field).items()) + '\n'


def contracts(aw, field):
    return dict(counts=counts(aw, field), normal=dict(returncode=0, stdout=footer(aw, field), stderr=''),
                oracle=dict(returncode=1, stdout='', stderr='S4_P8_WARM_NEGATIVE_ORACLE_REJECT\n'),
                peak=dict(returncode=1, stdout='', stderr='S4_P8_WARM_NEGATIVE_PEAK_REJECT\n'))


def validate(stdout, stderr, returncode, config, assets):
    need(set(config) == {'aw', 'field', 'mode'} and config['mode'] in ('normal', 'oracle', 'peak') and assets == {},
         'P8_WARM_NATIVE_V2_CONFIG')
    expected = contracts(config['aw'], config['field'])[config['mode']]
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
         (stdout, stderr, returncode) == (expected['stdout'], expected['stderr'], expected['returncode']),
         'P8_WARM_TYPED_OUTPUT')
    return dict(status='PASS_expected_contracts', aw=config['aw'], p=8, field=config['field'], mode=config['mode'],
                promotion_allowed=False, scope='P8 one-field numeric/cycle/fault plus exact independent lease ledger; not full core/PRP/clock promotion.')


def compile_bench(bundle, field):
    verify(); text, header = parent.compile_bench(bundle, field); aw = bundle['parameters']['AW']
    c = CALENDARS[aw]; g = bundle['geometry']
    need((g['sink_accept'], g['rows'], g['warm_interval']) == (c['sink'], c['rows'], c['interval']),
         'P8_WARM_SOURCE_CALENDAR_DRIFT')
    peak = ownership_contract(aw, field)['post_edge_peak']
    header += f'constexpr unsigned EXPECTED_PEAK={peak};\n'
    changes = [
        ('static bool negative_oracle=false;', 'static bool negative_oracle=false,negative_peak=false;'),
        ('counts.peak=std::max(counts.peak,unsigned(d.owner_count));',
         '''unsigned expected_owners=0;
        for(const auto& f:frames)
            expected_owners+=tick>=f.start && tick<f.start+SINK+T-1;
        need(unsigned(d.owner_count)==expected_owners,"S4_P8_OWNER_LEDGER tick="+std::to_string(tick));
        counts.peak=std::max(counts.peak,unsigned(d.owner_count));'''),
        ('need(argc==1 || negative_oracle,"S4_ARGUMENTS");',
         'negative_peak=argc==2 && std::string(argv[1])=="--negative-peak";\n'
         '        need(argc==1 || negative_oracle || negative_peak,"S4_ARGUMENTS");'),
        ('need(!negative_oracle,"S4_P8_WARM_NEGATIVE_ORACLE_MISSED");',
         '''need(counts.peak==EXPECTED_PEAK,"S4_P8_WARM_EXACT_PEAK_LEDGER");
        if(negative_peak){
            const unsigned wrong_peak=EXPECTED_PEAK==1?2:1;
            need(counts.peak==wrong_peak,"S4_P8_WARM_NEGATIVE_PEAK_REJECT");
        }
        need(!negative_oracle,"S4_P8_WARM_NEGATIVE_ORACLE_MISSED");'''),
    ]
    for old, new in changes:
        need(text.count(old) == 1, 'P8_WARM_LEASE_BENCH_ANCHOR '+old[:45]); text = text.replace(old, new)
    return text, header
