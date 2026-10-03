from pathlib import Path
import tempfile
import unittest

from fpga.host.r15_arithmetic import Checkpoint, HostFault, SoftwareBackend
from fpga.host.r15_boinc_wrapper import SlotPlan, SoftwareBoincService, Status


class Calls:
    def __init__(self, status=Status()):
        self.current=status;self.saved=[];self.progress=[];self.acks=0
    def status(self):return self.current
    def time_to_checkpoint(self):return True
    def save_checkpoint(self, raw):self.saved.append(raw)
    def checkpoint_completed(self):self.acks+=1
    def fraction_done(self, value):self.progress.append(value)


class Wrapper(unittest.TestCase):
    def test_slot_resolver_contains_paths_without_writing(self):
        with tempfile.TemporaryDirectory() as raw:
            plan=SlotPlan(raw, lambda name:name, enabled=True)
            self.assertEqual(plan.path('checkpoint'), Path(raw).resolve()/'checkpoint')
            with self.assertRaises(HostFault):plan.path('../outside')
            plan=SlotPlan(raw, lambda name:'/etc/passwd', enabled=True)
            with self.assertRaises(HostFault):plan.path('checkpoint')

    def test_suspend_checkpoint_abort_only_verified(self):
        b=SoftwareBackend(10,32,enabled=True);b.load(99)
        cp=Checkpoint(10,32,1,0,4,7,'source')
        calls=Calls(Status(suspended=True))
        service=SoftwareBoincService(b,cp,calls,8,enabled=True)
        self.assertEqual(service.poll(),'suspended_no_progress')
        self.assertEqual(b.read(),99);self.assertFalse(calls.saved)
        calls.current=Status()
        self.assertEqual(service.poll(),'software_ready')
        self.assertEqual(calls.acks,1);self.assertEqual(calls.progress,[0.5])
        calls.current=Status(abort_request=True)
        self.assertEqual(service.poll(),'abort_without_result_publication')
        self.assertEqual(b.read(),7);self.assertTrue(service.finished)
        self.assertEqual(calls.saved, [cp.encode(), cp.encode()])

    def test_default_off(self):
        with self.assertRaisesRegex(HostFault,'OFF'):
            SlotPlan('/tmp',lambda value:value)


if __name__=='__main__':unittest.main()
