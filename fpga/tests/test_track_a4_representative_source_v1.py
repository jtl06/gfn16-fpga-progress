import unittest
from fpga.reference.track_a4_representative_source_v1 import verify
from fpga.reference.track_a4_representative_recipe_v1 import geometry
from fpga.reference.track_a4_representative_output_v1 import parse


class RepresentativeSourceTests(unittest.TestCase):
    def test_exact_delta(self):self.assertEqual(verify()['rtl_changes'],0)

    def test_parser_fulln_scalar_events(self):
        g=geometry(16);rows=[]
        for r in g['identities']:
            root=8743*r['load'];total=root+20558+4162+4108*r['cold']
            rows.append(f'A4_CORE_SQUARE index={r["index"]} cold={r["cold"]} load={r["load"]} double={r["double"]} latency={total+2} total={total} prefill={4106*r["cold"]} root={root} ntt=20558 post=4158 seed=1')
        rows.append('A4_CORE_PASS aw=16 commands=786452 squares=16 cold_squares=8 profile_loads=4 readbacks=524288 hold_checks=1572904 ticks=10000000 max_latency=37573')
        text='\n'.join(rows)+'\n'
        self.assertTrue(parse(text,16)['source_schedule_hypotheses_match'])
        for mutant in (text+'junk\n',text.replace('post=4158','post=4159',1),text.replace('squares=16','squares=15'),text.replace('load=1','load=0',1)):
            with self.assertRaises(ValueError):parse(mutant,16)


if __name__=='__main__':unittest.main()
