from dataclasses import replace
import unittest

from fpga.host.r15_arithmetic import HostFault
from fpga.host.r15_link_adapter import CoreSnapshot, TransactionPlan
from fpga.reference.stream27_r15_host_link_model_v1 import decode_word, LinkFault
from fpga.reference.stream27_r15_host_mmio_v1 import REG, CMD_START


class Adapter(unittest.TestCase):
    def plan(self):
        snap=CoreSnapshot(4,1,65534,1,True)
        return TransactionPlan(256,1000000,1000,3,0,snap,enabled=True)

    def test_core_generation_not_double_incremented(self):
        plan=self.plan()
        self.assertEqual(plan.header.generation,1)
        self.assertEqual(plan.header.owner,(999 << 24)|(997 << 8)|1)
        writes=dict(plan.begin_writes())
        self.assertEqual(writes[REG['GENERATION']],1)
        self.assertNotIn(REG['NEXT_GENERATION'],writes)
        for i in range(6):self.assertEqual(writes[REG[f'RESERVED_SETUP{i}']],0)

    def test_coherence_and_generation_exhaustion(self):
        snap=CoreSnapshot(4,1,65534,1,False)
        with self.assertRaisesRegex(HostFault,'SNAPSHOT'):
            TransactionPlan(256,1000000,1,0,0,snap,enabled=True)
        with self.assertRaisesRegex(LinkFault,'GEN_EXHAUSTED'):
            TransactionPlan(256,1000000,1,0,0,replace(snap,prospective_generation=256,
                                                    fenced_acknowledgement=True),enabled=True)

    def test_every_wire_record_carries_old_session_and_full_owner(self):
        plan=self.plan()
        records=list(plan.data_records(9,[-1]+[0]*255,[0]*16,[0]*16))
        self.assertEqual(len(records),288)
        for index,raw in enumerate(records):
            word=decode_word(raw)
            self.assertEqual((word.session,word.lease,word.context,word.owner,word.index),
                             (4,9,1,plan.header.owner,index))
        self.assertEqual(decode_word(records[0]).value,0xffffffff)

    def test_destination_ack_and_start_are_separate(self):
        plan=self.plan()
        with self.assertRaisesRegex(HostFault,'ACK'):
            plan.commit_plan(9,accepted=288,applied=287,coherent_idle_ack=True)
        self.assertEqual(plan.commit_plan(9,accepted=288,applied=288,coherent_idle_ack=True)[-1],
                         (REG['COMMAND'],2))
        self.assertEqual(plan.start_plan(committed_header=plan.header,context_still_idle=True)[-1],
                         (REG['COMMAND'],CMD_START))
        with self.assertRaises(HostFault):
            plan.start_plan(committed_header=replace(plan.header,count=999),context_still_idle=True)


if __name__=='__main__':unittest.main()
