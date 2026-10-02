"""Source-only AW16 normal adapter tests; never HDL/native/cloud dispatch."""
import hashlib
import json
from pathlib import Path
import unittest
from fpga.reference import core27_prefill_aw16_structure as structure
from fpga.reference import core27_prefill_aw16_regression as gate

ROOT=Path(__file__).resolve().parents[1]


def fixture(parent):
    lines=[]
    for old in parent['metrics']:
        fast=int(old['case'].startswith('no-host') and old['profile_before']==1)
        row={k:v for k,v in old.items() if k not in ('case','aw','n')}
        row['carry']+=5;row['conversion']=0 if fast else 4102
        row['cycles']+=5-(4102 if fast else 0)
        row.update(prefill_before=fast,prefill_after=1)
        lines.append(old['case']+' '+' '.join(f'{k}={v}' for k,v in row.items()))
    return '\n'.join(lines+['PASS n=65536 squares=12 readbacks=10 aborts=0'])


class AW16PreparationTests(unittest.TestCase):
    def setUp(self):self.parent=json.loads((ROOT/structure.PARENT_REPORT).read_text())

    def test_mechanical_ancestor_identity(self):
        self.assertEqual(structure.validate(ROOT)['aw'],16)
        self.assertEqual(hashlib.sha256((ROOT/structure.ANCESTOR).read_bytes()).hexdigest(),structure.ANCESTOR_SHA)
        self.assertEqual(gate.NORMAL_REPORT_SHA,structure.PARENT_SHA)

    def test_normal_only_command_and_closure(self):
        self.assertEqual(gate.GROUPS,('normal',))
        self.assertEqual(len(gate.compiled(ROOT,'normal')),17)
        self.assertEqual(gate.commands('/exe','/vector','normal'),[('normal',['/exe','/vector','profile'])])
        for invalid in ('reset-tail','base-change','mutant','host-error-tail'):
            with self.assertRaises(ValueError):gate.commands('/exe','/vector',invalid)
            with self.assertRaises(ValueError):gate.compiled(ROOT,invalid)
            with self.assertRaises(ValueError):gate.top(invalid)

    def test_parent_vectors_and_phase_predictions(self):
        self.assertEqual(self.parent['vectors']['squares'],12)
        self.assertEqual(self.parent['vectors']['readbacks'],10)
        output=fixture(self.parent);rows=gate.check_normal(output,self.parent)
        self.assertEqual(len(rows),12)
        self.assertTrue(any(row['prefill_before'] for row in rows))
        for row,old in zip(rows,self.parent['metrics']):
            self.assertEqual(row['carry']-old['carry'],5)
            self.assertEqual(row['cycles']-old['cycles'],-4097 if row['prefill_before'] else 5)
        with self.assertRaises(ValueError):gate.check_normal(output.replace('carry=4152','carry=4153',1),self.parent)
        with self.assertRaises(ValueError):gate.check_normal(output.replace('conversion=4102','conversion=4101',1),self.parent)

    def test_unique_footer_rejects_wrong_counts_or_duplicates(self):
        output=fixture(self.parent)
        with self.assertRaises(ValueError):gate.check_normal(output.replace('readbacks=10 aborts=0','readbacks=9 aborts=0'),self.parent)
        with self.assertRaises(ValueError):gate.check_normal(output+'\nPASS n=65536 squares=12 readbacks=10 aborts=0',self.parent)
        with self.assertRaises(ValueError):gate.check_normal(output.replace(self.parent['metrics'][0]['case'],'wrong-case',1),self.parent)

    def test_profile_guard_fast_requires_cached_parent(self):
        output=fixture(self.parent)
        old=self.parent['metrics'][0]
        self.assertEqual(old['profile_before'],0)
        first=output.splitlines()[0].replace('prefill_before=0','prefill_before=1')
        with self.assertRaises(ValueError):gate.check_normal(first+'\n'+'\n'.join(output.splitlines()[1:]),self.parent)

    def test_limits_do_not_weaken_CPU_memory_storage_or_bootstrap(self):
        source=(ROOT/structure.CANDIDATE).read_text()
        for required in ("limits['affinity'] == [0, 2]",'6*GIB','10*GIB','2*GIB','768*MIB','64*MIB',
                         'resource.RLIMIT_CORE','resource.RLIMIT_AS','LOCK.open','os.killpg',
                         'source-only imports','pre-import drift','unlisted imported source',
                         "'-GAW=16'",'-Werror=return-type','3600, total_budget_seconds=5400'):
            self.assertIn(required,source)
        self.assertEqual(str(gate.ROOT),'/home/jtl/gfn-fpga-lab/agent-work/core27-prefill-aw16/snapshot-v1/fpga')
        self.assertNotIn('def check_target_output',source)

    def test_closed_source_inventory_and_state_mapping(self):
        pins=gate.source_pins(ROOT)
        self.assertEqual(pins[structure.PARENT_REPORT],structure.PARENT_SHA)
        self.assertIn(structure.ANCESTOR,pins)
        self.assertIn(structure.CANDIDATE,pins)
        self.assertEqual(gate.validate_observer_states(ROOT),dict(CORE_IDLE=0,CORE_CARRY_WAIT=11,CORE_PREFILL_CHECK=13,CARRY_EMIT=7))
        self.assertEqual(pins['rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill.sv'],
            'fc8f381d0db17d3c1bff9ee4b89a99878102099b2c6a404d60157ce2c6b5d6af')


if __name__=='__main__':unittest.main()
