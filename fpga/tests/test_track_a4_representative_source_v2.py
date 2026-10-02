import unittest
from fpga.reference.track_a4_representative_source_v2 import ROOT,verify
from fpga.reference.track_a4_representative_output_v2 import parse

class RepresentativeV4Tests(unittest.TestCase):
    def test_exact_unchanged_recipe_harness(self):
        result=verify()
        self.assertFalse(result['arithmetic_or_recipe_change'])
        self.assertEqual(result['model_threads'],1)

    def test_old_measured_metrics_rejected_plus_one_prediction_accepted(self):
        directory=ROOT/'results/throughput-20260929/track-a4-core-v3-representative-aw16-aethia-v1'
        logs=[p for p in directory.glob('*.log') if p.read_text().startswith('A4_CORE_SQUARE')]
        self.assertEqual(len(logs),1);raw=logs[0].read_text()
        with self.assertRaises(ValueError):parse(raw,16)
        lines=[]
        for line in raw.splitlines():
            words=line.split();values=dict(v.split('=') for v in words[1:])
            for key in (('latency','total') if words[0]=='A4_CORE_SQUARE' else ('ticks','max_latency')):
                values[key]=str(int(values[key])+(16 if key=='ticks' else 1))
            lines.append(words[0]+' '+' '.join(k+'='+v for k,v in values.items()))
        hypothetical='\n'.join(lines)+'\n';result=parse(hypothetical,16)
        self.assertTrue(result['source_schedule_hypotheses_match'])
        for changed in (hypothetical+hypothetical,hypothetical.replace('ntt=20558','ntt=20559',1),hypothetical.replace('post=4158','post=4159',1)):
            with self.assertRaises(ValueError):parse(changed,16)

if __name__=='__main__':unittest.main()
