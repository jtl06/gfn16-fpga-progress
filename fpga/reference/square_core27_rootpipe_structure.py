"""Exact whole-core NTT backend substitution; integration is not yet simulated."""
import hashlib

CORE_SHA = '75eb580540fc6a7939f824182d244123e03e3b780e65e57722352564b145b648'
HOST_SHA = 'd431f5193c45ff6128a15d7dcb353a5cc8f49f2b9b3fa6ec40f0c0d9f4e4851e'
BENCH_SHA = 'bd0ca4ebf1a501f3adef25bdcec08202d6f1b84be9bbfa618d44c6c8469342a4'


def pinned(text, expected):
    if hashlib.sha256(text.encode()).hexdigest() != expected:
        raise ValueError('frozen integration ancestor changed')


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('ambiguous integration delta: ' + old)
    return text.replace(old, new)


def core_source(original):
    pinned(original, CORE_SHA)
    text = once(original,
        '// Isolated atomic27 precision-stream integration; frozen cached basis and arithmetic.\n'
        '// Ancestor core47f61c26; only carry storage/control is changed. No input fusion,\n'
        '// generated roots, CRT replacement, or root-recurrence multiplier replacement.',
        '// Isolated root-pipeline integration from frozen precision-stream core75eb.\n'
        '// Only the NTT backend/adapter and default lane parameter change.\n'
        '// Conversion, cached root generation, CRT, carry and outer FSM are unchanged.')
    text = once(text, 'module genefer_square_core27_stream #(',
                'module genefer_square_core27_stream_rootpipe #(')
    text = once(text, 'parameter int NTT_LANES=16', 'parameter int NTT_LANES=64')
    text = once(text, 'genefer_ntt_banked27_host_engine #(',
                'genefer_ntt_banked27_host_rootpipe_engine #(')
    # The pinned ancestor has one extra empty EOF line; normalize that alone.
    assert text.endswith('endmodule\n\n')
    return text[:-1]


def host_source(original):
    pinned(original, HOST_SHA)
    text = once(original, '// Narrow vector-host wrapper around the frozen wide arithmetic engine.',
                '// Isolated narrow-host adapter around the qualified root-pipeline engine.')
    text = once(text, 'module genefer_ntt_banked27_host_engine #(',
                'module genefer_ntt_banked27_host_rootpipe_engine #(')
    return once(text, 'genefer_ntt_banked27_engine #(',
                'genefer_ntt_banked27_rootpipe_engine #(')


def ntt_cycles(aw, lanes=64, drain=9):
    if not 1 <= aw <= 16 or lanes != 64 or drain not in (7, 9):
        raise ValueError('only the compared 64-lane integration profiles are modeled')
    n = 1 << aw
    point = (n + lanes - 1) // lanes + drain
    transform = aw * (max(1, n // (2 * lanes)) + drain + 1)
    return 3 * point + 2 * transform + 10  # Two outer FSM clocks per operation.


def bench_source(original):
    pinned(original, BENCH_SHA)
    text = original.replace('Vgenefer_square_core27_stream', 'Vgenefer_square_core27_stream_rootpipe')
    text = once(text,
        '// explicit45-clock reservation wait after a52-clock warm N2 NTT.',
        '// explicit35-clock reservation wait after a62-clock warm N2 NTT.')
    text = once(text, 'n==2 && cache_before==15 && d.crt_cycles!=108',
                'n==2 && cache_before==15 && d.crt_cycles!=98')
    text = once(text, '                uint64_t elapsed=0;',
                '                uint64_t elapsed=0; bool abort_reached=false;')
    for condition in ('elapsed>=target', 'd.crt_cycles>=63',
                      'd.root_phases_loaded==phase && d.root_cycles>uint64_t(phase)*(n+2)+2',
                      'phase>=3'):
        text = once(text, f'if({condition})break;',
                    f'if({condition}){{abort_reached=true;break;}}')
    text = once(text, '                if(cmd=="ABORT") { reset();++aborts;continue; }',
                '''                if(cmd=="ABORT") {
                    if(!abort_reached || !d.busy || d.done)
                        throw std::runtime_error("abort did not interrupt requested live phase "+label);
                    reset();++aborts;continue;
                }''')
    return once(text, '                std::cout<<label<<" cycles="', '''                // 64-lane integration: three point phases, two transforms,
                // nine-clock drains, plus two outer FSM clocks per operation.
                unsigned lg=0;for(unsigned size=n;size>1;size>>=1)++lg;
                const uint64_t expected_ntt=3*((uint64_t(n)+63)/64+9)+
                    2*uint64_t(lg)*(std::max<uint64_t>(1,uint64_t(n)/128)+10)+10;
                if(d.ntt_cycles!=expected_ntt)
                    throw std::runtime_error("rootpipe NTT cycle model mismatch");
                std::cout<<label<<" cycles="''')
