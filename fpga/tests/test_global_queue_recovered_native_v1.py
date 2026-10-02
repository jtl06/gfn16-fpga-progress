"""Retained original contracts can close GC'd units without invented exits."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import global_queue_v1 as q


class RecoveredNativeTests(unittest.TestCase):
    def setUp(self):
        self.identifier = 's4-aw8-stale-eligibility-q1-v1'
        path = next(p for p in (q.QUEUE/'running'/f'{self.identifier}.json', q.QUEUE/'done'/f'{self.identifier}.json') if p.exists())
        self.ticket = json.loads(path.read_text())
        self.ticket.pop('result',None);self.ticket.pop('dependency_gate',None)
        self.root = q.FPGA/'results/throughput-20260929/azure-sim-idle-recognition-v5'
        self.native = self.root/'interrupted-s4-native-v1/report.json'
        self.wrapper = self.root/'interrupted-s4-queue-report-v1.json'
        self.journal = self.root/'boot-guard-marker-chronology-v2.log'

    def invoke(self, directory, live=False):
        (directory/'done').mkdir(exist_ok=True)
        q.atomic(directory/'running'/f'{self.identifier}.json',copy.deepcopy(self.ticket))
        with patch.object(q,'QUEUE',directory), patch.object(q,'load_host',return_value=dict(name='gfn16-azure-sim-f32',lanes=[dict(id=self.ticket['dispatch']['lane'],cpus=[2,3])])), \
             patch.object(q,'ssh',return_value={}), patch.object(q,'output',return_value=('LoadState=loaded\nMainPID=99\nInvocationID=other\n' if live else 'LoadState=not-found\nMainPID=0\nInvocationID=\n')), \
             patch.object(q,'probe',return_value=dict(free_lanes=[self.ticket['dispatch']['lane']])):
            return q.recover_completed_native(self.identifier,self.native,q.sha(self.native),self.wrapper,q.sha(self.wrapper),self.journal,q.sha(self.journal))

    def test_original_typed_negative_actual_source_artifacts_and_journal_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);q.atomic(directory/'hosts/host.json',dict(name='gfn16-azure-sim-f32'))
            result=self.invoke(directory)
            self.assertEqual(result['gate']['status'],'PASS_expected_contracts')
            self.assertEqual(result['original_invocation'],'cf4aa4cf484c46f485b18eba772bee57')
            self.assertEqual(result['actual_journal_terminal'],'2026-10-01T09:58:03Z')
            self.assertFalse(result['unit_replayed'])
            final=json.loads((directory/'done'/f'{self.identifier}.json').read_text())
            self.assertNotIn('properties',final['result'])
            self.assertTrue(final['result']['terminal_properties_unavailable_after_gc'])
            self.assertFalse((directory/'running'/f'{self.identifier}.json').exists())

    def test_live_or_different_invocation_retains_original_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);q.atomic(directory/'hosts/host.json',dict(name='gfn16-azure-sim-f32'))
            with self.assertRaisesRegex(ValueError,'unit gone'):
                self.invoke(directory,live=True)
            self.assertTrue((directory/'running'/f'{self.identifier}.json').exists())


if __name__=='__main__':unittest.main()
