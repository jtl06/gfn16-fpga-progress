from dataclasses import replace
import unittest

from fpga.host.r15_arithmetic import HostFault, SoftwareBackend
from fpga.host.r15_canonical_job_session import CanonicalJobSession
from fpga.host.r15_genefer_proof import digits
from fpga.host.r15_image_codec import (Publication, CanonicalCollector, ExportWord,
    CANONICAL_A, encode_signed96)
from fpga.host.r15_link_adapter import CoreSnapshot


class ChunkSession(unittest.TestCase):
    def session(self, **kwargs):
        return CanonicalJobSession(256, 600, source='small-model-fixture',
            transport_session=7, width=kwargs.pop('width', 64),
            verify_every=kwargs.pop('verify_every', 4), enabled=True, **kwargs)

    def plan(self, s, context, bits, *, epoch=65534):
        snapshot = CoreSnapshot(s.session, context, epoch,
                                s.generation[context] + 1, True)
        return s.plan(context, snapshot, tuple(bits))

    def export(self, s, plan, *, corrupt=False):
        # Independent endpoint test double executes the actual descriptor list
        # from the canonical cold value; no expected pow value is supplied.
        b = SoftwareBackend(s.base, s.n, enabled=True)
        value = s.current_value[plan.context]
        b.load(value)
        for bit in plan.bits:
            b.step(bit)
        value = (b.read() + int(corrupt)) % b.modulus
        h = plan.transaction.header
        collector = CanonicalCollector(Publication(s.n, s.base, plan.context, h.owner,
                                                    h.count, True), enabled=True)
        for index, value in enumerate(digits(value, s.base, s.n)):
            collector.accept(ExportWord(CANONICAL_A, plan.context, h.owner, index,
                                        encode_signed96(value)))
        return collector.finish()

    def run_job(self, s, plan, *, corrupt=False):
        s.acknowledge_cold(plan, lease=9, accepted=s.n+32, applied=s.n+32,
                           coherent_idle_ack=True, retained_profile_ready=True)
        return s.accept_canonical(plan, self.export(s, plan, corrupt=corrupt),
                                  response_session=s.session)

    def test_full_small_PRP_split_equals_independent_pow_no_padding(self):
        for base in (599, 600):
            s = CanonicalJobSession(256, base, source='small-model-fixture',
                transport_session=7, width=64, verify_every=4, enabled=True)
            exponent = base**256
            bits = tuple(c == '1' for c in bin(exponent)[2:])
            for start in range(0, len(bits), s.width):
                block = bits[start:start+s.width]
                if len(block) != s.width:
                    self.assertTrue(s.flush(0))
                self.run_job(s, self.plan(s, 0, block))
            self.assertTrue(s.flush(0))
            cp = s.checkpoint(0)
            self.assertEqual((cp.ordinal, cp.value),
                             (len(bits), pow(2, exponent, exponent + 1)))
            self.assertEqual(s.accounting['descriptors'], len(bits))
            self.assertEqual(s.accounting['raw_cold_words'], s.accounting['jobs']*288)
            self.assertEqual(s.accounting['canonical_words'], s.accounting['jobs']*256)
            self.assertFalse(s.accounting['native_GL_coupling'])
            self.assertIsNone(s.accounting['transport_seconds'])

    def test_two_context_rollback_checkpoints_and_reset_drain_reload(self):
        s = self.session(width=4, verify_every=2, initial_values=(1, 7))
        bits = (True, False, True, True)
        for context in (0, 1):
            self.run_job(s, self.plan(s, context, bits))
            self.assertTrue(self.run_job(s, self.plan(s, context, bits)))
        safe = tuple(s.verified)
        self.run_job(s, self.plan(s, 1, bits))  # peer provisional state is not checkpointed
        self.run_job(s, self.plan(s, 0, bits))
        self.assertFalse(self.run_job(s, self.plan(s, 0, bits), corrupt=True))
        self.assertEqual(tuple(s.verified), safe)
        with self.assertRaisesRegex(HostFault, 'RESET'):
            self.plan(s, 0, bits)
        with self.assertRaises(HostFault):
            s.acknowledge_common_reset(8, core_reset_ack=True, both_domains_drained=False)
        s.acknowledge_common_reset(8, core_reset_ack=True, both_domains_drained=True)
        self.assertEqual((s.ordinal, s.current_value),
                         ([cp.ordinal for cp in safe], [cp.value for cp in safe]))
        self.assertEqual(s.reload_required, {0, 1})
        p = self.plan(s, 1, bits)
        self.assertEqual(p.cold_digits, tuple(digits(safe[1].value, 600, 256)))
        self.assertEqual(p.raw_cold_words[-32:], (0,)*32)

    def test_owner_global_ordinal_and_session_are_distinct(self):
        s = self.session(width=4, verify_every=1)
        p = self.plan(s, 0, (False,)*4)
        image = self.export(s, p)
        with self.assertRaisesRegex(HostFault, 'ACK'):
            s.accept_canonical(p, image, response_session=7)
        with self.assertRaisesRegex(HostFault, 'PROFILE'):
            s.acknowledge_cold(p, lease=9, accepted=288, applied=288, coherent_idle_ack=True,
                               retained_profile_ready=False)
        s.acknowledge_cold(p, lease=9, accepted=288, applied=288, coherent_idle_ack=True,
                           retained_profile_ready=True)
        wrong = replace(image, publication=replace(image.publication, owner=image.publication.owner ^ (1 << 40)))
        with self.assertRaisesRegex(HostFault, 'OWNER'):
            s.accept_canonical(p, wrong, response_session=7)
        self.assertTrue(s.recovery_required)
        s.acknowledge_common_reset(8, core_reset_ack=True, both_domains_drained=True)
        p = self.plan(s, 0, (False,)*4)
        image = self.export(s, p)
        s.acknowledge_cold(p, lease=9, accepted=288, applied=288, coherent_idle_ack=True,
                           retained_profile_ready=True)
        self.assertTrue(s.accept_canonical(p, image, response_session=8))
        self.assertEqual(s.checkpoint(0).ordinal, 4)
        self.assertEqual(s.checkpoint(0).last_job_owner >> 24, 3)
        with self.assertRaisesRegex(HostFault, 'UNEXPORTED'):
            s.proof_checkpoint(0, 2)

    def test_generation_refusal_not_wrap_or_old_response_reuse(self):
        s = self.session(width=1, verify_every=1)
        for _ in range(255):
            self.assertTrue(self.run_job(s, self.plan(s, 0, (False,))))
        with self.assertRaisesRegex(ValueError, 'EXHAUSTED'):
            self.plan(s, 0, (False,))
        cp = s.checkpoint(0)
        s.acknowledge_common_reset(8, core_reset_ack=True, both_domains_drained=True)
        p = self.plan(s, 0, (False,))
        self.assertEqual(p.global_begin, cp.ordinal)
        self.assertEqual(p.transaction.header.generation, 1)
        image = self.export(s, p)
        s.acknowledge_cold(p, lease=9, accepted=288, applied=288, coherent_idle_ack=True,
                           retained_profile_ready=True)
        with self.assertRaisesRegex(HostFault, 'SESSION'):
            s.accept_canonical(p, image, response_session=7)

    def test_default_off_partial_load_and_width_barrier(self):
        with self.assertRaisesRegex(HostFault, 'OFF'):
            CanonicalJobSession(256, 600, source='x', transport_session=1, width=4, verify_every=2)
        s = self.session(width=4, verify_every=2)
        p = self.plan(s, 0, (False,)*4)
        with self.assertRaisesRegex(HostFault, 'ACK'):
            s.acknowledge_cold(p, lease=9, accepted=288, applied=287, coherent_idle_ack=True,
                               retained_profile_ready=True)
        self.run_job(s, p)
        with self.assertRaisesRegex(HostFault, 'WIDTH'):
            self.plan(s, 0, (True,))
        self.assertTrue(s.flush(0))
        self.assertIsNone(self.run_job(s, self.plan(s, 0, (True,))))
        self.assertTrue(s.flush(0))

    def test_exact_special_A_reloads_raw_minus_one_without_finalizing_again(self):
        s = self.session(width=1, verify_every=1, initial_values=(600**128, 1))
        p = self.plan(s, 0, (False,))
        image = self.export(s, p)
        self.assertTrue(image.special)
        self.assertEqual(image.digits, (-1,) + (0,)*255)
        s.acknowledge_cold(p, lease=9, accepted=288, applied=288, coherent_idle_ack=True,
                           retained_profile_ready=True)
        self.assertTrue(s.accept_canonical(p, image, response_session=7))
        p = self.plan(s, 0, (False,))
        self.assertEqual(p.raw_cold_words, (0xffffffff,) + (0,)*287)
        self.assertTrue(self.run_job(s, p))
        self.assertEqual(s.checkpoint(0).value, 1)


if __name__ == '__main__':
    unittest.main()
