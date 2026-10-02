from dataclasses import FrozenInstanceError, replace
import unittest

from fpga.reference.stream_ntt_two_context_protocol_v2 import (
    Job, ProtocolBank, abort_isolation_control, stale_completion_control, verify_sources,
)
from fpga.reference.stream_ntt_two_context_model import ContextBank
from fpga.reference.stream_ntt_model import ModelMismatch


class ProtocolV2(unittest.TestCase):
    def test_frozen_prerequisites(self):
        self.assertEqual(len(verify_sources()),3)

    def test_reproduces_frozen_v1_omission(self):
        bank=ContextBank();bank.load(0,[3]*32,173)
        old=bank.start(0);bank.complete(old);new=bank.start(0,1)
        self.assertEqual(old[1],new[1])
        self.assertTrue(bank.complete(old))  # Regression evidence, NOT success.
        self.assertFalse(bank.contexts[0]['busy'])

    def test_stale_same_generation_positive_and_negative(self):
        self.assertTrue(stale_completion_control())
        with self.assertRaisesRegex(ModelMismatch,'S5-stale-completion'):
            stale_completion_control(mutant=True)

    def test_context_abort_positive_and_negative(self):
        self.assertTrue(abort_isolation_control())
        with self.assertRaisesRegex(ModelMismatch,'S5-abort-leakage'):
            abort_isolation_control(mutant=True)

    def test_duplicate_and_all_snapshot_field_tampering(self):
        bank=ProtocolBank();bank.load(0,[7]*32,173);bank.load(1,[9]*32,1009)
        a=bank.start(0);b=bank.start(1,1)
        before=[dict(s) for s in bank.contexts]
        mutants=[replace(a,context=1),replace(a,generation=a.generation+1),
                 replace(a,job_id=b.job_id),replace(a,base=1009),
                 replace(a,value=a.value+1),replace(a,double=1)]
        for bad in mutants:
            self.assertFalse(bank.complete(bad));self.assertEqual(bank.contexts,before)
        self.assertTrue(bank.complete(a));done=dict(bank.contexts[0])
        self.assertFalse(bank.complete(a));self.assertEqual(bank.contexts[0],done)
        self.assertTrue(bank.complete(b))

    def test_immutable_job(self):
        bank=ProtocolBank();bank.load(0,[1]*32,173);job=bank.start(0)
        with self.assertRaises(FrozenInstanceError):job.double=1
        with self.assertRaises(TypeError):bank.complete(tuple(job.__dict__.values()))

    def test_ids_never_reused_across_abort_error_reset_load(self):
        bank=ProtocolBank();jobs=[]
        for operation in ('abort','error','reset_context','reset_all'):
            bank.load(0,[2]*32,173);old=bank.start(0);jobs.append(old)
            if operation=='reset_all':bank.reset_all()
            else:getattr(bank,operation)(0)
            bank.load(0,[4]*32,173);new=bank.start(0);jobs.append(new)
            before=dict(bank.contexts[0]);self.assertFalse(bank.complete(old))
            self.assertEqual(bank.contexts[0],before);self.assertTrue(bank.complete(new))
        self.assertEqual([j.job_id for j in jobs],list(range(len(jobs))))

    def test_independent_bases_double_chains_and_old_replays(self):
        bank=ProtocolBank();bases=(173,1009);expected=[];history=[[],[]]
        for ctx,base in enumerate(bases):
            digits=[ctx+3]*32;bank.load(ctx,digits,base)
            expected.append(sum(d*base**i for i,d in enumerate(digits)))
        for epoch in range(24):
            jobs=[bank.start(ctx,(epoch+ctx)&1) for ctx in (0,1)]
            before=[dict(s) for s in bank.contexts]
            for ctx in (0,1):
                for stale in history[ctx]:self.assertFalse(bank.complete(stale))
            self.assertEqual(bank.contexts,before)
            for ctx in ((1,0) if epoch&1 else (0,1)):
                expected[ctx]=expected[ctx]**2*(1<<((epoch+ctx)&1))%(bases[ctx]**32+1)
                self.assertTrue(bank.complete(jobs[ctx]));self.assertEqual(bank.read(ctx),expected[ctx])
                history[ctx].append(jobs[ctx])

    def test_partial_load_base_change_busy_reject_other_unchanged(self):
        bank=ProtocolBank();bank.load(0,[8]*32,173);bank.load(1,[5]*32,1009)
        b=bank.start(1,1);snapshot=dict(bank.contexts[1])
        with self.assertRaisesRegex(ModelMismatch,'S5-host-busy'):bank.load_digit(1,0,7)
        bank.load_digit(0,2,10);bank.change_base(0,1009)
        self.assertEqual(bank.contexts[1],snapshot);self.assertTrue(bank.complete(b))
        self.assertEqual(bank.canonical_digits(0),[8,8,10]+[8]*29)
        bank.load(0,[999]*32,1009)
        with self.assertRaisesRegex(ModelMismatch,'S5-base-reload'):bank.change_base(0,173)
        self.assertFalse(bank.contexts[0]['valid']);self.assertTrue(bank.contexts[1]['valid'])

    def test_context_validation(self):
        bank=ProtocolBank()
        for ctx in (-1,2,True,None):
            with self.assertRaises(ValueError):bank.abort(ctx)
            with self.assertRaises(ValueError):bank.load(ctx,[0]*32,173)


if __name__=='__main__':unittest.main()
