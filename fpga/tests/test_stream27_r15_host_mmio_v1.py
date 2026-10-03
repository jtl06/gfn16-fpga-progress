import unittest
from dataclasses import replace
from fpga.reference.stream27_r15_host_mmio_v1 import Header,REG,header,register_writes,commit_writes,LinkFault


class HeaderTests(unittest.TestCase):
    def test_prospective_owner_wrap_not_old_live_owner(self):
        h=header(65536,1,1000000,1000,3,0,core_next_epoch=65534,core_job_generation=0)
        self.assertEqual(h.owner,(999<<24)|(997<<8)|1)
        writes=dict(register_writes(h,session=9))
        self.assertEqual(writes[REG['COUNT']],1000)
        for i in range(6):self.assertEqual(writes[REG[f'RESERVED_SETUP{i}']],0)
        self.assertNotIn(REG['NEXT_EPOCH'],writes)

    def test_count_mode_and_generation_refusals(self):
        for count,mode,gen in ((0,3,0),(33,1,0),(2,0,0),(1,2,0),(1,0,255)):
            with self.assertRaises(LinkFault):
                header(256,0,1000000,count,mode,0,core_next_epoch=4,core_job_generation=gen)

    def test_mutated_header_and_bad_commit_refuse(self):
        h=header(256,0,1000000,1,0,0,core_next_epoch=4,core_job_generation=2)
        with self.assertRaises(LinkFault):register_writes(replace(h,owner=h.owner+1),session=1)
        with self.assertRaises(LinkFault):commit_writes(True,1)
        self.assertEqual(commit_writes(1,2)[-1],(REG['COMMAND'],2))


if __name__=='__main__': unittest.main()
