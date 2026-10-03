import copy
import unittest
from fpga.reference import stream27_context_lean_watchdog_bind as bind


class WarmWatchdog(unittest.TestCase):
    def test_exact_default_reverse_and_routing(self):
        for n in (256,65536):
            self.assertEqual(bind.prepare(n,enabled=0),bind.capture(n))
            candidate=bind.prepare(n,enabled=1)
            self.assertEqual(len(candidate['files']),58)
        parent=bind.capture(256)
        self.assertEqual(bind.bind(parent,enabled=0),parent)
        candidate=bind.bind(parent,enabled=1)
        record=candidate['lean_watchdog_warm_progress']
        raw=candidate['files'][candidate['top']+'.sv']
        for before,after in reversed(record['root_edits']):raw=raw.replace(after,before,1)
        self.assertEqual(raw,parent['files'][parent['top']+'.sv'])
        self.assertEqual(candidate['geometry'],parent['geometry'])
        self.assertEqual(candidate['parameters'],parent['parameters'])
        self.assertEqual(len(candidate['files']),58)
        self.assertFalse(record['host_gl_implemented'])
        self.assertFalse(record['native_qualified'])
        self.assertIn('child_completed!=lean_completed_seen',bind.AFTER)
        self.assertNotIn('child_started',bind.AFTER)
        self.assertNotIn('|busy',bind.AFTER)
        changed=copy.deepcopy(parent);changed['parameters']['P']=8
        with self.assertRaises(ValueError):bind.bind(changed,enabled=1)
        with self.assertRaises(ValueError):bind.bind(parent,enabled=True)

    def test_real_completion_progress_vs_stall_and_sticky_reset(self):
        for interval,squares in ((214,8000),(8460,1000)):
            n=256 if interval==214 else 65536
            value=bind.watchdog_trace(n,interval,squares)
            self.assertFalse(value['error'])
            stalled=bind.watchdog_trace(n,interval,1,stall=True)
            self.assertTrue(stalled['error'])
            self.assertEqual(stalled['first_error_edge'],64*n+4096)


if __name__=='__main__':unittest.main()
