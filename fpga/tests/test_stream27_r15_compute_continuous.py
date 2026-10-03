import unittest
from fpga.reference import stream27_r15_compute_continuous as p


class Continuous(unittest.TestCase):
    def test_header_config_and_forecast_scalar(self):
        m,f=p.role()
        self.assertEqual(p.config()['count'],1000)
        self.assertEqual(p.config()['doubles'],1022)
        self.assertEqual(p.config()['r15_flags']['LEAN_BUILD'],1)
        result=p.predict(246.089767281,458.069481439)
        self.assertTrue(result['fits_finite_shape'])
        self.assertEqual(result['operation_ratio'],10)
        with self.assertRaises(ValueError):p.predict(2,1)
        with self.assertRaises(ValueError):p.predict(1,2,margin=1)


if __name__=='__main__':unittest.main()
