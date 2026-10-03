"""Finite software-only R15 recipe; no HDL, device, BOINC, or submission.

Coordinator uses --engine python and only small N32. Azure executor must use
--engine gmp; missing gmpy2 is a failure, not a fallback. Proof-codec native
upstream serialization is a separate fixture gate, not implied by this job.
"""
import argparse
import json
import platform
import time
import unittest

from .r15_arithmetic import HostFault, SoftwareBackend, Checkpoint, genefer_trace, run_verified_window
from .r15_genefer_proof import digits, generate_proof, verify_proof


def run(engine):
    start = time.monotonic()
    modules = ('fpga.tests.test_r15_host_arithmetic', 'fpga.tests.test_r15_host_transport')
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError('R15_HOST_TEST_SUITE_FAILED')
    rows, runtime = [], None
    for base in (10, 599, 600):
        backend = SoftwareBackend(base, 32, enabled=True, engine=engine)
        runtime = backend.runtime
        exponent = base**32
        value, _, valid, _ = genefer_trace(backend, exponent, 7)
        if not valid or value != pow(2, exponent, exponent+1):
            raise RuntimeError('R15_HOST_GMP_GL_ORACLE')
        raw = generate_proof(backend, exponent, 3, enabled=True)
        if not verify_proof(backend, exponent, raw, enabled=True):
            raise RuntimeError('R15_HOST_GMP_PROOF_RELATION')
        bridge_fixture = False
        if engine == 'gmp':
            import gmpy2
            if type(backend.modulus) is not gmpy2.mpz:
                raise RuntimeError('R15_HOST_ACTUAL_GMP_MODULUS')
            # REAL chosen-GMP modular products execute above. Their proof bytes
            # must equal the complete small Python reference, not a fake mpz.
            reference = SoftwareBackend(base, 32, enabled=True, engine='python')
            if raw != generate_proof(reference, exponent, 3, enabled=True):
                raise RuntimeError('R15_HOST_GMP_BRIDGE_BYTES')
            for invalid in (True, 1.0, gmpy2.mpz(1), -1, exponent+1):
                try:
                    digits(invalid, base, 32)
                except HostFault:
                    pass
                else:
                    raise RuntimeError('R15_HOST_STRICT_EXTERNAL_PROOF_RESIDUE')
            bridge_fixture = True
        cp = Checkpoint(base, 32, 1, 0, 0, 7, 'recipe-fixture')
        bits = [True, False, True, True]*4
        good = run_verified_window(backend, bits, 4, cp, enabled=True)
        def corrupt(b, index):
            if index == 3:
                b.load(int((b.read()+1) % b.modulus))
        bad = run_verified_window(backend, bits, 4, cp, enabled=True, inject=corrupt)
        if good is None or bad is not None or backend.read() != cp.value:
            raise RuntimeError('R15_HOST_GMP_ROLLBACK')
        rows.append(dict(base=base, n=32, exponent_bits=exponent.bit_length(),
                         proof_bytes=len(raw), gl=True, proof_relation=True,
                         corrupt_window_rejected=True, rollback_restored=True,
                         actual_gmp_boundary_fixture=bridge_fixture))
    return dict(schema='r15-host-software-normal-v1', status='software_tests_pass',
                tests=result.testsRun, cases=rows, runtime=runtime,
                platform=platform.system(), elapsed_seconds=time.monotonic()-start,
                scope=dict(software_backend=True, board_executed=False, HDL_executed=False,
                           actual_VFIO_operations=False, BOINC_runtime=False,
                           PrimeGrid_submission=False, full_N_or_full_PRP=False,
                           upstream_CPP_format_gate=False, promotion_allowed=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', choices=('python', 'gmp'), required=True)
    args = parser.parse_args()
    print('R15_HOST_RESULT ' + json.dumps(run(args.engine), sort_keys=True))


if __name__ == '__main__':main()
