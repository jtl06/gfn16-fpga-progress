"""Structural isolation checks, not RTL correctness or physical-fit evidence."""
from pathlib import Path
import hashlib
import shutil
import tempfile
import unittest

from fpga.reference.ntt27_prefetch_data27_regression import PARENT, TOP, check_clone

ROOT=Path(__file__).resolve().parents[1]

class Data27IsolationTests(unittest.TestCase):
    def test_exact_data_ram_only_delta(self):
        check_clone(ROOT)

    def test_root_profile_change_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);kernel=root/"rtl/kernel";kernel.mkdir(parents=True)
            for module in (PARENT,TOP):
                shutil.copy2(ROOT/"rtl/kernel"/(module+".sv"),kernel/(module+".sv"))
            candidate=kernel/(TOP+".sv")
            text=candidate.read_text()
            self.assertIn("genefer_sp_ram #(.WIDTH(32)",text)
            candidate.write_text(text.replace("genefer_sp_ram #(.WIDTH(32)","genefer_sp_ram #(.WIDTH(27)"))
            with self.assertRaisesRegex(AssertionError,"non-storage changes"):
                check_clone(root)

    def test_missing_pretruncation_assertion_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);kernel=root/"rtl/kernel";kernel.mkdir(parents=True)
            for module in (PARENT,TOP):
                shutil.copy2(ROOT/"rtl/kernel"/(module+".sv"),kernel/(module+".sv"))
            candidate=kernel/(TOP+".sv")
            text=candidate.read_text()
            self.assertIn("data_w[bank]>=P",text)
            candidate.write_text(text.replace("data_w[bank]>=P","data_w[bank][26:0]>=P"))
            with self.assertRaisesRegex(AssertionError,"non-storage changes"):
                check_clone(root)

    def test_benchmark_only_adds_diagnostics_and_fault_payloads(self):
        parent=(ROOT/"rtl/tb/ntt_banked27_prefetch_engine.cpp").read_text()
        self.assertEqual(hashlib.sha256(parent.encode()).hexdigest(),
            "7fadaaa7d32c80f91be878055300c9496412ace40f254d003e0d9dc2a281e585")
        expected=parent.replace('d.write_data=MODULUS;\n            std::string mode=std::getenv("NTT_NONCANON");',
            'd.write_data=MODULUS;\n            std::string mode=std::getenv("NTT_NONCANON");\n            if(mode.find("high")!=std::string::npos)d.write_data=0x80000001u;')
        expected=expected.replace('if(mode=="vector") {Beat payload{};payload[0]=MODULUS;',
            'if(mode.find("vector")!=std::string::npos) {Beat payload{};payload[0]=d.write_data;')
        expected=expected.replace('<<" cycles="<<d.cycles<<"\\n";++runs;',
            '<<" cycles="<<d.cycles<<" butterflies="<<d.butterflies<<" data_reads="<<d.data_reads<<" data_writes="<<d.data_writes<<" root_reads="<<d.root_reads<<" wait_cycles="<<d.wait_cycles<<"\\n";++runs;')
        self.assertEqual((ROOT/"rtl/tb/ntt_banked27_prefetch_data27_engine.cpp").read_text(),expected)

if __name__=="__main__":unittest.main()
