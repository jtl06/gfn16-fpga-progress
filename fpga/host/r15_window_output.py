"""Strict finite software-window output; rejects real-core/performance claims."""
import json
import math


def validate(stdout, *, require_gmp=True):
    rows = [row for row in stdout.splitlines() if row.startswith('R15_WINDOW_RESULT ')]
    if len(rows) != 1:
        raise ValueError('R15_WINDOW_EXACT_ONE_RESULT')
    value = json.loads(rows[0][len('R15_WINDOW_RESULT '):])
    if set(value) != {'schema', 'status', 'tests', 'cases', 'runtime', 'platform', 'controls',
                      'sample_plan', 'elapsed_seconds', 'scope'} or (
            value['schema'] != 'r15-software-canonical-window-normal-v1' or
            value['status'] != 'software_windows_pass' or value['tests'] != 23 or
            type(value['tests']) is not int):
        raise ValueError('R15_WINDOW_SCHEMA_TESTS')
    scope = dict(software_GMP_windows=require_gmp, software_endpoint_model=True,
        actual_core=False, actual_transport=False, arbitrary_in_job_checkpoints=False,
        full_N_numeric=False, measured_full_PRP=False, board=False,
        inherited_compute_timing=False, promotion=False)
    if value['scope'] != scope or any(type(item) is not bool for item in value['scope'].values()):
        raise ValueError('R15_WINDOW_SCOPE')
    if type(value['cases']) is not list or len(value['cases']) != 2:
        raise ValueError('R15_WINDOW_TWO_CASES')
    for case, base in zip(value['cases'], (599, 600), strict=True):
        operations = (base**256).bit_length()
        jobs, tail = divmod(operations, 64)
        total_jobs = jobs + bool(tail)
        checks = (jobs+3)//4 + bool(tail)
        wanted = dict(base=base, n=256, global_operations=operations, jobs=total_jobs,
            raw_cold_words=total_jobs*288, canonical_words=total_jobs*256,
            host_GL_checks=checks, independent_pow_equal=True,
            global_ordinal_equal=True, no_padded_descriptors=True)
        if case != wanted or any(type(case[key]) is not type(item) for key, item in wanted.items()):
            raise ValueError('R15_WINDOW_CASE')
    plan = dict(operations=1911814, width=65536, jobs=30, last=11270,
                generations_below_256=True, integer_only=True)
    if value['sample_plan'] != plan or any(type(value['sample_plan'][key]) is not type(item)
                                         for key, item in plan.items()):
        raise ValueError('R15_WINDOW_INTEGER_PLAN')
    controls = dict(chosen_engine_corrupt_A_GL_rejected=True,
                    two_rollback_checkpoints_preserved=True,
                    common_reset_drain_fullreload_required=True,
                    global_ordinals_rewound=True)
    if value['controls'] != controls or any(item is not True for item in value['controls'].values()):
        raise ValueError('R15_WINDOW_CONTROLS')
    elapsed = value['elapsed_seconds']
    if type(elapsed) not in (float, int) or not math.isfinite(elapsed) or not 0 <= elapsed < 105:
        raise ValueError('R15_WINDOW_BOUND')
    runtime = value['runtime']
    if require_gmp and (value['platform'] != 'Linux' or set(runtime) != {'engine', 'version', 'gmp'} or
            runtime['engine'] != 'gmpy2' or not all(type(runtime[key]) is str and runtime[key]
                                                for key in ('version', 'gmp'))):
        raise ValueError('R15_WINDOW_ACTUAL_GMP')
    return value
