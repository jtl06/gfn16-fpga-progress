import copy
import unittest

from fpga.host.r15_host_output import validate
from fpga.host.r15_host_selftest import run


class TypedOutput(unittest.TestCase):
    def test_source_small_output_and_bad_claims(self):
        import json
        value=run('python')
        line='R15_HOST_RESULT '+json.dumps(value)
        self.assertEqual(validate(line, require_gmp=False), value)
        with self.assertRaises(ValueError):validate(line)
        for key in ('board_executed','PrimeGrid_submission','promotion_allowed'):
            wrong=copy.deepcopy(value);wrong['scope'][key]=True
            with self.assertRaises(ValueError):
                validate('R15_HOST_RESULT '+json.dumps(wrong), require_gmp=False)
        for wrong in ('',line+'\n'+line,line[:-1]):
            with self.assertRaises(ValueError):validate(wrong, require_gmp=False)


if __name__=='__main__':unittest.main()
