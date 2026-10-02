"""Pure source/role/calendar guards; no compiler, HDL execution or host action.

The native probe is an AW5/AW8 three-field component composition. Its ROM
collector is an observer, not engine-header/cache/whole-operation qualification.
Normal cancel/FAILED are established before a posedge and obey the frozen
full-clock contract; no prior RAM commit is rolled back. A pending-transfer
subcycle cancel is deliberately outside that contract and must quarantine.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOP = 'genefer_anext_field_reset_probe_v1'
SV = f'rtl/tb/{TOP}.sv'
CPP = 'rtl/tb/anext_field_reset_probe_v1.cpp'
COMPILED = (
    SV,
    'rtl/kernel/genefer_anext_field_reset_release_v1.sv',
    'rtl/kernel/genefer_track_a4_field_transfer_v2.sv',
    'rtl/kernel/genefer_track_a4_blockroute_v2.sv',
    'rtl/kernel/genefer_sdp_ram32.sv',
    'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv',
    'rtl/kernel/genefer_a10_profile3_v1.sv',
)
PINS = {
    SV: 'd1f9b9dc8b59c837da79478872937a3137d7f19737460d10d6516ddfa8995c48',
    CPP: 'a658bf4d5bf938bda6315e179babac4cc3231235a2dd9cdf8ac976b1d445870d',
    COMPILED[1]: '41ac94d2480a27d88678b37f4bb571ef2374e34a80210775d55b0fc0bad20e6e',
    COMPILED[2]: 'dd0e0401965741201fcfa8fddfacd530d8fec3da66030c8d307a480d54244688',
    COMPILED[3]: '0d292ef6072f250f9255b758319e0754b0265a3d26be694601bb96b25a9e1cfa',
    COMPILED[4]: '993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0',
    COMPILED[5]: '501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
    COMPILED[6]: '526ede3d3bbb7bd43baf9f6830a087c5ba3f89ee0c6f5d32a8de24e57f27fd4b',
}
NEGATIVES = {
    '--negative-bad-generation': (41, 'ANEXT_RESET_NEGATIVE_BAD_GENERATION\n'),
    '--negative-early-ready': (42, 'ANEXT_RESET_NEGATIVE_EARLY_READY\n'),
    '--negative-stale-valid': (43, 'ANEXT_RESET_NEGATIVE_STALE_VALID\n'),
}
PRIMES = (104857601, 69206017, 67239937)
GENERATORS = (3, 5, 10)


def need(ok, why):
    if not ok:
        raise ValueError(why)


def geometry(aw):
    need(type(aw) is int and aw in (5, 8), 'ANEXT_RESET_COMPONENT_AW5_AW8_ONLY')
    return dict(aw=aw, fields=3, banks_per_field=128, banks=384,
                words=1 << aw, offsets=1 << (aw-4), rw=max(1, aw-7),
                depth=1 << max(0, aw-7))


@dataclass(frozen=True)
class CalendarRow:
    phase: str
    edges: int
    read_accepts: int = 0
    write_accepts: int = 0
    physical_read_edges: int = 0
    physical_write_edges: int = 0
    caller_responses: int = 0
    mult_accepts: int = 0
    mult_completed: int = 0
    rom_starts: int = 0
    rom_word_edges: int = 0
    rom_completed: int = 0
    reloads: int = 0
    tail_windows: int = 0


def calendar_rows(aw):
    """Source-derived planned events, never measured-output calibration.

    Units are three-field edges/transactions, not number of field lanes. Ten
    full image writes cover all N independently expected flat words per field.
    Thirteen complete checks (fourteen at AW8) read retained/reloaded images. Cancel age3
    has already committed its leaf read but cannot publish the caller result.
    """
    t = geometry(aw)['offsets']
    rows = [
        CalendarRow('initial-reset-prime-fill-check', 22+2*t,
                    t, t+1, t, t+1, t, 1, 1, 1, 4, 1, 1),
        CalendarRow('eight-ordinary-Montgomery-products', 12, mult_accepts=8, mult_completed=8),
        CalendarRow('real-four-word-ROM-restart', 7, rom_starts=1, rom_word_edges=4, rom_completed=1),
    ]
    if aw == 8:
        rows.append(CalendarRow('actual-bank0-row0-read-row1-write-check', 13+t,
                                t+1, 1, t+1, 1, t+1))
    rows.append(CalendarRow('disjoint-mask-read-write-check-tail', 35+t,
                            t+1, 1, t+1, 1, t+1, tail_windows=1))
    for age in (0, 1, 3):
        rows.append(CalendarRow(f'full-clock-cancel-age{age}-reload', 46+age+2*t,
                                t+1, t+1, t+int(age >= 2), t+1, t,
                                2, 1+int(age >= 3), 2, 4+age, 1, 1, 1))
    rows += [
        CalendarRow('registered-steady-FAILED-reload', 48+2*t,
                    t+1, t+1, t, t+1, t, 1, 1, 1, 4, 1, 1, 1),
        CalendarRow('quiet-transfer-subcycle-leaf-reset-retention', 32+t,
                    t, 0, t, 0, t, 1, 0, 1, 0, 0, 0, 1),
        CalendarRow('external-reset-pending-transfer-mult-ROM', 52+3*t,
                    2*t+1, t+1, 2*t, t+1, 2*t, 2, 1, 2, 5, 1, 1, 1),
        CalendarRow('external-reset-after-ROM-word3-before-collector', 49+2*t,
                    t, t+1, t, t+1, t, 1, 1, 2, 8, 1, 1, 1),
    ]
    for name in ('malformed-response-tag', 'missing-response', 'illegal-pending-subcycle-cancel'):
        rows.append(CalendarRow(name+'-quarantine-cancel-reset-reload', 50+2*t,
                                t+1, t+1, t+1, t+1, t, 1, 1, 1, 4, 1, 1, 1))
    rows.append(CalendarRow('final-quiet16', 22, tail_windows=1))
    return tuple(rows)


def calendar(aw):
    rows = calendar_rows(aw)
    return {name: sum(getattr(row, name) for row in rows)
            for name in CalendarRow.__dataclass_fields__ if name != 'phase'}


def header(aw, field):
    geometry(aw)
    need(type(field) is int and field in (0, 1, 2), 'ANEXT_RESET_FIELD')
    p, g = PRIMES[field], GENERATORS[field]
    n, r = 1 << aw, (1 << 32) % p
    return (0x41313000, n, r*r*pow(n, -1, p) % p, pow(g, (p-1)//(2*n), p))


def source_guard():
    for name, expected in PINS.items():
        need(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected,
             'ANEXT_RESET_PROBE_SOURCE_DRIFT '+name)
    sv, cpp = (ROOT/SV).read_text(), (ROOT/CPP).read_text()
    for token in (
        '.field_rst_n,.field_allow,.ready(actual_ready),.kill',
        '.failed(failed || outer_fault)',
        '.cancel(cancel || failed || outer_fault)',
        '!transfer_error && !transfer.protocol_fault',
        'genefer_track_a4_field_transfer_v2 #(.AW(AW)) transfer',
        'for(genvar f=0;f<3;f=f+1)begin: field_leaf',
        'genefer_track_a4_blockroute_v2 #(.AW(AW),.RW(RW)) route',
        'for(genvar bank=0;bank<128;bank=bank+1)begin: data_bank',
        'genefer_sdp_ram32 #(.AW(RW),.DEPTH(1<<(AW>7 ? AW-7 : 0))) ram',
        '.read_en(ram_re[bank] && field_allow[f])',
        '.write_en(ram_we[bank] && field_allow[f])',
        'genefer_montgomery_mul27_sparse_pipe #(.P(P),.Q(Q)) multiply',
        'genefer_a10_profile3_rom_v1 #(.AW(AW),.P(P)) profile',
        'else if(transfer_error)outer_fault<=1;',
        'consumed_valid<=transfer_valid & field_allow;',
    ):
        need(token in sv, 'ANEXT_RESET_REAL_LEAF_WIRING '+token)
    need(sv.count('.rst_n(field_rst_n[f])') == 4, 'ANEXT_RESET_DIRECT_LEAF_RESETS')
    need('!ready' not in sv and '!actual_ready' not in sv.split('assign caller_valid=')[0],
         'ANEXT_RESET_NO_EXTENDED_TRANSFER_CANCEL')
    need('upper_block_engine' not in sv and 'ntt_sequencer' not in sv, 'ANEXT_RESET_COMPONENT_ONLY')
    need('boost' not in cpp.lower() and 'AW==5 || AW==8' in cpp, 'ANEXT_RESET_BOUNDED_STANDARD_CPP')
    for token in (
        'edge+2', 'edge+5', 'edge+3', 'ordinary_montgomery', 'header(f)[rom_address]',
        'ANEXT_RESET_SOURCE_DERIVED_EDGE_COUNTS', 'edge==571+23*T',
        '#error "ANEXT_RESET_AW must match the compiled RTL AW parameter"',
        'd.read_mask=1;d.write_mask=1u<<8;words(3,1);tick();quiet();advance(6);check();',
        'accepted_reads==13*T+9', 'accepted_writes==10*T+11',
        'observed_read_edges==13*T+5', 'caller_responses==13*T+1',
        'mult_accepted==23 && mult_completed==19 && rom_started==17 && rom_word_edges==53',
        'for(unsigned age:std::array<unsigned,3>{0,1,3})',
        'ANEXT_RESET_MALFORMED_REAL_ERROR', 'ANEXT_RESET_MALFORMED_OUTER_LATCH',
        'ANEXT_RESET_FAULT_NOT_MASKED_BY_CANCEL', 'ANEXT_RESET_PENDING_ROM_WORD3',
        'ANEXT_RESET_QUIET16_PHYSICAL_WRITE_TAIL', 'Bench b(d);b.baseline();baseline_footer();',
        'ANEXT_RESET_NEGATIVE_WRONG_ORACLE', 'ANEXT_RESET_NEGATIVE_NOT_DETECTED',
    ):
        need(token in cpp, 'ANEXT_RESET_INDEPENDENT_CPP_ORACLE '+token)
    return dict(PINS)


def baseline_footer(aw):
    g, c = geometry(aw), calendar(aw)
    return (f'ANEXT_FIELD_RESET_BASELINE aw={aw} fields=3 banks=384 ram_depth={g["depth"]}'
            ' release_edges=2 direct_edge=3 transfer_ram=2 transfer_caller=5 mont=3 rom_words=4'
            ' cancel_ages=0,1,3 quiet_tail=16 reloads=10 tail_windows=12 rom_completed=11'
            f' edges={c["edges"]} read_accepts={c["read_accepts"]} write_accepts={c["write_accepts"]}'
            f' physical_read_edges={c["physical_read_edges"]} physical_write_edges={c["physical_write_edges"]}'
            f' caller_responses={c["caller_responses"]} mult_accepts=23 mult_completed=19 rom_starts=17 rom_word_edges=53'
            f' same_bank_row_pairs={int(aw == 8)}\n')


def role_config(aw):
    """Pure reviewable role, not a package, ticket or native admission receipt."""
    geometry(aw)
    pins = source_guard()
    normal = baseline_footer(aw)
    cases = [dict(name='positive', args=[], expected_exit=0, expected_stderr='',
                  expected_stdout=normal+f'ANEXT_FIELD_RESET_PASS aw={aw} fields=3 scope=real-leaf-component no_clock_claim=1\n')]
    cases += [dict(name=mode.removeprefix('--negative-'), args=[mode], expected_exit=status,
                   expected_stdout=normal, expected_stderr=stderr)
              for mode, (status, stderr) in NEGATIVES.items()]
    return dict(schema='anext-field-reset-real-leaf-component-role-v1', source_only=True,
                build=dict(top=TOP, parameters=dict(AW=aw), sv_sources=list(COMPILED), cpp_source=CPP,
                           cflags=['-std=c++17', f'-DANEXT_RESET_AW={aw}'], threads=1),
                sources=pins, cases=cases, geometry=geometry(aw), calendar=calendar(aw),
                scope='actual transfer + three actual routes + 384 actual SDP32 banks + three sparseMont + three fixed ROMs',
                cancel_contract='cancel/terminalFAILED before accepting posedge, full-clock cancel; no rollback',
                pulse_scope='quiet transfer leaf reset only; pending-transfer subcycle pulse must quarantine',
                profile_scope='four-word ROM and probe collector only; no real engine header/cache or whole-operation proof',
                native_execution=False, clock_claim=False, fanout_claim=False, promotion_allowed=False)


class FieldResetProbeSourceTests(unittest.TestCase):
    def test_pins_actual_leaves_and_cancel_ownership(self):
        self.assertEqual(set(source_guard()), set(COMPILED)|{CPP})
        for aw in (5, 8):
            role = role_config(aw)
            self.assertEqual(role['build']['parameters'], dict(AW=aw))
            self.assertEqual(role['build']['sv_sources'], list(COMPILED))
            self.assertEqual(role['geometry']['depth'], 1 if aw == 5 else 2)
            self.assertEqual(role['geometry']['rw'], 1)
            self.assertFalse(role['native_execution'])

    def test_source_derived_calendar_and_full_reload_counts(self):
        for aw in (5, 8):
            t, c, pair = 1 << (aw-4), calendar(aw), int(aw == 8)
            self.assertEqual(c, dict(edges=571+23*t+pair*(13+t), read_accepts=13*t+9+pair*(t+1), write_accepts=10*t+11+pair,
                                    physical_read_edges=13*t+5+pair*(t+1), physical_write_edges=10*t+11+pair,
                                    caller_responses=13*t+1+pair*(t+1), mult_accepts=23, mult_completed=19,
                                    rom_starts=17, rom_word_edges=53, rom_completed=11, reloads=10, tail_windows=12))
            self.assertEqual(len(calendar_rows(aw)), 15+pair)

    def test_all_three_ordinary_profiles_and_exact_root_order(self):
        for aw in (5, 8):
            for field, p in enumerate(PRIMES):
                words = header(aw, field)
                self.assertEqual(words[:2], (0x41313000, 1 << aw))
                self.assertEqual(pow(words[3], 1 << aw, p), p-1)
                self.assertEqual(pow(words[3], 2 << aw, p), 1)

    def test_exact_case_outputs_after_full_baseline(self):
        for aw in (5, 8):
            cases = role_config(aw)['cases']
            self.assertEqual(len(cases), 4)
            self.assertEqual(cases[0]['expected_exit'], 0)
            self.assertEqual(cases[0]['expected_stderr'], '')
            for case, (mode, (code, stderr)) in zip(cases[1:], NEGATIVES.items()):
                self.assertEqual(case['args'], [mode])
                self.assertEqual(case['expected_exit'], code)
                self.assertEqual(case['expected_stderr'], stderr)
                self.assertEqual(case['expected_stdout'], baseline_footer(aw))

    def test_invalid_geometry_and_source_drift_fail_closed(self):
        for aw in (4, 7, 16, True, '5'):
            with self.assertRaisesRegex(ValueError, 'AW5_AW8_ONLY'):
                geometry(aw)
        for field in (-1, 3, True):
            with self.assertRaisesRegex(ValueError, 'ANEXT_RESET_FIELD'):
                header(5, field)
        with patch.dict(PINS, {SV: '0'*64}):
            with self.assertRaisesRegex(ValueError, 'SOURCE_DRIFT'):
                source_guard()


if __name__ == '__main__':
    unittest.main()
