import unittest
from fpga.reference import stream27_host_core_v1 as host
from fpga.reference import stream27_shared_field_v2 as frozen


class HostCoreSource(unittest.TestCase):
    def test_composes_actual_closed_modules_and_preserves_arithmetic(self):
        b=host.prepare(32,paired=True)
        self.assertEqual(b['parameters'],dict(AW=5,P=16,CONTEXTS=1))
        self.assertEqual(b['files']['genefer_stream27_host_image_ports_v1.sv'],(host.ROOT/host.HOST).read_text())
        self.assertEqual(len([x for x in b['files'] if x.endswith('_signed_host_v3.sv')]),3)
        self.assertIn('module '+b['top'],b['files'][b['top']+'.sv'])
        for field in range(3):
            old=frozen.prepare(32,16,field)
            for name,text in old['files'].items():
                if name!=old['top']+'.sv':self.assertEqual(b['files'][name],text)

    def test_real_storage_and_source_visible_host_completion(self):
        b=host.prepare(256);s=b['files'][b['top']+'.sv']
        self.assertIn('.commit_we(copy_fire)',s)
        self.assertIn('COPY_DRAIN:begin state<=IDLE;done<=1;',s)
        self.assertIn('host_access(state==IDLE && !start && !error)',s)
        self.assertIn('child_read_data[95:32]!={64{child_read_data[31]}}',s)
        self.assertEqual(b['host_contract']['extra_shadow_bits'],8192)
        self.assertIn('NOT full long PRP',b['host_contract']['batch'])

    def test_event_cost_separates_legacy_and_batch(self):
        b=host.prepare(32);g=b['geometry']
        self.assertEqual(host.cycle_contract(32,g)['host_done'],458)
        self.assertEqual(host.cycle_contract(32,g,cache_hit=True)['host_done'],359)
        self.assertEqual(host.cycle_contract(32,g,count=4)['host_done'],836)
        self.assertEqual(host.cycle_contract(32,g,special=True)['host_done'],490)
        self.assertEqual(host.cycle_contract(32,g)['canonical_done_to_host_done'],36)
        for n in (32,256):
            b=host.prepare(n)
            for count in (1,2,4,32):
                for hit in (False,True):
                    normal=host.cycle_contract(n,b['geometry'],count=count,cache_hit=hit)
                    special=host.cycle_contract(n,b['geometry'],count=count,cache_hit=hit,special=True)
                    self.assertEqual(special['host_done']-normal['host_done'],n)
                    self.assertEqual(normal['host_done']-normal['canonical_done'],n+4)

    def test_hooks_fail_closed_not_smaller_core(self):
        with self.assertRaisesRegex(ValueError,'P8_CARRY'):host.prepare(32,8)
        with self.assertRaisesRegex(ValueError,'CONTEXTS2'):host.prepare(32,contexts=2)
        with self.assertRaisesRegex(ValueError,'FINITE_COUNT'):host.cycle_contract(32,{},count=33)


if __name__=='__main__':unittest.main()
