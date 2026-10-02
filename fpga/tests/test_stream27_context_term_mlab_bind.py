import unittest
from fpga.reference import stream27_context_term_mlab_bind as mlab


class TermMlabBindTests(unittest.TestCase):
    def parent(self,stage):
        _,_,bundle=mlab.captured.capture(stage)
        return mlab.captured.binder.bind(bundle,enabled=1)

    def test_default_exact_both_captures(self):
        for stage in ('aw8','full'):
            p=self.parent(stage);self.assertEqual(mlab.bind(p),p)

    def test_actual_data_only_seam_and_unchanged_checks(self):
        p=self.parent('aw8');c=mlab.bind(p,enabled=1);s=c['files'][mlab.NEW+'.sv']
        self.assertEqual(len(c['files']),54)
        self.assertIn('current_term=payload_read;',s)
        self.assertIn('if(bypass)begin current_term=product_data;consumer_missing=1',s)
        self.assertIn('product_owner_bad=product_slot && bank_owner[prod_bank]!=product_owner',s)
        self.assertIn('context_row[prod_bank][product_row[1:0]]<=product_row',s)
        self.assertIn('!stop && product_slot && bank_owner[prod_bank]==product_owner',s)
        self.assertFalse(c['term_mlab']['no_rw_check'])
        self.assertEqual(c['term_mlab']['extra_read_registers'],0)
        for field in range(3):
            old=next(s for k,s in p['files'].items() if '_f'+str(field)+'_' in k and k.endswith('_storage2_v1.sv'))
            new=next(s for k,s in c['files'].items() if '_f'+str(field)+'_' in k and k.endswith('_term_mlab_v1.sv'))
            self.assertEqual(old.count('A_table['),new.count('A_table['))
            self.assertEqual(old.count('B_table['),new.count('B_table['))

    def test_no_payload_reset_rw_waiver_or_unbound_parent(self):
        p=self.parent('full')
        ram=(mlab.ROOT/'rtl/kernel'/ (mlab.RAM+'.sv')).read_text()
        self.assertNotIn('rst_n',ram);self.assertNotIn('no_rw_check',ram.split('module',1)[1])
        self.assertIn('assign read_data=memory[read_address]',ram)
        for value in (True,2,-1):
            with self.assertRaises(ValueError):mlab.bind(p,enabled=value)
        p['files'][mlab.TERM+'.sv']+='\n'
        with self.assertRaises(ValueError):mlab.bind(p,enabled=1)


if __name__=='__main__':unittest.main()
