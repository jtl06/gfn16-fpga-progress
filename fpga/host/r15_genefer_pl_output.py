"""Strict small upstream-method interoperability output, never a core gate."""
import json
import re

COMMIT = 'd5060c61090942f42a908492628eba13ebd7cd82'


def validate(stdout):
    rows = [line for line in stdout.splitlines() if line.startswith('R15_PL_RESULT ')]
    if len(rows) != 1:
        raise ValueError('R15_PL_OUTPUT_ONE_RESULT')
    value = json.loads(rows[0][len('R15_PL_RESULT '):])
    wanted = dict(schema='r15-pinned-genefer-pl-gl-oracle-v1', status='software_interop_equal',
        upstream_commit=COMMIT, upstream_PL_GL_methods_executed=True,
        synthetic_GMP_transform=True, real_genefer_transform=False,
        full_N_PRP=False, board=False, BOINC_server=False, promotion=False)
    if set(value) != set(wanted) | {'rows', 'build_stderr'} or any(
            value[key] != item or type(value[key]) is not type(item)
            for key, item in wanted.items()):
        raise ValueError('R15_PL_OUTPUT_SCOPE')
    if type(value['build_stderr']) is not str or len(value['build_stderr']) > 65536:
        raise ValueError('R15_PL_OUTPUT_DIAGNOSTICS_BOUND')
    if type(value['rows']) is not list or len(value['rows']) != 3:
        raise ValueError('R15_PL_OUTPUT_CASES')
    for case, base in zip(value['rows'], (10, 599, 600), strict=True):
        if set(case) != {'base', 'n', 'depth', 'bytes', 'proof_sha256', 'pkey',
                         'upstream_GL_bad_result_rejected'} or any(
                type(case[key]) is not int or case[key] != item for key, item in
                dict(base=base, n=32, depth=3, bytes=556).items()) or (
                case['upstream_GL_bad_result_rejected'] is not True or
                type(case['pkey']) is not int or not 0 <= case['pkey'] < 1 << 64 or
                type(case['proof_sha256']) is not str or
                re.fullmatch('[0-9a-f]{64}', case['proof_sha256']) is None):
            raise ValueError('R15_PL_OUTPUT_EXACT_CASE')
    return value
