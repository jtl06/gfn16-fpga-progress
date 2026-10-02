import unittest
from fpga.reference import stream27_shared_field_v5 as candidate


class SerialCorrectionBinding(unittest.TestCase):
    def test_default_frozen_and_transform_identity(self):
        for n,p in ((32,8),(32,16),(256,8),(256,16)):
            a=candidate.parent.prepare(n,p,0,mode='warm_signed')
            self.assertEqual(a,candidate.prepare(n,p,0,mode='warm_signed'))
            b=candidate.prepare(n,p,0,mode='warm_signed',corr_serial_bfs=2)
            changed=[name for name in a['files'] if b['files'].get(name)!=a['files'][name]]
            self.assertEqual(len(changed),2)
            s=b['files'][b['top']+'.sv']
            self.assertIn('CORR_SERIAL_BFS=2',s)
            self.assertIn('.frame_start(digit_slot && launch_tag[ROW_W])',s)
            self.assertIn(f".POINTWISE_FIRST({b['geometry']['pointwise_accept']})",s)
            self.assertGreaterEqual(b['geometry']['initial_latest_correction'],0)

    def test_all_scalar_calendars(self):
        for aw in range(5,17):
            for p in (8,16):
                g=candidate.geometry(1<<aw,p,corr_serial_bfs=2)
                self.assertGreaterEqual(g['cache_margin'],0)
                self.assertGreaterEqual(g['pointwise_accept'],g['correction_cache_latency']+1)
        for p,interval,latency,margin in ((8,16653,51,58),(16,8459,77,31)):
            g=candidate.geometry(65536,p,corr_serial_bfs=2)
            self.assertEqual((g['warm_interval'],g['correction_cache_latency'],g['cache_margin']),(interval,latency,margin))
            self.assertEqual(g['input_delay'],0)
        self.assertGreater(candidate.geometry(256,16,corr_serial_bfs=2)['input_delay'],0)
        for bad in (1,3,True):
            with self.assertRaises(ValueError):candidate.prepare(corr_serial_bfs=bad)


if __name__=='__main__':unittest.main()
