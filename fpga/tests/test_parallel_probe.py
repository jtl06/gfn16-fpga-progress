import json
from pathlib import Path
import tempfile
import unittest

from synthesis.prepare import prepare
from synthesis.parallel_probe import clone


class ParallelProbeTests(unittest.TestCase):
    def test_only_processor_setting_changes(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"original";destination=Path(d)/"parallel"
            old=prepare(source,"multiplier27_sparse",field=3,period=5,processors=2)
            (source/"output_files").mkdir()
            (source/"output_files/stale.txt").write_text("do not reuse")
            new=clone(source,destination,8)
            self.assertEqual(new["source_sha256"],old["source_sha256"])
            self.assertEqual(new["clock_period_ns"],old["clock_period_ns"])
            self.assertEqual(new["field_parameters"],old["field_parameters"])
            self.assertEqual(new["compile_processors"],8)
            self.assertEqual((source/"probe.qsf").read_text().replace("NUM_PARALLEL_PROCESSORS 2","NUM_PARALLEL_PROCESSORS 8"),
                             (destination/"probe.qsf").read_text())
            for name in ("probe.qpf","probe.sdc","run.tcl"):
                self.assertEqual((source/name).read_bytes(),(destination/name).read_bytes())
            self.assertFalse((destination/"output_files").exists())
            with self.assertRaises(FileExistsError):clone(source,destination,4)

    def test_tampering_and_unbounded_parallelism_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"original";destination=Path(d)/"parallel"
            m=prepare(source,"multiplier27_sparse")
            for n in (0,17,2.5,True):
                with self.assertRaises(ValueError):clone(source,destination,n)
            name=next(iter(m["source_sha256"]))
            (source/"rtl"/name).write_text("changed")
            with self.assertRaisesRegex(ValueError,"hash mismatch"):clone(source,destination,4)
            self.assertFalse(destination.exists())

    def test_hardware_stages_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"original";destination=Path(d)/"parallel"
            m=prepare(source,"multiplier27_sparse")
            m["allowed_stages"].append("asm")
            (source/"manifest.json").write_text(json.dumps(m))
            with self.assertRaises(ValueError):clone(source,destination,4)
