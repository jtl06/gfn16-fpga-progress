"""Python source checks only; this does not simulate the integrated core."""
from pathlib import Path
import unittest
from unittest.mock import patch

from reference import core27_prefetch_r2_host_broadcast_core_structure as s


class BroadcastCoreStructureTests(unittest.TestCase):
    root=Path(__file__).resolve().parents[1]

    def text(self,relative):return (self.root/relative).read_text()

    def test_full_pinned_closure(self):
        pins=s.validate_files(self.root)
        self.assertEqual(len(pins),18)
        self.assertEqual(len(s.KERNEL_PINS),16)
        self.assertEqual(len(s.validate_bench_files(self.root)),2)
        self.assertNotIn('rtl/kernel/'+s.ANCESTOR+'.sv',pins)
        self.assertNotIn('rtl/kernel/'+s.OLD_HOST+'.sv',pins)

    def test_only_two_rtl_substitutions(self):
        old=self.text('rtl/kernel/'+s.ANCESTOR+'.sv')
        new=self.text('rtl/kernel/'+s.CANDIDATE+'.sv')
        normalized=new.replace('module '+s.CANDIDATE+' #(','module '+s.ANCESTOR+' #(')
        normalized=normalized.replace(s.NEW_HOST+' #(',s.OLD_HOST+' #(')
        self.assertEqual(normalized,old)
        self.assertEqual(new,s.core_source(old))
        self.assertEqual(new.count(s.NEW_HOST+' #('),1)
        self.assertEqual(new.count(".profile_format(8'd2)"),1)
        self.assertIn('.HOST_LANES(IO_WIDTH)',new)
        self.assertIn('localparam int CARRY_LANES=16;',new)
        self.assertIn('parameter int NTT_LANES=64',new)

    def test_kernel_closure_only_replaces_wrapper_and_top(self):
        from synthesis.prepare import CORE27_PREFETCH_R2_SOURCES
        expected=[{s.OLD_HOST+'.sv':s.NEW_HOST+'.sv',s.ANCESTOR+'.sv':s.CANDIDATE+'.sv'}.get(n,n)
                  for n in CORE27_PREFETCH_R2_SOURCES]
        self.assertEqual(list(s.KERNEL_PINS),expected)
        self.assertIn('genefer_digit_reduce27_pipe.sv',expected)
        self.assertIn('genefer_root_profile27_r2_rom.sv',expected)
        self.assertNotIn('genefer_montgomery_mul27_canonical_pipe.sv',expected)
        self.assertNotIn('genefer_ntt_banked27_prefetch_data27_engine.sv',expected)

    def test_bench_arithmetic_and_abort_byte_identity(self):
        old=self.text('rtl/tb/'+s.OLD_BENCH+'.cpp')
        new=self.text('rtl/tb/'+s.NEW_BENCH+'.cpp')
        self.assertEqual(new.replace('V'+s.CANDIDATE,'V'+s.ANCESTOR),old)
        self.assertEqual(new,s.bench_source(old))
        for guard in ('!abort_reached || !d.busy || d.done',
                      'd.conversion_cycles!=uint64_t((n+15)/16)+6',
                      'signed96(d.read_data)!=I(expected[i])',
                      'd.ntt_cycles!=expected_ntt || d.seed_setup_cycles!=expected_seed_setup',
                      'd.crt_cycles!=expected_crt'):
            self.assertIn(guard,new)

    def test_thread_wrapper_changes_only_model_and_include(self):
        old=self.text('rtl/tb/'+s.OLD_BENCH+'_threaded.cpp')
        new=self.text('rtl/tb/'+s.NEW_BENCH+'_threaded.cpp')
        normalized=new.replace('V'+s.CANDIDATE,'V'+s.ANCESTOR)
        normalized=normalized.replace('#include "'+s.NEW_BENCH+'.cpp"','#include "'+s.OLD_BENCH+'.cpp"')
        self.assertEqual(normalized,old)
        self.assertEqual(new,s.wrapper_source(old))
        self.assertEqual(new.count('CORE27_PREFETCH_R2_RUNTIME_THREADS'),old.count('CORE27_PREFETCH_R2_RUNTIME_THREADS'))
        self.assertLess(new.index('threadContextp()->threads(requested)'),new.index('V'+s.CANDIDATE+' dut;'))

    def test_changed_ancestor_or_ambiguous_anchor_rejected(self):
        for filename,transform in (('rtl/kernel/'+s.ANCESTOR+'.sv',s.core_source),
            ('rtl/tb/'+s.OLD_BENCH+'.cpp',s.bench_source),
            ('rtl/tb/'+s.OLD_BENCH+'_threaded.cpp',s.wrapper_source)):
            with self.subTest(filename=filename),self.assertRaisesRegex(ValueError,'ancestor identity'):
                transform(self.text(filename)+'\n')
        for text in ('absent','xx'):
            with self.assertRaisesRegex(ValueError,'ambiguous'):s.replace(text,'x','y')

    def test_core_mutations_outside_scope_rejected(self):
        relative='rtl/kernel/'+s.CANDIDATE+'.sv'
        original=self.text(relative)
        for old,new in ((".profile_format(8'd2)",".profile_format(8'd1)"),
                        ('localparam int CARRY_LANES=16;','localparam int CARRY_LANES=8;'),
                        ('conversion_cycles<=conversion_cycles+1;','conversion_cycles<=conversion_cycles+2;'),
                        ('104857601','104857603')):
            with self.subTest(anchor=old):
                self.assertIn(old,original)
                self.reject_mutated_file(relative,original.replace(old,new,1))

    def test_bench_and_dependency_mutations_rejected(self):
        relative='rtl/tb/'+s.NEW_BENCH+'.cpp';original=self.text(relative)
        for old,new in (('!abort_reached || !d.busy || d.done','!d.busy'),
                        ('uint64_t((n+15)/16)+6','uint64_t((n+15)/16)+9'),
                        ('signed96(d.read_data)!=I(expected[i])','false')):
            with self.subTest(anchor=old):self.reject_mutated_file(relative,original.replace(old,new,1))
        child='rtl/kernel/genefer_ntt_banked27_prefetch_r2_engine.sv'
        self.reject_mutated_file(child,self.text(child)+'\n')

    def reject_mutated_file(self,relative,mutated):
        read=Path.read_text;target=self.root/relative
        def supplied(path,*args,**kwargs):return mutated if path==target else read(path,*args,**kwargs)
        with patch.object(Path,'read_text',supplied),self.assertRaises(ValueError):s.validate_files(self.root)


if __name__=='__main__':unittest.main()
