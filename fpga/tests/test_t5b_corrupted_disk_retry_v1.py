import importlib.util
from pathlib import Path
import unittest

FPGA=Path(__file__).resolve().parents[1]
PATH=FPGA/'results/throughput-20260929/core27_t5b_corrupted_disk_retry_v1.py'
SPEC=importlib.util.spec_from_file_location('disk_retry',PATH)
gate=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(gate)


class DiskRetryDerivationTests(unittest.TestCase):
    def test_only_scratch_and_positive_guard_change(self):
        raw=(FPGA/'tools/native_source_gate_v1.py').read_bytes();derived=gate.derive_helper(raw)
        expected=raw.decode().replace("tempfile.mkdtemp(prefix='gfn16-source-gate-', dir='/dev/shm')","tempfile.mkdtemp(prefix='gfn16-source-gate-', dir="+repr(str(gate.DISK))+")").replace('    def guard():\n','    def guard():\n        STORAGE_GUARD()\n').encode()
        self.assertEqual(derived,expected);compile(derived,'derived','exec')
        self.assertIn(b'durable_floor_bytes=10*GIB',derived)
        self.assertIn(b'scratch_floor_bytes=2*GIB',derived)
        self.assertNotIn(b'-Wno-fatal',derived)

    def test_changed_parent_rejected(self):
        raw=(FPGA/'tools/native_source_gate_v1.py').read_bytes()
        for changed in (raw+b'\n',raw.replace(b'compile_workers=2',b'compile_workers=4')):
            with self.assertRaises(ValueError):gate.derive_helper(changed)


if __name__=='__main__':unittest.main()
