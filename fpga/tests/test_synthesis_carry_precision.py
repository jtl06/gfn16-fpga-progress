"""Source-pinned preparation checks for isolated reciprocal experiments."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from synthesis.prepare import AW_TARGETS, FIELD_TARGETS, LANE_PARAMETERS, TARGETS, prepare


SHARED = {
    "genefer_sp_ram.sv": "b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df",
    "genefer_carry_prefix_stream_pipe.sv": "9838c6852cac57f7901f8b57dcbb4ee11b7fa129ef86e40158d67cc789b06e5e",
}
CANDIDATES = {
    "dsp27": {
        "genefer_div_recip_dsp27.sv": "15d377127ae9c0274d7cdbc394127ec915a1fddd3979f48d718b0792c9a9b6be",
        "genefer_carry_prefix_stream_dsp27.sv": "8fff906268095811bf9cdb1d9fe481f3c505d43b723577e8a8288df1da959bc2",
    },
    "precision": {
        "genefer_div_recip_precision.sv": "832021ed0b3410dc867d92ac4436a725d5717f9630d233073e39896789ebbd7c",
        "genefer_carry_prefix_stream_precision.sv": "ba7ce9d0c1a99ad959bfe9909c62f341fabd537c76f196c5bcb6394c161296d3",
    },
}


class CarryPrecisionPrepareTests(unittest.TestCase):
    def test_all_targets_snapshot_exact_frozen_dependency_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            for variant, hashes in CANDIDATES.items():
                for lanes in (4,16):
                    with self.subTest(variant=variant, lanes=lanes):
                        target=f"carry_stream_{variant}{lanes}"
                        path=Path(directory)/target
                        manifest=prepare(path,target,aw=16,period=5,processors=2)
                        self.assertEqual(manifest["source_sha256"],SHARED | hashes)
                        self.assertEqual(manifest["top"],f"genefer_carry_prefix_stream_{variant}")
                        self.assertEqual(manifest["address_width"],16)
                        self.assertEqual(manifest["clock_period_ns"],5)
                        self.assertEqual(manifest["compile_processors"],2)
                        self.assertEqual(manifest["allowed_stages"],["syn","fit","sta"])
                        self.assertFalse(manifest["bitstream_generation"])
                        self.assertEqual(manifest["status"],"prepared_not_vendor_validated")
                        self.assertIsNone(manifest["field_parameters"])
                        self.assertIsNone(manifest["core_parameters"])
                        for filename, expected in manifest["source_sha256"].items():
                            self.assertEqual(hashlib.sha256((path/"rtl"/filename).read_bytes()).hexdigest(),expected)
                        qsf=(path/"probe.qsf").read_text()
                        self.assertEqual([line for line in qsf.splitlines() if line.startswith("set_parameter")],
                                         ["set_parameter -name AW 16",f"set_parameter -name LANES {lanes}"])
                        self.assertIn("set_global_assignment -name NUM_PARALLEL_PROCESSORS 2",qsf)
                        self.assertIn("create_clock -name kernel_clk -period 5",(path/"probe.sdc").read_text())
                        pins=TARGETS[f"carry_stream{lanes}"][2]
                        self.assertEqual(TARGETS[target][2],pins)
                        self.assertEqual([line for line in qsf.splitlines() if "VIRTUAL_PIN" in line],
                            [f"set_instance_assignment -name VIRTUAL_PIN ON -to {{{pin}}}" for pin in pins])

    def test_target_membership_and_no_legacy_selection_change(self):
        for variant in CANDIDATES:
            for lanes in (4,16):
                target=f"carry_stream_{variant}{lanes}"
                self.assertEqual(LANE_PARAMETERS[target],lanes)
                self.assertIn(target,AW_TARGETS)
                self.assertNotIn(target,FIELD_TARGETS)
                self.assertEqual(TARGETS[f"carry_stream{lanes}"][0],"genefer_carry_prefix_stream")
                self.assertEqual(TARGETS[f"carry_stream_divpipe{lanes}"][0],"genefer_carry_prefix_stream_divpipe")
        self.assertNotIn("genefer_div_recip_precision.sv",TARGETS["square_core"][1])
        self.assertNotIn("genefer_div_recip_dsp27.sv",TARGETS["square_core"][1])

    def test_rejects_overwrite_and_invalid_width_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            for variant in CANDIDATES:
                target=f"carry_stream_{variant}4"
                path=Path(directory)/variant
                prepare(path,target,aw=1,period=5,processors=2)
                before=(path/"manifest.json").read_bytes()
                with self.assertRaises(FileExistsError):
                    prepare(path,target,aw=16,period=5,processors=2)
                self.assertEqual((path/"manifest.json").read_bytes(),before)
                bad=Path(directory)/(variant+"-bad")
                with self.assertRaises(ValueError):
                    prepare(bad,target,aw=17,period=5,processors=2)
                self.assertFalse(bad.exists())


if __name__ == "__main__":
    unittest.main()
