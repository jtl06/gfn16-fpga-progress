"""Pure Python arithmetic/edge and source-contract tests; no HDL or cloud."""
import hashlib
from pathlib import Path
import random
import tempfile
import unittest
from reference import stream27_signed_boundary_oracle as o
from reference import stream27_signed_boundary_structure as structure

FPGA=Path(__file__).resolve().parents[1]
RTL=FPGA/'rtl/kernel/genefer_stream27_signed_boundary_reduce27_pipe.sv'
CHILD=FPGA/'rtl/kernel/genefer_digit_reduce27_pipe.sv'
CHILD_SHA='61e14bb13c2dbcc13b5030756578a0d0358269beb24fb207a5641b98795883e8'


def word(x):return x&0xffffffff


class ArithmeticTests(unittest.TestCase):
    def test_all_geometry_bounds_and_both_signs(self):
        for aw in range(5,17):
            for blocks in (8,16):
                _,k,minimum=o.geometry(aw,blocks)
                for base in (minimum,minimum+1,1_000_000_000):
                    for kind,limit in ((0,base-1),(1,k)):
                        for x in (-limit,-1,0,1,limit):
                            for p in o.FIELDS:
                                r=o.evaluate(word(x),kind,base,aw=aw,blocks=blocks,p=p)
                                self.assertFalse(r['error']);self.assertEqual(r['residue'],x%p)
                        for x in (-limit-1,limit+1):self.assertTrue(o.evaluate(word(x),kind,base,aw=aw,blocks=blocks)['error'])

    def test_modulus_and_subtraction_threshold_neighbors(self):
        for p in o.FIELDS:
            values={0,1,-1,999999999,-999999999}
            for multiplier in range(1,17):
                for delta in (-1,0,1):
                    x=multiplier*p+delta
                    if x<=999999999:values.update((x,-x))
            for x in values:
                result=o.evaluate(word(x),0,1_000_000_000,p=p)
                self.assertFalse(result['error']);self.assertEqual(result['residue'],x%p)
            for x in (-p,-2*p,-8*p):
                self.assertEqual(o.evaluate(word(x),0,1_000_000_000,p=p)['residue'],0)

    def test_fixed_random_exact_integer_modulo(self):
        rng=random.Random(0xB0322026)
        for i in range(20000):
            aw=rng.randrange(5,17);blocks=rng.choice((8,16));_,k,minimum=o.geometry(aw,blocks)
            base=rng.randrange(minimum,1_000_000_001);kind=rng.randrange(2);limit=k if kind else base-1
            x=rng.randrange(-limit,limit+1);p=o.FIELDS[i%3]
            self.assertEqual(o.evaluate(word(x),kind,base,aw=aw,blocks=blocks,p=p)['residue'],x%p)

    def test_full_word_guard_and_transport_are_distinct(self):
        for x in (-2147483648,2147483647,-1000000000,1000000000):
            for kind in (0,1):self.assertTrue(o.evaluate(word(x),kind,1_000_000_000)['error'])
        for bad in (-1,1<<32,True):
            with self.assertRaises(ValueError):o.evaluate(bad,0,1_000_000_000)
        for base in (0,131076,1000000001,0xffffffff):self.assertTrue(o.evaluate(0,0,base)['error'])
        for bad in (0,3,65536):
            with self.assertRaises(ValueError):o.geometry(16,bad)

    def test_source_frozen_child_and_wide_before_narrowing(self):
        self.assertEqual(hashlib.sha256(CHILD.read_bytes()).hexdigest(),CHILD_SHA)
        text=RTL.read_text()
        for anchor in ('wire signed [32:0] wide_correction={correction[31],correction}',
                       "33'(-wide_correction)","legal ? magnitude[31:0] : 32'h80000000",
                       '.PAYLOAD_W(PAYLOAD_W+1)', '.payload_in({correction[31],payload_in})',
                       'magnitude_payload[PAYLOAD_W] && magnitude_residue!=0',
                       'if(magnitude_valid || magnitude_error)payload_out',
                       'out_valid<=magnitude_valid','out_error<=magnitude_error'):
            self.assertEqual(text.count(anchor),1)
        self.assertNotIn('genefer_digit_reduce27_pipe.sv"',text)

    def test_arithmetic_mutant_witnesses_are_typed_not_qualification(self):
        p=o.FIELDS[0]
        self.assertNotEqual((-17)%p,17%p)  # omitted sign
        self.assertNotEqual((-p)%p,p)      # missing negative-zero branch
        self.assertTrue(o.evaluate(0x80000000,0,1_000_000_000)['error'])
        self.assertNotEqual((-2147483648)%p,(0x80000000&0x07ffffff)%p)  # premature truncation

    def test_exact_source_contract(self):
        result=structure.validate();self.assertEqual(result['acceptance_output_edge_offset'],4)
        self.assertEqual(result['initiation_interval'],1)

    def test_source_and_frozen_child_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in structure.PINS:
                destination=root/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes((FPGA/name).read_bytes())
            structure.validate(root)
            for name in structure.PINS:
                destination=root/name;original=destination.read_bytes();destination.write_bytes(original+b'\n')
                with self.assertRaisesRegex(ValueError,'source identity'):structure.validate(root)
                destination.write_bytes(original)


