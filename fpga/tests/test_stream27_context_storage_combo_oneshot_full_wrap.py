"""Full geometry wrap source/parser checks only; no full-N numeric execution."""
import json
import unittest
from fpga.reference import stream27_context_storage_combo_oneshot_full_wrap as w
from fpga.reference import stream27_context_storage_combo_oneshot_native as n


class FullWrapTests(unittest.TestCase):
    def test_production_bytes_and_stateless_observer_only(self):
        original, files, production=n.role('full')
        m,new=w.role()
        observer='rtl/'+m['build']['top']+'.sv'
        self.assertEqual(len(m['build']['sv_sources']),56)
        for path in original['build']['sv_sources']:
            if path!=observer:self.assertEqual(new[path],files[path])
        self.assertNotRegex(new[observer].decode(),r'\b(always|always_ff|always_comb|initial)\b')
        cpp=new[w.CPP].decode()
        self.assertEqual(cpp.count('d.cycles='),1)
        self.assertIn('age==20000||age==20004||age==20008',cpp)
        self.assertIn('if(mask==3)wrap_tick(d,unsigned(age));else edge(d)',cpp)
        self.assertIn('R84_FULL_CONTEXT_ALONE_BIT_IDENTITY',cpp)
        self.assertIn('R6_FULL_REAL_TABLE_OWNERS',cpp)
        self.assertEqual(m['build']['parameters'],original['build']['parameters'])

    def test_exact_footer_and_frozen_validator_asset(self):
        m,files=w.role()
        assets={'frozen_normal_validator':files[w.ORIGINAL_VALIDATOR].decode()}
        v=dict(aw=16,p=16,contexts=2,bases=[604832956,999999937],squares=8,reads=393216,
            signed96=True,context_alone_bit_identical=True,independent_reference=True,interval=8459,
            pair_launch_cycles=8459,peer_live_reads=65536,model_threads=1,launches=[[204,8663],[4433,12892]],
            single_cycles=[746121,746121],joint_cycles=1405684,overlap_edges=680684,
            done_edges=[680685,1340148],warm_edges=[21221,25450],setup_edges=[99,199],
            single_first=[104,104],seconds=450.0)
        stdout='R84_C2_FULL_PASS '+json.dumps(v)+'\n'+w.FOOTER
        self.assertEqual(w.validate(stdout,'',0,m['steps'][0]['validator']['config'],assets)['status'],'PASS_expected_contracts')
        for bad in (stdout.removesuffix(w.FOOTER),stdout.replace('aliases=3','aliases=2'),stdout+'extra\n'):
            with self.assertRaises(ValueError):w.validate(bad,'',0,m['steps'][0]['validator']['config'],assets)
        with self.assertRaises(ValueError):w.validate(stdout,'',0,m['steps'][0]['validator']['config'],dict(frozen_normal_validator=assets['frozen_normal_validator']+'\n'))


if __name__=='__main__':unittest.main()
