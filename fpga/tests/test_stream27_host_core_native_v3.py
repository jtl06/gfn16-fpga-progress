import unittest
from fpga.reference import stream27_host_core_native_v1 as old
from fpga.reference import stream27_host_core_native_v3 as current


class ImmutableExpectedImages(unittest.TestCase):
    def test_actual_failure_counterexample_is_oracle_alias_not_zero_arithmetic(self):
        for n in (32,256):
            historical=old.cases(n);fixed=current.cases(n)
            self.assertEqual(historical[0]['jobs'][0]['expected'][3],7)
            self.assertEqual(fixed[0]['jobs'][0]['expected'],(0,)*n)
            self.assertEqual(historical[3]['jobs'][0]['expected'][0],1)
            self.assertEqual(fixed[3]['jobs'][0]['expected'][0],4)

    def test_later_writes_cannot_mutate_any_previous_expected(self):
        for n in (32,256):
            for case in current.cases(n):
                words=list(case['initial']);history=[]
                for job in case['jobs']:
                    snapshot=tuple(history)
                    for address,value in job['changes']:words[address]=value
                    self.assertEqual(tuple(history),snapshot)
                    self.assertIsInstance(job['expected'],tuple)
                    self.assertEqual(tuple(old.ordinary_image(words,job['base'],job['count'],job['mask'],job['twice'])),job['expected'])
                    history.append(job['expected']);words=list(job['expected'])
                    words[0]=-2 # External mutation of next working buffer cannot affect frozen expected.
                    self.assertEqual(history[-1],job['expected'])
                    words=list(job['expected'])
                    with self.assertRaises(TypeError):job['expected'][0]=99

    def test_same_commands_and_special_seam(self):
        for n in (32,256):
            before=old.cases(n);after=current.cases(n)
            for a,b in zip(before,after):
                self.assertEqual(tuple(a['initial']),b['initial'])
                for x,y in zip(a['jobs'],b['jobs']):
                    self.assertEqual({k:v for k,v in x.items() if k!='expected'},{k:v for k,v in y.items() if k!='expected'})
            self.assertEqual(after[4]['jobs'][0]['expected'],(-1,)+(0,)*(n-1))
            self.assertEqual(sum(j['count'] for c in after for j in c['jobs']),19)


if __name__=='__main__':unittest.main()
