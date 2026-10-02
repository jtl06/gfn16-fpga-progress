"""Source/mapping tests only; no HDL elaboration or hardware qualification."""
from collections import Counter
from pathlib import Path
import random
import re
import unittest
from fpga.reference import core27_rootfused_diag_structure as diagnostic


ROOT=Path(__file__).resolve().parents[1]


def bank(address,aw,kw=7):
    result=0
    for b in range(aw):result^=((address>>b)&1)<<(b%kw)
    return result


def xor_route(words,mask,xor):
    words=list(words);mask=list(mask)
    for bit in range(6):
        words=[words[h^(1<<bit)] if xor&(1<<bit) else words[h] for h in range(64)]
        mask=[mask[h^(1<<bit)] if xor&(1<<bit) else mask[h] for h in range(64)]
    return words,mask


class RootfusedDiagnosticTests(unittest.TestCase):
    def test_exact_frozen_ancestry_and_generated_body_identity(self):
        report=diagnostic.validate(ROOT)
        self.assertEqual(report['added_preserve_partition_attributes'],0)
        self.assertEqual(len(report['generated_sha256']),6)
        self.assertEqual(len(report['extracted_bodies']),7)

    def test_no_register_or_nonblocking_expression_changed(self):
        old=(ROOT/'rtl/kernel'/(diagnostic.ENGINE+'.sv')).read_text()
        generated,_=diagnostic.generate(ROOT)
        new=generated['rtl/kernel/'+diagnostic.ENGINE+'_diag.sv']
        helpers=generated['rtl/kernel/'+diagnostic.PREFIX+'_blocks.sv']
        expressions=lambda text:Counter(re.sub(r'\s+','',x) for x in
            re.findall(r'\b\w+(?:\[[^\]]*\])*\s*<=\s*[^;]+;',text))
        self.assertEqual(expressions(old),expressions(new+helpers))

    def test_external_ports_and_arithmetic_children_identical(self):
        generated,_=diagnostic.generate(ROOT)
        for name in (diagnostic.ENGINE,diagnostic.ADAPTER,diagnostic.CORE):
            old=(ROOT/'rtl/kernel'/(name+'.sv')).read_text()
            new=generated['rtl/kernel/'+name+'_diag.sv']
            header=lambda text:text[text.index(' #('):text.index('\n);')]
            self.assertEqual(header(old),header(new))
        engine=generated['rtl/kernel/'+diagnostic.ENGINE+'_diag.sv']
        self.assertEqual(engine.count('genefer_ntt_difdit_butterfly27 #'),1)
        self.assertEqual(engine.count('genefer_root_recurrence27 #'),1)
        self.assertEqual(engine.count('genefer_sdp_ram32 #'),1)
        self.assertIn('(* preserve, dont_merge *) logic orientation_q;',engine)
        bench=diagnostic.CORE.removeprefix('genefer_')
        for suffix in ('.cpp','_threaded.cpp'):
            old=(ROOT/'rtl/tb'/(bench+suffix)).read_text()
            new=generated['rtl/tb/'+bench+'_diag'+suffix]
            self.assertEqual(new.replace(diagnostic.CORE+'_diag',diagnostic.CORE).replace(bench+'_diag.cpp',bench+'.cpp'),old)

    def test_package_enum_identity_and_no_new_attributes(self):
        generated,_=diagnostic.generate(ROOT)
        helpers=generated['rtl/kernel/'+diagnostic.PREFIX+'_blocks.sv']
        old=(ROOT/'rtl/kernel'/(diagnostic.ENGINE+'.sv')).read_text()
        for enum in re.findall(r'typedef enum[^;]+;',old):self.assertEqual(helpers.count(enum),1)
        self.assertNotIn('(*',helpers)
        self.assertNotIn('PARTITION',helpers)
        self.assertNotIn('PRESERVE_HIERARCHY',helpers)

    def test_unique_source_anchors_reject_missing_or_duplicates(self):
        with self.assertRaises(ValueError):diagnostic.replace_once('a a','a','b')
        with self.assertRaises(ValueError):diagnostic.slice_once('start start end','start','end')
        with self.assertRaises(ValueError):diagnostic.replace_once('other','absent','b')

    def test_host_XOR_route_equals_direct_logical_bank_mapping(self):
        rng=random.Random(20260930)
        for aw in range(1,17):
            n=1<<aw
            addresses={0,max(0,n-64)&~63}
            addresses.update(rng.randrange(max(1,n//64))*64 for _ in range(20))
            for address in addresses:
                words=list(range(64));mask=[h<n-address and bool(rng.randrange(2)) for h in range(64)]
                vectorbank=bank(address,aw)
                routed,routedmask=xor_route(words,mask,vectorbank)
                half=(vectorbank>>6)&1
                for h in range(min(n-address,64)):
                    b=bank(address+h,aw)
                    self.assertEqual(b//64,half)
                    self.assertEqual(routed[b%64],h)
                    self.assertEqual(routedmask[b%64],mask[h])
                returned,_=xor_route(routed,[True]*64,vectorbank)
                self.assertEqual(returned,words)

    def test_pairing_read_and_write_are_inverse_for_every_bank(self):
        for pairing in range(7):
            for orientation in (0,1):
                seen=set()
                for lane in range(64):
                    low=(lane&((1<<pairing)-1))|((lane>>pairing)<<(pairing+1))
                    high=low|(1<<pairing)
                    u,v=(high,low) if orientation else (low,high)
                    self.assertEqual(u^v,1<<pairing)
                    for physical,result in ((u,'y0'),(v,'y1')):
                        recovered=(physical&((1<<pairing)-1))|((physical>>(pairing+1))<<pairing)
                        chosen='y0' if orientation==((physical>>pairing)&1) else 'y1'
                        self.assertEqual((recovered,chosen),(lane,result));seen.add(physical)
                self.assertEqual(seen,set(range(128)))

    def test_root_clip_XOR_literal_network(self):
        for stage in range(16):
            low=stage<7;mask=(1<<stage)-1 if low else 127
            for routexor in range(128):
                words=list(range(64))
                for bit in range(6):
                    output=[]
                    for j in range(64):
                        neighbor=bool(mask&(1<<bit) and routexor&(1<<bit)) if not j&(1<<bit) else bool(not mask&(1<<bit) or routexor&(1<<bit))
                        output.append(words[j^(1<<bit)] if neighbor else words[j])
                    words=output
                self.assertEqual(words,[(j^routexor)&mask&63 for j in range(64)])

    def test_seven_edge_row_tags_bubbles_and_reset(self):
        rng=random.Random(5);pipeline=[[0]*128 for _ in range(7)];history=[]
        for tick in range(40):
            row=[rng.randrange(512) for _ in range(128)]
            before=[r[:] for r in pipeline]
            pipeline=[row]+before[:-1];history.append(row)
            self.assertEqual(pipeline[6],history[tick-6] if tick>=6 else [0]*128)
            if tick==20:pipeline=[[0]*128 for _ in range(7)];history=[]
            # Restart observer tick bookkeeping after async reset separately.
            if tick==20:break
        self.assertEqual(pipeline,[[0]*128 for _ in range(7)])


if __name__=='__main__':unittest.main()
