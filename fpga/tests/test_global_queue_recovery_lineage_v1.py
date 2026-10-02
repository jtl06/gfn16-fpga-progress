"""Pure admission regressions; no queue, transport, HDL or cloud mutation."""
import copy
import json
import unittest
from unittest.mock import patch
from fpga.tools import global_queue_v1 as q


class RecoveryLineageTests(unittest.TestCase):
    def setUp(self):
        self.root=dict(id='original',owner='owner',tool_identity='tool',package=dict(worker_id='native-original'),
            result=dict(status='cancelled_unstarted_dependency_failure'))
        self.middle=dict(id='middle',owner='owner',tool_identity='tool',package=dict(worker_id='native-middle'),
            supersedes_unstarted='original',result=dict(status='terminal_prelaunch_failure_preserved'))
        self.fresh=dict(id='fresh',owner='owner',tool_identity='tool',package=dict(worker_id='native-fresh'),infra_retry_of='middle')
        self.known={'original':self.root,'middle':self.middle}

    def test_preserved_unstarted_ancestor_and_one_prelaunch_attempt_are_allowed(self):
        with patch.object(q,'expected_identity',return_value='same'):
            self.assertEqual(q.recovery_ancestors(self.fresh,self.known),{'original','middle'})
        self.assertNotIn('unrelated',q.recovery_ancestors(dict(id='ordinary'),self.known))

    def test_an_unstarted_chain_never_admits_launched_or_other_owner_history(self):
        with patch.object(q,'expected_identity',return_value='same'):
            self.root['dispatch']=dict(phase='launch_sent')
            with self.assertRaisesRegex(ValueError,'never-claimed'):q.recovery_ancestors(self.fresh,self.known)
            self.root.pop('dispatch');self.root['owner']='different'
            with self.assertRaisesRegex(ValueError,'exact owner'):q.recovery_ancestors(self.fresh,self.known)

    def test_retry_is_once_and_never_for_arithmetic_failure(self):
        with patch.object(q,'expected_identity',return_value='same'):
            self.middle['result']['status']='terminal_contract_failure'
            with self.assertRaisesRegex(ValueError,'proven terminal infrastructure'):q.recovery_ancestors(self.fresh,self.known)
            self.middle['result']['status']='terminal_prelaunch_failure_preserved'
            self.known['other']=dict(id='other',infra_retry_of='middle')
            with self.assertRaisesRegex(ValueError,'one infrastructure successor'):q.recovery_ancestors(self.fresh,self.known)

    def test_actual_wide_provider_age_and_stage_margin(self):
        package=json.loads((q.QUEUE/'done/t5b-wide-threads2-q3-v1.json').read_text())['package']
        captured=q.epoch('2026-10-01T14:57:25.397154Z')
        self.assertTrue(q.wide_provider_freshness(package,captured+840))
        self.assertFalse(q.wide_provider_freshness(package,captured+840.001))
        self.assertFalse(q.wide_provider_freshness(package,captured-1))
        self.assertTrue(q.wide_provider_freshness({'runner':'ordinary'},captured+99999))


if __name__=='__main__':unittest.main()
