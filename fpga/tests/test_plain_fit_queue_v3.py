"""Narrow launch-observation type/restart regression. No native/remote calls."""
from copy import deepcopy
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plain_queue_v3',FPGA/'tools/plain_fit_queue_v3.py')
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
NOW = datetime(2026,10,1,11,tzinfo=timezone.utc)
HOST = 'gfn16-azure-f16'; INV = 'a'*32


class Backend:
    def __init__(self,first): self.first=first; self.calls=[]; self.actual=None
    def preflight(self,host,slot): self.calls.append(('preflight',host,slot)); return {}
    def stage(self,handle,archive): self.calls.append(('stage',handle['id']))
    def launch(self,handle,helpers):
        self.calls.append(('launch',handle['id']))
        return dict(invocation_id=self.first,request_sha256=handle['request_sha256'],state=dict(MainPID='42',ActiveState='active'))
    def observe(self,handle):
        self.calls.append(('observe',handle['id']))
        return dict(invocation_id=self.actual,request_sha256=handle['request_sha256'],state=dict(MainPID='42',ActiveState='active'))
    def collect(self,handle): self.calls.append(('collect',handle['id'])); raise AssertionError('active/unknown lease must not collect')


def prepare(job,host,slot,directory,topology,now):
    directory.mkdir(); request=directory/'request.json'
    q.save(request,dict(schema='pure fixture'))
    reference=dict(path=str(request),sha256=q.digest(request.read_bytes()))
    return dict(id=job['id'],host=host,slot=slot,unit=job['unit'],project_name=job['project_name'],scope=job['scope'],
        request=reference,request_sha256=reference['sha256'],remote_request='/home/azureuser/gfn16-worker/tools/request.json'),{},request


class InvocationTests(unittest.TestCase):
    def queue(self):
        return dict(schema='plain-fit-queue-v1',until_utc='2026-10-02T04:00:00Z',adopt=[],jobs=[dict(
            id='seed4',priority=1,project_name='seed4-project',unit='gfn16-seed4.service',scope='whole_core',
            allowed_slots={HOST:['b']},variants={HOST:{}},after=[],requires=[])])

    def controller(self,value,root,backend):
        # Source admission is outside this narrow regression; all state/launch
        # transitions and actual v3 tick implementation run unchanged.
        with patch.object(q,'validate_queue',return_value=q.END):
            return q.Controller(value,root,backend,prepare)

    def test_exact_typed_validation_only_frozen_v2_untouched(self):
        original=(FPGA/'tools/plain_fit_queue_v2.py').read_text()
        successor=(FPGA/'tools/plain_fit_queue_v3.py').read_text()
        old="                        need(re.fullmatch('[0-9a-f]{32}',observation.get('invocation_id','')) and observation['request_sha256']==handle['request_sha256'],'exact native launch handle')"
        new="                        inv=observation.get('invocation_id')\n                        need(type(inv) is str and re.fullmatch('[0-9a-f]{32}',inv) and observation['request_sha256']==handle['request_sha256'],'exact native launch handle')"
        self.assertEqual(q.digest(original.encode()),'ae6c7191574e46841c4d63e3e5f632c4e6a48b73495dd8dcfedcb7027dde1a31')
        self.assertEqual(original.count(old),1)
        self.assertEqual(successor,original.replace(old,new))

    def test_none_first_observation_retains_intent_and_restart_never_relaunches(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); value=self.queue(); backend=Backend(None)
            controller=self.controller(value,root,backend); current=controller.tick(NOW)
            self.assertEqual(current['seed4']['phase'],'launch_attempt')
            self.assertNotIn('invocation_id',current['seed4'])
            self.assertEqual([row['event'] for row in controller.journal.rows],['intent','launch_attempt','blocked'])
            self.assertIn('exact native launch handle',controller.journal.rows[-1]['reason'])
            current=self.controller(value,root,backend).tick(NOW)
            self.assertEqual(current['seed4']['phase'],'launch_attempt')
            self.assertEqual(sum(call[0]=='launch' for call in backend.calls),1)
            self.assertEqual(sum(call[0]=='stage' for call in backend.calls),1)
            self.assertFalse(any(call[0]=='collect' for call in backend.calls))

    def test_malformed_first_observations_are_valueerror_not_typeerror(self):
        for first in (False,0,123,{},[],['a'*32],'','short','A'*32,'a'*31,'a'*33):
            with self.subTest(first=first),tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve(); backend=Backend(first); value=self.queue()
                current=self.controller(value,root,backend).tick(NOW)
                self.assertEqual(current['seed4']['phase'],'launch_attempt')
                self.assertEqual(sum(call[0]=='launch' for call in backend.calls),1)
                self.assertEqual(self.controller(value,root,backend).tick(NOW)['seed4']['phase'],'launch_attempt')
                self.assertEqual(sum(call[0]=='launch' for call in backend.calls),1)

    def test_later_actual_original_invocation_adopted_on_restart_without_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); backend=Backend(None); value=self.queue()
            self.controller(value,root,backend).tick(NOW)
            backend.actual=INV
            current=self.controller(value,root,backend).tick(NOW)
            self.assertEqual(current['seed4']['phase'],'started')
            self.assertEqual(current['seed4']['invocation_id'],INV)
            self.assertEqual(sum(call[0]=='launch' for call in backend.calls),1)
            self.assertEqual(sum(call[0]=='stage' for call in backend.calls),1)
            self.assertFalse(any(call[0]=='collect' for call in backend.calls))


if __name__=='__main__': unittest.main()
