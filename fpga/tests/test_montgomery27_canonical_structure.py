"""Local source/integer/clock-model checks, never RTL compilation/simulation."""
import random
from pathlib import Path
import unittest
from unittest.mock import patch

from reference import montgomery27_canonical_structure as m

ROOT=Path(__file__).resolve().parents[1]


class CanonicalMultiplierTests(unittest.TestCase):
    def test_exact_source_delta_and_ancestor(self):
        self.assertEqual(len(m.validate_files(ROOT)),1)
        source=(ROOT/'rtl/kernel'/(m.ANCESTOR+'.sv')).read_text()
        with self.assertRaises(ValueError):m.expected(source+'\n')
        candidate=m.expected(source)
        # Public ports and every internal width/reset/gating/valid/assertion
        # statement match exactly, except the two permitted result assignments.
        restored=candidate.replace(m.TOP,m.ANCESTOR).replace(
            '// Isolated RTL-only candidate: explicitly zero-extended27-bit result, II=1.',
            '// Experimental four-stage Montgomery multiplier, II=1.').replace(
            "result<={5'b0,27'(hi_s3-mp_hi)};",'result<=hi_s3-mp_hi;').replace(
            "result<={5'b0,27'(hi_s3+P-mp_hi)};",'result<=hi_s3+P-mp_hi;')
        self.assertEqual(restored,source)

    def test_source_guard_rejects_extra_width_latency_and_valid_changes(self):
        target=ROOT/'rtl/kernel'/(m.TOP+'.sv');source=target.read_text();read=Path.read_text
        for old,new in [('logic [31:0] m_s2','logic [26:0] m_s2'),
                        ('logic [58:0] mp_s3','logic [53:0] mp_s3'),
                        ('out_valid<=valid_pipe[2]','out_valid<=valid_pipe[1]'),
                        ("27'(hi_s3-mp_hi)","26'(hi_s3-mp_hi)"),
                        ('if(valid_pipe[2])begin','if(in_valid)begin')]:
            altered=source.replace(old,new);self.assertNotEqual(altered,source)
            def content(path,*args,**kwargs):return altered if path==target else read(path,*args,**kwargs)
            with patch.object(Path,'read_text',content),self.assertRaises(ValueError):m.validate_files(ROOT)

    def test_exact_parameter_and_range_bounds(self):
        for p,q,_ in m.FIELDS:
            self.assertEqual(p*q%m.RADIX,1)
            self.assertEqual(q,(2-p)%m.RADIX)
            self.assertEqual((p-1)**2%m.RADIX,0)
            self.assertLess(1<<22,p);self.assertLess(p,1<<27)
            self.assertLess((1<<22)-1+p,1<<27)
            self.assertLess((m.RADIX-1)*p,1<<59)
        for p,q in ((17,1),(104857601,1)):
            with self.assertRaises(ValueError):m.parameters(p,q)

    def test_boundary_and_random_full27_math_not_expanded_API(self):
        rng=random.Random(270932);branches=set();noncanonical=0;top_bit_witness=False
        for p,q,_ in m.FIELDS:
            inv=pow(m.RADIX,-1,p)
            edges=sorted({0,1,2,p-2,p-1,p,p+1,(1<<26)-1,1<<26,(1<<27)-2,(1<<27)-1})
            pairs=[(a,b) for a in edges for b in edges]
            pairs.extend((rng.randrange(1<<27),rng.randrange(1<<27)) for _ in range(100000))
            self.assertEqual(len(pairs),100121)
            for a,b in pairs:
                r=m.mathematical_reduction(a,b,p,q);branches.add(r['corrected'])
                noncanonical+=int(a>=p or b>=p)
                self.assertEqual(r['m'],r['lo']*q%m.RADIX)
                self.assertEqual(r['mp'],r['m']*p)
                self.assertEqual(r['mp']%m.RADIX,r['lo'])
                self.assertLess(r['h'],1<<22);self.assertLess(r['k'],p)
                self.assertLess(-p,r['h']-r['k']);self.assertLess(r['h']-r['k'],p)
                self.assertEqual(r['before'],r['after'])
                self.assertEqual(r['after'],a*b*inv%p)
                self.assertTrue(0<=r['after']<p)
                if a<p and b<p and r['after']>=1<<26:top_bit_witness=True
        self.assertEqual(branches,{False,True});self.assertGreater(noncanonical,0)
        self.assertTrue(top_bit_witness,'26-bit narrowing would not be equivalent')

    def test_declared_input_contract_unchanged(self):
        for p,q,_ in m.FIELDS:
            model=m.PipelineModel(p,q)
            for a,b in ((p,1),(1,p),((1<<27)-1,1),(-1,1),(1<<31,1)):
                with self.assertRaisesRegex(ValueError,'noncanonical'):model.edge(in_valid=True,a=a,b=b)
            # Invalid payload is irrelevant on bubbles/reset, just as RTL.
            model.edge(in_valid=False,a=1<<31,b=-1)
            self.assertEqual(model.edge(rst_n=False,in_valid=True,a=p,b=p),(False,0))

    def test_pipeline_random_bubbles_reset_flush_hold_and_II1(self):
        rng=random.Random(325427)
        for p,q,_ in m.FIELDS:
            model=m.PipelineModel(p,q);pending={};last=0;inv=pow(m.RADIX,-1,p);outputs=0
            for edge in range(20000):
                rst_n=edge%137 not in (0,1);valid=edge%17<13
                a=rng.randrange(p);b=rng.randrange(p)
                if not rst_n:pending.clear();last=0
                elif valid:pending[edge+3]=a*b*inv%p
                got_valid,got=model.edge(rst_n,valid,a,b)
                expected=pending.pop(edge,None) if rst_n else None
                self.assertEqual(got_valid,expected is not None)
                if expected is not None:last=expected;outputs+=1
                self.assertEqual(got,last);self.assertLess(got,1<<27)
            self.assertGreater(outputs,14000)

    def test_cancellation_at_every_pipeline_age(self):
        for p,q,_ in m.FIELDS:
            for age in range(4):
                model=m.PipelineModel(p,q);model.edge(in_valid=True,a=p-1,b=p-1)
                for _ in range(age):model.edge()
                self.assertEqual(model.edge(rst_n=False),(False,0))
                for _ in range(5):self.assertEqual(model.edge(),(False,0))
                model.edge(in_valid=True,a=1,b=1)
                self.assertFalse(model.edge()[0]);self.assertFalse(model.edge()[0])
                self.assertEqual(model.edge(),(True,pow(m.RADIX,-1,p)))


if __name__=='__main__':unittest.main()
