"""Strict typed software recipe output; never grants board/promotion scope."""
import json
import math


def validate(stdout, *, require_gmp=True):
    lines = [line for line in stdout.splitlines() if line.startswith('R15_HOST_RESULT ')]
    if len(lines) != 1:
        raise ValueError('R15_HOST_OUTPUT_EXACT_ONE_RESULT')
    value = json.loads(lines[0][len('R15_HOST_RESULT '):])
    if set(value) != {'schema', 'status', 'tests', 'cases', 'runtime', 'platform',
                      'elapsed_seconds', 'scope'}:
        raise ValueError('R15_HOST_OUTPUT_KEYS')
    if (value['schema'] != 'r15-host-software-normal-v1' or value['status'] != 'software_tests_pass' or
            type(value['tests']) is not int or value['tests'] != 14):
        raise ValueError('R15_HOST_OUTPUT_TESTS')
    expected_scope = dict(software_backend=True, board_executed=False, HDL_executed=False,
                          actual_VFIO_operations=False, BOINC_runtime=False,
                          PrimeGrid_submission=False, full_N_or_full_PRP=False,
                          upstream_CPP_format_gate=False, promotion_allowed=False)
    if value['scope'] != expected_scope or any(type(x) is not bool for x in value['scope'].values()):
        raise ValueError('R15_HOST_OUTPUT_SCOPE')
    for case, base in zip(value['cases'], (10, 599, 600), strict=True):
        wanted = dict(base=base, n=32, exponent_bits=(base**32).bit_length(), proof_bytes=556,
                      gl=True, proof_relation=True, corrupt_window_rejected=True,
                      rollback_restored=True,
                      actual_gmp_boundary_fixture=value['runtime'].get('engine') == 'gmpy2')
        if case != wanted or any(type(case[key]) is not bool for key in
                ('gl', 'proof_relation', 'corrupt_window_rejected', 'rollback_restored',
                 'actual_gmp_boundary_fixture')):
            raise ValueError('R15_HOST_OUTPUT_CASE')
    elapsed = value['elapsed_seconds']
    if type(elapsed) not in (float, int) or not math.isfinite(elapsed) or not 0 <= elapsed < 105:
        raise ValueError('R15_HOST_OUTPUT_FINITE_TIME')
    runtime = value['runtime']
    if require_gmp and (value['platform'] != 'Linux' or set(runtime) != {'engine', 'version', 'gmp'} or
                        runtime['engine'] != 'gmpy2' or not all(type(runtime[k]) is str and runtime[k]
                            for k in ('version', 'gmp'))):
        raise ValueError('R15_HOST_OUTPUT_ACTUAL_GMP')
    return value
