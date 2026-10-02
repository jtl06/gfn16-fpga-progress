import json
from pathlib import Path
import shutil
import tempfile
import unittest
from fpga.tools.prefit_t5b_seed95_v1 import assess

ROOT=Path(__file__).resolve().parents[1]


class SeedSource(unittest.TestCase):
    def test_both_exact_projects_synthesis_only(self):
        for seed in (2,3):
            r=assess(ROOT/f'artifacts/t5b-seed{seed}-95ns-azure-v1/project')
            self.assertTrue(r['synthesis_allowed'])
            self.assertEqual((r['seed'],r['clock_period_ns'],r['workers']),(seed,9.5,4))
            for flag in ('fit_allowed','promotion_allowed','native_crossing_coverage_complete','native_design_assistant_pass'):
                self.assertFalse(r[flag])

    def test_exact_source_control_evidence_drift_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'project';shutil.copytree(ROOT/'artifacts/t5b-seed2-95ns-azure-v1/project',p)
            names=['probe.qsf','probe.qpf','probe.sdc','run.tcl','evidence/parent-manifest.json',
                   'evidence/parent-100-review.json','evidence/parent-9668-review.json',
                   'rtl/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv']
            for name in names:
                with self.subTest(name=name):
                    path=p/name;old=path.read_bytes();path.write_bytes(old+b'\n')
                    with self.assertRaises(ValueError):assess(p)
                    path.write_bytes(old)
            (p/'rtl/extra.sv').write_text('module extra;endmodule\n')
            with self.assertRaises(ValueError):assess(p)

    def test_functional_manifest_and_promotion_drift_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'project';shutil.copytree(ROOT/'artifacts/t5b-seed2-95ns-azure-v1/project',p)
            path=p/'manifest.json';original=json.loads(path.read_text())
            for key,value in [('seed',4),('compile_processors',6),('clock_period_ns',9.4),
                ('address_width',8),('core_parameters',{'NTT_LANES':32}),('source_sha256',{}),
                ('control_sha256',{}),('promotion_allowed',True),('usable_clock_mhz',105)]:
                with self.subTest(key=key):
                    m=dict(original);m[key]=value;path.write_text(json.dumps(m))
                    with self.assertRaises(ValueError):assess(p)


if __name__=='__main__':unittest.main()
