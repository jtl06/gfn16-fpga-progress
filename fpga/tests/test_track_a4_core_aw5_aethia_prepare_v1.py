import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import track_a4_core_aw5_aethia_prepare_v1 as prepare
from fpga.reference import track_a4_core_aw5_output_v1 as output
from fpga.reference.track_a4_core_vectors_v1 import corpus
from fpga.tools import native_source_gate_v1 as policy


class CorePreparationTests(unittest.TestCase):
    def test_frozen_snapshot_matches_ticket_and_integer_corpus(self):
        with tempfile.TemporaryDirectory() as name:
            stage=Path(name).resolve()/'stage';report=prepare.prepare(stage)
            manifest=json.loads((stage/'aw5-manifest.json').read_text())
            policy.check_sources(stage/'snapshot/source/fpga',manifest['sources'])
            self.assertEqual(manifest['host'],'aethia');self.assertEqual(manifest['build']['parameters'],{'AW':5})
            self.assertEqual(len(manifest['build']['sv_sources']),29)
            self.assertIn('-DA4_CORE_AW=5',manifest['build']['cflags'])
            self.assertEqual(report['corpus']['sha256'],output.VECTOR_SHA)
            self.assertEqual(report['exact_successor_guard']['exact_successors'],4)
            self.assertEqual((stage/'snapshot/approved-manifest.json').read_bytes(),(stage/'aw5-manifest.json').read_bytes())
            self.assertNotIn('expected_stdout',manifest['steps'][0])
            with self.assertRaisesRegex(ValueError,'fresh'):prepare.prepare(stage)

    def example_output(self):
        vectors,metadata=corpus(5);rows=[]
        for index,line in enumerate(vectors.splitlines()[1:]):
            v=list(map(int,line.split()))
            if v[0]!=5:continue
            total=5+100+68+14*v[8]
            row=dict(index=index,cold=v[8],load=v[9],double=v[4],latency=total+2,total=total,prefill=12*v[8],root=5,ntt=100,post=64,seed=3)
            rows.append('A4_CORE_SQUARE '+' '.join(f'{k}={row[k]}' for k in output.FIELDS))
        rows.append('A4_CORE_PASS '+' '.join(f'{k}={v}' for k,v in dict(output.COUNTS,ticks=100000,max_latency=1000).items()))
        return vectors,'\n'.join(rows)+'\n'

    def test_strict_footer_and_ordered_operation_binding(self):
        vectors,text=self.example_output();result=output.parse(text,vectors)
        self.assertTrue(result['source_schedule_hypotheses_match']);self.assertEqual(len(result['metrics']),14)
        for altered in (text.replace('readbacks=256','readbacks=255'),text.replace('cold=1','cold=0',1),text+'extra\n',text.replace('ntt=100','ntt=-1',1)):
            with self.assertRaises(ValueError):output.parse(altered,vectors)

    def test_schedule_disagreement_is_preserved_not_relabelled(self):
        vectors,text=self.example_output();result=output.parse(text.replace('post=64','post=65',1),vectors)
        self.assertFalse(result['source_schedule_hypotheses_match'])
        self.assertEqual(result['source_schedule_discrepancies'][0]['differences']['post'],{'measured':65,'source_hypothesis':64})
        self.assertFalse(result['promotion_allowed'])


if __name__=='__main__':unittest.main()
