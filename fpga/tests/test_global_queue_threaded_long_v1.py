"""Exact threaded-long intake only; no transport/model/reference execution."""
import copy
import hashlib
import io
import json
import tarfile
import unittest
from unittest.mock import patch

from fpga.tools import global_queue_v1 as q


class ThreadedLongTests(unittest.TestCase):
    def setUp(self):
        self.ticket=json.loads((q.QUEUE/'inputs/soak-t5b-thread1000-q3-v1.json').read_text())

    def test_actual_intrinsic_packet(self):
        q.validate(self.ticket)

    def test_old_nonintrinsic_runner_refused(self):
        self.ticket['package']['runner']='tools/native_threaded_long_package_v1.py'
        with self.assertRaisesRegex(ValueError,'existing finite package runner'):
            q.validate(self.ticket)

    def test_other_cap_and_stager_dependencies_refused(self):
        altered=copy.deepcopy(self.ticket)
        altered['resources']['ram_gib']=8
        with self.assertRaisesRegex(ValueError,'exact intrinsic measured'):
            q.validate(altered)

    def test_exact_completed_pilot_placement_required(self):
        for change in ({'placement_from':'other-pilot'},{'after':[]},{'priority':'P1'}):
            altered=dict(self.ticket,**change)
            with self.assertRaisesRegex(ValueError,'exact intrinsic measured'):
                q.validate(altered)
        altered=copy.deepcopy(self.ticket)
        altered['package']['stager_dependencies'].pop()
        with self.assertRaisesRegex(ValueError,'dependency closure'):
            q.validate(altered)

    def test_wrong_duration_rehashed_metadata_refused(self):
        package=self.ticket['package']
        with tarfile.open(package['archive'],'r:gz') as archive:
            values={name:archive.extractfile(name).read() for name in ('ticket.json','manifest.json')}
        native=json.loads(values['ticket.json'])
        native['runtime_duration']['model_command_seconds']=4501
        values['ticket.json']=json.dumps(native).encode()
        package['ticket_sha256']=hashlib.sha256(values['ticket.json']).hexdigest()
        class Metadata:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def extractfile(self,name): return io.BytesIO(values[name])
        with patch.object(q.tarfile,'open',return_value=Metadata()):
            with self.assertRaisesRegex(ValueError,'immutable typed threaded duration'):
                q.validate(self.ticket)

    def test_never_serial_auto_converted(self):
        with patch.object(q,'rows',return_value=[self.ticket]), patch.object(q,'dependency_state',return_value=(True,'')), \
             patch.object(q,'role_host_compatible',side_effect=AssertionError('special policy converted')):
            q.automatic_variants([],[])


if __name__=='__main__': unittest.main()