class EdgeTests(unittest.TestCase):
    def test_D4_payload_bubbles_invalid_hold_and_dense_II1(self):
        dut=o.Pipeline();tokens=[(-1,0,101),(17,0,102),(-2147483648,0,103),(-o.FIELDS[0],0,104)]
        for edge in range(12):
            if edge<len(tokens):x,kind,tag=tokens[edge];out=dut.edge(in_valid=True,word=word(x),boundary_high=kind,payload=tag)
            else:out=dut.edge()
            if edge<4:self.assertFalse(out['out_valid'] or out['out_error'])
            if edge==4:self.assertEqual(out,dict(out_valid=True,out_error=False,residue=o.FIELDS[0]-1,payload=101))
            if edge==5:self.assertEqual(out['residue'],17);self.assertEqual(out['payload'],102)
            if edge==6:self.assertEqual(out,dict(out_valid=False,out_error=True,residue=17,payload=103))
            if edge==7:self.assertEqual(out,dict(out_valid=True,out_error=False,residue=0,payload=104))
            if edge>=8:self.assertEqual(out,dict(out_valid=False,out_error=False,residue=0,payload=104))

    def test_every_age_async_reset_cancels_due_and_immediate_restart(self):
        for age in range(5):
            dut=o.Pipeline();dut.edge(in_valid=True,word=word(-1),payload=900)
            for _ in range(age):dut.edge()
            self.assertEqual(dut.async_reset(),dict(out_valid=False,out_error=False,residue=0,payload=0))
            dut.edge(in_valid=True,word=23,payload=901)
            for i in range(4):out=dut.edge();self.assertEqual(out['out_valid'],i==3)
            self.assertEqual(out['residue'],23);self.assertEqual(out['payload'],901)
            for _ in range(5):self.assertFalse(dut.edge()['out_valid'])

    def test_mixed_base_and_kinds_metadata_are_token_local(self):
        dut=o.Pipeline();_,k,minimum=o.geometry(16,8)
        expected=[]
        for i,(x,kind,base) in enumerate(((minimum-1,0,minimum),(-k,1,minimum),(-minimum,0,minimum),(0,1,0),(k,1,1_000_000_000))):
            expected.append((o.evaluate(word(x),kind,base),i+1));dut.edge(in_valid=True,word=word(x),boundary_high=kind,base=base,payload=i+1)
        # The first response matured on edge4; remaining four are independently due.
        for result,tag in expected[1:]:
            out=dut.edge();self.assertEqual(out['payload'],tag);self.assertEqual(out['out_error'],result['error'])
            if not result['error']:self.assertEqual(out['residue'],result['residue'])


if __name__=='__main__':unittest.main()
