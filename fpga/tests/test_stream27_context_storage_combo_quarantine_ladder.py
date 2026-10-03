"""Source-only R3 ladder checks; no local HDL or full-N numeric execution."""
import json
from pathlib import Path
import unittest
from fpga.reference import stream27_context_storage_combo_quarantine_long_native as pilot
from fpga.reference import stream27_context_storage_combo_quarantine_continuous as long
from fpga.reference import stream27_context_storage_combo_quarantine_fault as fault


def test_frozen_full_role_and_calendar():
    manifest, files = pilot.role(100, 1)
    assert len(manifest['build']['sv_sources']) == 56
    assert manifest['build']['parameters']['QUARANTINE_REPLICAS'] == 1
    proof = manifest['context_storage_combo_quarantine']['own_long']['own_calendar']
    assert proof['frames'] == 200 and proof['lease_peak'] <= 4
    assert proof['launch_gaps'] == [4229, 4230]
    assert manifest['rtl_readiness']['rtl_ready_at_utc'] == pilot.READY
    assert b'COUNT=100,INTERVAL=8459' in files[pilot.HEADER]


def test_own_header_only_long_delta():
    manifest, files = pilot.role(100, 1)
    new = long.header(files[pilot.HEADER])
    assert b'COUNT=1000,INTERVAL=8459' in new
    assert long.bits(1000)[0][:100] == pilot.bits(100)[0]
    assert long.bits(1000)[1][:100] == pilot.bits(100)[1]
    assert long.config() == pilot.config(1000, 1)


def test_early_cache_keeps_shared_term_dependency():
    manifest, files = fault.role('early-cache')
    source = manifest['build']['sv_sources']
    term = 'rtl/genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1_payload_lookahead_v1'
    assert term + '.sv' in source and term + '_earlycache_probe.sv' in source
    assert len(source) == 56
    assert 'C2_STORAGE_EARLY_CACHE_ACTUAL_PREMATURE_TOKEN' in files[fault.CPP].decode()


def test_actual_origin_quarantine_assertion_retained():
    manifest, files = pilot.role(100, 1)
    roots = [n for n in manifest['build']['sv_sources'] if 'shared_warm_aw16' in n
             and n.endswith('_storage_combo_quarantine_v1.sv')]
    assert len(roots) == 3
    for name in roots:
        text = files[name].decode()
        assert 'transform_quarantine!={2{controller_error}}' in text
        assert 'fault_set(!stop && (admission_bad || join_bad' in text


def test_forecast_is_source_thread_bound_not_actual_long():
    forecast = long.predict(100, 200)
    assert forecast['continuous_command_seconds_estimate'] == 1750
    assert forecast['overall_seconds_estimate'] == 2525
    assert long.PILOT_ID == 's4-p16-c2-combo-r3-own100-serial-q1-v1'
    assert long.THREADS == 1


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(function)
        for name, function in sorted(globals().items()) if name.startswith('test_'))


if __name__ == '__main__':
    unittest.main()
