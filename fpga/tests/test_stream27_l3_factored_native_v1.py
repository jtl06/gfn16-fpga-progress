import hashlib
import json
import re
import unittest
from fpga.reference import stream27_l3_factored_native_v1 as n
from fpga.reference import stream27_l3_factored_mutants_v1 as m
from fpga.reference import stream27_l3_factored_probe_v1 as probe

class L3NativeSources(unittest.TestCase):
    def test_normal_exact_source_and_snapshot(self):
        n.verify()
        for p in n.HIGH:
            manifest,files=n.role(p)
            declared=manifest['rtl_readiness'];sources=declared['source_snapshot']
            digest=hashlib.sha256(json.dumps(sources,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            self.assertEqual(declared['candidate_source_sha256'],digest)
            self.assertEqual(declared['rtl_ready_at_utc'],'2026-10-01T19:03:12Z')
            self.assertEqual(manifest['test_role'],'normal')
            self.assertTrue(all(manifest['sources'][key]==value for key,value in sources.items()))
            self.assertTrue(all(n.s.sha(raw)==manifest['sources'][key] for key,raw in files.items()))
    def test_mutations_are_four_isolated_single_site_deltas(self):
        m.verify();text=m.generated_sv()
        self.assertEqual(len(m.MUTATIONS),4)
        self.assertEqual(text.count('wire [53:0] low_product=lhs[26:0]*rhs;'),4)
        for p in n.HIGH:
            manifest,_=m.role(p)
            self.assertEqual(manifest['test_role'],'deliberate_fault')
            self.assertEqual(manifest['build']['sv_sources'],[m.SV,n.s.RTL])
            self.assertTrue(all(re.fullmatch('[a-z][a-z0-9-]*',step['name']) for step in manifest['steps']))
    def test_typed_validators_do_not_accept_missing_fault_or_phase_checks(self):
        for p,high in n.HIGH.items():
            normal=f'PASS_L3_FACTORED P={p} checked=16925 canceled=224 holds=3166 high_inputs={high} edges=20091 outputs=4\n'
            mutants=f'PASS_L3_MUTANTS P={p} checked=16925 canceled=224 holds=3166 high_inputs={high} edges=20091 detected=15\n'
            self.assertEqual(n.validate(normal,'',0,{'p':p},{})['latency'],3)
            self.assertEqual(len(m.validate(mutants,'',0,{'p':p},{})['mutants_detected']),4)
            for output in (normal.replace('outputs=4','outputs=3'),normal.replace('16925','16924')):
                with self.assertRaises(ValueError):n.validate(output,'',0,{'p':p},{})
            with self.assertRaises(ValueError):m.validate(mutants.replace('detected=15','detected=14'),'',0,{'p':p},{})
            with self.assertRaises(ValueError):m.validate(mutants,'',1,{'p':p},{})
    def test_sizing_probe_uses_independent_four_cells_and_same_leaf_sources(self):
        self.assertEqual((n.ROOT/probe.WRAPPER).read_text(),probe.TEXT)
        for index,cell in enumerate(('new_canonical','frozen_canonical','new_lazy','frozen_lazy')):
            self.assertIn(cell+'(',probe.TEXT)
            self.assertIn(f'.in_valid(valid_q[{index}])',probe.TEXT)
            self.assertIn(f'.result(result[{32*index}+:32])',probe.TEXT)
        self.assertEqual(len(probe.gates()),3)
        snapshot=probe.fit_dispatch.snapshot(n.ROOT/'results/throughput-20260929/stream27-l3-factored-cell-f0-source-v1/project')
        self.assertEqual(snapshot['source_sha256']['genefer_stream27_montgomery_factored_v1.sv'],n.PINS[n.s.RTL])
        self.assertEqual(len(snapshot['source_sha256']),4)

if __name__=='__main__':unittest.main()
