import copy
import json
from pathlib import Path
import unittest
from fpga.tools import native_profile_variants_v7 as old
from fpga.tools import native_profile_variants_v8 as new

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/throughput-20260929/threaded-long-package-v1'


def packet(path):
    return dict(manifest=json.loads((path/'manifest.json').read_text()),budget=json.loads((path/'ticket.json').read_text())['budget'],source_root=path/'capture/source/fpga')


class MeasuredLongVariantTests(unittest.TestCase):
    def test_actual_fresh_budget_only_variant_matches(self):
        values=[packet(DATA/name) for name in ('packet-v2','packet-v3')]
        with self.assertRaisesRegex(ValueError,'exact finite outer'):old.functional_fingerprint(**values[0])
        result=new.match_variants(values)
        self.assertEqual(result['functional_sha256'],'f4482042e7831a6ab778bd925475558bff0c79a88f4b6b3b74bb7ea5fd35c8c5')
        self.assertFalse(result['fresh_budget_admission_conferred'])
        self.assertEqual(result['variants'][0]['identity']['runtime_duration'],values[0]['manifest']['runtime_duration'])

    def test_exact_family_resource_and_budget_negatives(self):
        for kind in ('runner','runtime','policy','host','profile','threads','shape','window','source','provider'):
            v=packet(DATA/'packet-v3');m=v['manifest'];b=v['budget']
            if kind in ('runner','runtime','policy'):m['sources'][list(new.FAMILY)[('runner','runtime','policy').index(kind)]]='0'*64
            elif kind=='host':m['host']='gfn16-pilot-c4d'
            elif kind=='profile':m['cpu_profile']='azure-burst16-static01-v1'
            elif kind=='threads':m['build']['runtime_threads']=1
            elif kind=='shape':m['runtime_duration']['shape']['outer_seconds']=6000
            elif kind=='window':b['max_seconds']=3715
            elif kind=='source':b['source_sha256']='0'*64
            else:b['provider']='gcp'
            with self.subTest(kind=kind),self.assertRaises(ValueError):new.functional_fingerprint(**v)

    def test_serial_long_and_ordinary_identity_unchanged(self):
        for path in (ROOT/'results/throughput-20260929/native-long-duration-v3/t5b-packet01',ROOT/'artifacts/soak-t5b-thread100-burst23-v1'):
            v=packet(path);self.assertEqual(new.functional_fingerprint(**v),old.functional_fingerprint(**v))

    def test_role_and_proof_remain_identity_not_broad_exclusions(self):
        original=packet(DATA/'packet-v3');baseline=new.functional_fingerprint(**original)['sha256']
        altered=copy.deepcopy(original);altered['manifest']['runtime_duration']['contract_sha256']='0'*64
        self.assertNotEqual(new.functional_fingerprint(**altered)['sha256'],baseline)
        self.assertIn('long-duration/forecast.json',new.functional_fingerprint(**original)['identity']['sources'])


if __name__=='__main__':unittest.main()
