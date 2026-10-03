"""Finite GMP/software endpoint contract; no real core/PCIe/board execution."""
import argparse
import json
import platform
import time
import unittest

from .r15_arithmetic import SoftwareBackend, need
from .r15_canonical_job_session import CanonicalJobSession, window_counts
from .r15_genefer_proof import digits
from .r15_image_codec import (Publication, CanonicalCollector, ExportWord,
                              CANONICAL_A, encode_signed96)
from .r15_link_adapter import CoreSnapshot


def one_job(model, context, bits, engine, *, epoch=65534, corrupt=False):
    plan = model.plan(context, CoreSnapshot(model.session, context, epoch,
        model.generation[context]+1, True), tuple(bits))
    model.acknowledge_cold(plan, lease=9, accepted=288, applied=288,
                          coherent_idle_ack=True, retained_profile_ready=True)
    endpoint = SoftwareBackend(model.base, 256, enabled=True, engine=engine)
    endpoint.load(model.current_value[context])
    for bit in bits:
        endpoint.step(bit)
    value = (endpoint.read()+int(corrupt)) % endpoint.modulus
    header = plan.transaction.header
    collector = CanonicalCollector(Publication(256, model.base, context, header.owner,
                                                header.count, True), enabled=True)
    for index, value in enumerate(digits(int(value), model.base, 256)):
        collector.accept(ExportWord(CANONICAL_A, context, header.owner, index,
                                    encode_signed96(value)))
    return model.accept_canonical(plan, collector.finish(), response_session=model.session)


def run(engine):
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromNames((
        'fpga.tests.test_r15_canonical_job_session', 'fpga.tests.test_r15_image_codec',
        'fpga.tests.test_r15_checkpoint_store', 'fpga.tests.test_r15_link_adapter'))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    need(result.wasSuccessful(), 'WINDOW_SOURCE_TESTS')
    rows = []
    runtime = None
    for base in (599, 600):
        model = CanonicalJobSession(256, base, source='software-endpoint-fixture',
            transport_session=7, width=64, verify_every=4, enabled=True, engine=engine)
        runtime = model.checker.runtime
        exponent = base**256
        bits = tuple(bit == '1' for bit in bin(exponent)[2:])
        # Endpoint test double uses GMP independently of the host window
        # verifier. It emulates arithmetic, NOT RTL scheduling or transport.
        core_epoch = 65534
        for start in range(0, len(bits), 64):
            block = bits[start:start+64]
            if len(block) != 64:
                need(model.flush(0), 'WINDOW_FLUSH_BEFORE_SHORT_LAST_JOB')
            outcome = one_job(model, 0, block, engine, epoch=core_epoch)
            need(outcome is not False, 'WINDOW_GMP_PRODUCT_RELATION')
            core_epoch = (core_epoch + len(block)) & 65535
        need(model.flush(0), 'WINDOW_FINAL_VERIFICATION')
        checkpoint = model.checkpoint(0)
        need(checkpoint.value == pow(2, exponent, exponent+1) and
             checkpoint.ordinal == len(bits), 'WINDOW_INDEPENDENT_FULL_SMALL_POW')
        rows.append(dict(base=base, n=256, global_operations=len(bits),
            jobs=model.accounting['jobs'], raw_cold_words=model.accounting['raw_cold_words'],
            canonical_words=model.accounting['canonical_words'],
            host_GL_checks=model.accounting['host_GL_checks'],
            independent_pow_equal=True, global_ordinal_equal=True,
            no_padded_descriptors=True))
    # Actual chosen-engine corruption/rollback relation, separate from the
    # Python unit-control fixtures. There is still no physical core endpoint.
    rollback = CanonicalJobSession(256, 600, source='software-endpoint-fixture',
        transport_session=7, width=4, verify_every=2, initial_values=(1, 7),
        enabled=True, engine=engine)
    block = (True, False, True, True)
    for context in (0, 1):
        one_job(rollback, context, block, engine)
        need(one_job(rollback, context, block, engine) is True, 'WINDOW_GOOD_PEER_CP')
    checkpoints = tuple(rollback.verified)
    one_job(rollback, 1, block, engine)
    one_job(rollback, 0, block, engine)
    need(one_job(rollback, 0, block, engine, corrupt=True) is False and
         tuple(rollback.verified) == checkpoints and rollback.recovery_required,
         'WINDOW_CORRUPTION_AND_TWO_INDEPENDENT_CP')
    rollback.acknowledge_common_reset(8, core_reset_ack=True, both_domains_drained=True)
    need(rollback.reload_required == {0, 1} and
         rollback.current_value == [cp.value for cp in checkpoints] and
         rollback.ordinal == [cp.ordinal for cp in checkpoints], 'WINDOW_RESET_REWIND')
    sample = window_counts(1911814)
    return dict(schema='r15-software-canonical-window-normal-v1', status='software_windows_pass',
        tests=result.testsRun, cases=rows, runtime=runtime, platform=platform.system(),
        controls=dict(chosen_engine_corrupt_A_GL_rejected=True,
                      two_rollback_checkpoints_preserved=True,
                      common_reset_drain_fullreload_required=True,
                      global_ordinals_rewound=True),
        sample_plan=dict(operations=1911814, width=65536, jobs=len(sample), last=sample[-1],
                         generations_below_256=True, integer_only=True),
        elapsed_seconds=time.monotonic()-started,
        scope=dict(software_GMP_windows=engine=='gmp', software_endpoint_model=True,
            actual_core=False, actual_transport=False, arbitrary_in_job_checkpoints=False,
            full_N_numeric=False, measured_full_PRP=False, board=False,
            inherited_compute_timing=False, promotion=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', choices=('python', 'gmp'), required=True)
    args = parser.parse_args()
    print('R15_WINDOW_RESULT ' + json.dumps(run(args.engine), sort_keys=True))
