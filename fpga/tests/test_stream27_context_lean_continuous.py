import ast
import copy
import json
import math
import re
import unittest
from fpga.reference import stream27_context_lean_continuous as own


class LeanContinuousTests(unittest.TestCase):
    def test_only_count_bits_compiled_delta_and_raw_forecast(self):
        manifest, files = own.role()
        original = own.read(own.PILOT_DIR/'manifest.json')
        compiled = set(manifest['build']['sv_sources']) | {own.pilot.CPP}
        self.assertEqual(manifest['build'], original['build'])
        self.assertTrue(all(manifest['sources'][name] == original['sources'][name] for name in compiled))
        self.assertNotEqual(manifest['sources'][own.pilot.HEADER], original['sources'][own.pilot.HEADER])
        self.assertEqual(manifest['steps'][0]['validator']['config']['parent_config'], own.config())
        self.assertEqual(own.bits()[0][:100], own.bits(100)[0])
        result = own.forecast(manifest)
        self.assertAlmostEqual(result['forecast']['continuous_command_seconds_estimate'],4351.536746164893)
        self.assertAlmostEqual(result['forecast']['overall_seconds_estimate'],5273.7996400234115)
        self.assertFalse(result['host_gl_implemented'])
        self.assertFalse(result['promotion_allowed'])
        self.assertEqual(files[own.pilot.CPP], (own.PILOT_DIR/'source/fpga'/own.pilot.CPP).read_bytes())

    def test_four_scalar_ast_abi_and_negative_bounds(self):
        tree = ast.parse((own.ROOT/own.SELF).read_text())
        nodes = [node for node in tree.body if isinstance(node,ast.FunctionDef)
                 and node.name in ('bits','config','header','predict')]
        self.assertEqual(len(nodes),4)
        namespace = dict(COUNT=1000,THREADS=1,BASES=[604832956,999999937],SHAPE=copy.deepcopy(own.SHAPE),
                         need=own.need,math=math,re=re)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'[own scalar functions]','exec'),namespace)
        self.assertEqual(namespace['config'](),own.config())
        self.assertEqual(namespace['predict'](248.65924263799388,432.80946770000446),
                         own.predict(248.65924263799388,432.80946770000446))
        raw = (own.PILOT_DIR/'source/fpga'/own.pilot.HEADER).read_bytes()
        self.assertEqual(namespace['header'](raw),own.header(raw))
        with self.assertRaisesRegex(ValueError,'COUNT100'):
            own.header(raw.replace(b'COUNT=100,INTERVAL=8459',b'COUNT=100,INTERVAL=8460'))
        for value in (True,float('nan'),float('inf'),0,-1):
            with self.assertRaisesRegex(ValueError,'FINITE_MEASURED'):
                own.predict(value,500)
        for margin,reserve in ((1.74,600),(1.75,599)):
            with self.assertRaisesRegex(ValueError,'FINITE_MEASURED'):
                own.predict(250,500,margin,reserve)


if __name__ == '__main__':
    unittest.main()
