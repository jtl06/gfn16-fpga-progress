"""Pure bounded/source/typed pilot tests; no HDL/ELF/fullN arithmetic."""
import unittest
from fpga.reference import stream27_host_chain_full_pilot_v1 as pilot


class PilotTests(unittest.TestCase):
    def test_exact_reversible_source_delta(self):
        pilot.verify();delta=pilot.source_delta()
        self.assertEqual(delta['reverse_anchors'],15)
        self.assertTrue(delta['independent_reference_unchanged'])
        self.assertEqual(len(pilot.BITS),24)
        self.assertEqual(pilot.BITS,pilot.BITS[:8]*3)

    def test_independent_fifo_ledger(self):
        row=pilot.fifo_ledger();counts=pilot.counts()
        self.assertEqual((row['pushes'],row['pops'],row['peak']), (23,23,4))
        self.assertEqual(row['full_exchanges'],19)
        self.assertEqual(row['backpressure_edges'],316387)
        self.assertEqual(row['full_exchanges'],counts['full_exchanges'])
        self.assertEqual(row['backpressure_edges'],counts['backpressure_edges'])
        self.assertEqual(row['accept_edges'][:4],[1,2,3,4])
        self.assertEqual(row['pop_edges'],[3+index*16653 for index in range(1,24)])
        self.assertEqual(row['accept_edges'][4:],row['pop_edges'][:19])

    def test_exact_cycle_and_final_word_counts(self):
        self.assertEqual(pilot.counts(),dict(jobs=2,operations=25,feed_descriptors=23,true_final_rows=16384,
            paired_reads=131072,copied_words=131072,partial_reads=1,canonical_cycles=786432,
            image_copy_cycles=131078,candidate_cycles=1350334,fifo_peak=4,full_exchanges=19,
            backpressure_edges=316387))
        feed_done=3+23*16653+24847+2+6*65536+65536+4
        self.assertEqual(feed_done,866627)
        self.assertEqual(483707+feed_done,1350334)

    def footer(self):
        return pilot.footer_prefix()+'750000'+''.join(' '+key+'='+str(100+index*1000)
            for index,key in enumerate(pilot.WALL_KEYS))+'\n'

    def test_exact_typed_positive_and_phase_schema(self):
        config=dict(aw=16,p=8,mode='normal');footer=self.footer()
        result=pilot.validate(footer,'',0,config,{})
        self.assertEqual(list(result['measured_simulator_wall_ms']),list(pilot.WALL_KEYS))
        for key,value in pilot.counts().items():
            with self.assertRaises(ValueError):
                pilot.validate(footer.replace(f'{key}={value}',f'{key}={value+1}',1),'',0,config,{})
        for key in pilot.WALL_KEYS:
            fragment=next(word for word in footer.split() if word.startswith(key+'='))
            for new in (key+'=01',key+'=-1',key+'=1800001',key+'=NaN',key+'=1.5',key+'='):
                with self.assertRaises(ValueError):pilot.validate(footer.replace(fragment,new),'',0,config,{})
            with self.assertRaises(ValueError):pilot.validate(footer.replace(' '+fragment,''),'',0,config,{})
        for bad in ('extra\n'+footer,footer+'extra\n',footer.replace('p=8','p=16'),footer.replace('750000','0750000'),
                    footer.replace('750000','24'),footer.replace('750000',str(25*(20*65536+100000)+1)),footer.rstrip()):
            with self.assertRaises(ValueError):pilot.validate(bad,'',0,config,{})
        with self.assertRaises(ValueError):pilot.validate(footer,'incidental\n',0,config,{})
        with self.assertRaises(ValueError):pilot.validate(footer,'',True,config,{})

    def test_exact_typed_firstword_negative(self):
        config=dict(aw=16,p=8,mode='oracle');pilot.validate('',pilot.NEGATIVE,1,config,{})
        for out,err,code in [(self.footer(),pilot.NEGATIVE,1),('',pilot.NEGATIVE,0),
                             ('',pilot.parent.NEGATIVE,1),('',pilot.NEGATIVE.replace('P8','P16'),1)]:
            with self.assertRaises(ValueError):pilot.validate(out,err,code,config,{})
        for bad in (dict(config,aw=8),dict(config,p=16),dict(config,aw=True),dict(config,unexpected=1)):
            with self.assertRaises(ValueError):pilot.validate('',pilot.NEGATIVE,1,bad,{})


if __name__=='__main__':unittest.main()
