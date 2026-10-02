"""Synthetic parser fixtures; percentages are not FPGA measurements."""
import hashlib
import unittest
from synthesis.routing_demand import summarize


class RoutingDemandTests(unittest.TestCase):
    def test_directional_estimates_and_provenance(self):
        text=b'''Info (20215): Router estimated peak short interconnect demand : 128% of down directional wire in region X0_Y147 to X7_Y153
    Info (20265): Estimated peak short right directional wire demand : 114% in region X208_Y77 to X215_Y83
Info (20265): Estimated peak short left directional wire demand : 99.5% in region X120_Y42 to X127_Y48
'''
        r=summarize(text)
        self.assertEqual(r['source_sha256'],hashlib.sha256(text).hexdigest())
        self.assertEqual(len(r['observations']),3)
        self.assertEqual(len(r['hotspots_above_100_percent']),2)
        self.assertEqual(r['maximum_observed_estimated_percent'],128)
        self.assertEqual(r['observations'][1]['region_grid'],[208,77,215,83])
        self.assertEqual(r['observations'][1]['line'],2)
        self.assertNotIn('fmax_mhz',r)

    def test_missing_and_partial_are_unknown_not_zero(self):
        for text in (b'',b'Info (20215): Router estimated peak short interconnect demand : 128%',
                     b'Info (170143): Final routing failed'):
            r=summarize(text)
            self.assertEqual(r['status'],'no_recognized_estimates')
            self.assertIsNone(r['maximum_observed_estimated_percent'])

    def test_preserve_different_passes(self):
        line='Info (20265): Estimated peak short up directional wire demand : {}% in region X1_Y2 to X8_Y9\n'
        r=summarize((line.format(120)+line.format(98)).encode())
        self.assertEqual([r['estimated_demand_percent'] for r in r['observations']],[120,98])

    def test_reject_invalid_region(self):
        with self.assertRaises(ValueError):
            summarize(b'Info (20265): Estimated peak short up directional wire demand : 110% in region X8_Y2 to X1_Y9')


if __name__=='__main__':unittest.main()
