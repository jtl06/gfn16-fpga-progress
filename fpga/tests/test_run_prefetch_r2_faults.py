"""Source contracts and independent integer checks only; no RTL execution."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import run_prefetch_r2_faults as f

ROOT=Path(__file__).resolve().parents[1]


def example_metric(label,base):
    row=dict(conversion=4102,roots=8743,ntt=20558,crt=4158,carry=4147,passes=2,
             base=base,profile_before=0,profile_loads=1,profile_hits=0,profile_words=8738,
             seed_setup=815,readback=1)
    row['cycles']=sum(row[k] for k in ('conversion','roots','ntt','crt','carry'))
    return label+' '+' '.join(k+'='+str(row[k]) for k in f.FIELDS)


class FusionFaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload,cls.info=f.directed_case('step-domain')
        cls.metric=example_metric(cls.info['label'],cls.info['base'])

    def test_single_reversible_mutation_and_frozen_identity(self):
        source=(ROOT/f.ROM).read_text()
        for name,(old,new) in f.MUTATIONS.items():
            altered=f.mutation(source,name)
            self.assertEqual(altered.replace(new,old),source)
            self.assertEqual(altered.count(new),1)
            self.assertNotEqual(f.digest(altered.encode()),f.ROM_SHA)
        with self.assertRaises(ValueError):f.mutation(source+'\n','seed-domain')
        with self.assertRaises(ValueError):f.mutation(source,'unrelated')

    def test_step_mutation_keeps_post_step_and_seeds(self):
        source=(ROOT/f.ROM).read_text();changed=f.mutation(source,'step-domain')
        self.assertIn("key==0 ? R2 : R",changed)
        self.assertIn('factor=key==0 ? R2 : IN;',changed)
        # Select expression keeps phase3 multiplier in Montgomery radix R.
        for p,g in ((104857601,3),(69206017,5),(67239937,10)):
            r=(1<<32)%p;r2=r*r%p;psi=pow(g,(p-1)//131072,p)
            for key in (0,33):
                alpha=psi if key==0 else pow(psi,-1,p)
                old_step=pow(alpha,256,p)*r%p
                altered_step=pow(alpha,256,p)*(r2 if key==0 else r)%p
                self.assertEqual(old_step==altered_step,key!=0)
        self.assertEqual(changed.replace(f.MUTATIONS['step-domain'][1],f.MUTATIONS['step-domain'][0]),source)

    def test_root_feedback_witness_all_three_fields(self):
        for name,index in (('seed-domain',0),('step-domain',256)):
            rows=f.root_witnesses(name);self.assertEqual(len(rows),3)
            for row in rows:
                self.assertEqual(row['index'],index)
                self.assertNotEqual(row['correct'],row['mutant'])
                self.assertTrue(0<=row['correct']<row['p'] and 0<=row['mutant']<row['p'])

    def test_one_directed_cold_square_full_readback(self):
        self.assertEqual(len(self.payload.splitlines()),5)
        self.assertNotIn(b'RUN_NOREAD',self.payload);self.assertNotIn(b'LOAD_KEEP',self.payload)
        self.assertEqual(len(self.info['expected']),65536)
        self.assertEqual(self.info['input_index'],256)
        self.assertEqual(self.info['expected'][512],1)

    def test_both_directed_wrong_coefficients_are_bounded(self):
        for name,wanted in (('seed-domain',41972152391961575983),('step-domain',18446744073709551616)):
            payload,info=f.directed_case(name)
            self.assertEqual(info['wrong_centered_coefficient'],wanted)
            self.assertLess(wanted,1<<66)
            self.assertLess(2*wanted,info['crt_modulus'])
            self.assertLess(wanted,2*65536*999999999**2)
            self.assertEqual(info['wrong_first_digit'],wanted%1000000000)
            self.assertNotEqual(info['wrong_first_digit'],info['expected'][info['coefficient_index']])

    def test_directed_integer_oracle_is_not_RNS_dependent(self):
        for name in f.MUTATIONS:
            payload,info=f.directed_case(name);lines=payload.decode().splitlines()
            digits=list(map(int,lines[2].split()));expected=list(map(int,lines[4].split()))
            # Closed-form impulse square, independent of the block packer.
            nonzero=[(i,d) for i,d in enumerate(digits) if d]
            self.assertEqual(nonzero,[(info['input_index'],info['input_digit'])])
            self.assertEqual([(i,d) for i,d in enumerate(expected) if d],
                             [(2*info['input_index'],info['input_digit']**2)])

    def test_positive_requires_all65536_readback_and_exact_metric(self):
        text=self.metric+'\nPASS n=65536 squares=1 readbacks=1 aborts=0\n'
        row=f.parse_metric(example_metric('original-random',604832956))
        self.assertEqual(f.check_positive(0,text,self.info,row),self.metric)
        for rc,wrong in ((1,text),(0,text.replace('readbacks=1','readbacks=0')),(0,text.replace('conversion=4102','conversion=4105'))):
            with self.assertRaises(ValueError):f.check_positive(rc,wrong,self.info,row)

    def test_only_exact_wrong_word_is_accepted(self):
        bad=self.metric+'\nsquare mismatch fusion-step-domain-impulse index=512 got_low=709551616 expected=1\n'
        self.assertTrue(f.expected_rejection(1,bad,self.info,self.metric))
        for rc,wrong in ((True,bad),(False,bad),(0,bad),(-6,bad),(137,bad),(1,bad.replace('got_low=709551616','got_low=1')),
                         (1,bad.replace('got_low=709551616','got_low=3')),
                         (1,bad.replace('expected=1','expected=9')),(1,bad.replace('index=512','index=65536')),
                         (1,bad.replace('fusion-step-domain-impulse index','other index')),(1,bad+'PASS n=65536\n'),
                         (1,bad.replace('conversion=4102','conversion=4105'))):
            self.assertFalse(f.expected_rejection(rc,wrong,self.info,self.metric))

    def test_resource_completion_assertion_failures_inconclusive(self):
        for text in ('completion mismatch first-s0-d0 cycles=123\n','std::bad_alloc\n',
                     '%Fatal: coefficient outside bound\n','command timeout\n',
                     'Aborted\n','Segmentation fault\n'):
            self.assertFalse(f.expected_rejection(1,text,self.info,self.metric))

    def test_static_runner_guards_and_no_parallel_fault_forest(self):
        source=(ROOT/'tools/run_prefetch_r2_faults.py').read_text();ast.parse(source)
        for contract in ("socket.gethostname()=='aethia'","limits['affinity']==[0,2]",
                         'resource.RLIMIT_AS,(6*GiB,6*GiB)',"'-j','2','--threads','1'",
                         "with LOCK.open('r')",'32*MiB-allocated(out)',"payload,info=directed_case(name)",
                         "run('fresh-control'","run('build-mutant'",'expected_rejection(rc,text,info,metric)'):
            self.assertIn(contract,source)
        self.assertLess(source.index("run('fresh-control'"),source.index("run('build-mutant'"))
        self.assertEqual(source.count("run('build-mutant'"),1)
        self.assertNotIn('ThreadPoolExecutor',source)

    def test_allocation_scan_tolerates_disappearing_compiler_temp(self):
        class Stat:
            st_blocks=7
        with patch.object(f.os,'walk',return_value=[('/scratch',[],['gone','retained'])]), \
             patch.object(Path,'lstat',side_effect=[FileNotFoundError('unlinked'),Stat()]):
            self.assertEqual(f.allocated(Path('/scratch')),7*512)


if __name__=='__main__':unittest.main()
