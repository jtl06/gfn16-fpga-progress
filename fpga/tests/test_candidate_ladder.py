"""Actual source templates, no native/math/provider execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import candidate_ladder as ladder

MANIFEST=ladder.ROOT/'results/throughput-20260929/s4-canonical-pipe-aw5-p8-normal-v2/input/manifest.json'
SOURCE=MANIFEST.parent/'source/fpga'


class LadderTests(unittest.TestCase):
    def descriptor(self):
        return dict(schema='gfn16-candidate-ladder-v1',candidate_id='real-canonical-pipe',owner='stream-core',track='S',
            flags=dict(CANONICAL_PIPE_STAGES=1),roles=[dict(id='thin-ladder-aw5-normal',stage='aw5',test_role='normal',
                manifest=dict(path=str(MANIFEST),sha256=ladder.queue.sha(MANIFEST)),source_root=str(SOURCE),after=[])])

    def plan(self,value):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'candidate.json';path.write_text(json.dumps(value))
            return ladder.plan(path)

    def test_real_source_role_without_new_faults_is_ready(self):
        value,roles=self.plan(self.descriptor())
        self.assertEqual(len(roles),1)
        self.assertEqual(roles[0][0]['test_role'],'normal')
        self.assertNotIn('typed_mutant',{row[0]['stage'] for row in roles})

    def test_unsupported_flag_or_missing_contract_does_not_create_fake_pass(self):
        for change in ('unknown','boolean','wrong_pin','missing_role','bad_stage'):
            value=self.descriptor()
            if change=='unknown':value['flags']={'UNIMPLEMENTED_TRUNK':1}
            elif change=='boolean':value['flags']['CANONICAL_PIPE_STAGES']=True
            elif change=='wrong_pin':value['roles'][0]['manifest']['sha256']='0'*64
            elif change=='missing_role':value['roles']=[]
            else:value['roles'][0]['stage']='placeholder'
            with self.subTest(change=change),self.assertRaises(ValueError):self.plan(value)

    def test_mutants_fanout_only_on_declared_data_dependencies(self):
        value=self.descriptor();normal=value['roles'][0]
        for n in range(2):
            row=copy.deepcopy(normal);row.update(id='thin-mutant-'+str(n),stage='typed_mutant',test_role='deliberate_fault',after=['real-native-parent'])
            value['roles'].append(row)
        real=json.loads(MANIFEST.read_text());fault=copy.deepcopy(real);fault['steps'][0]['expected_returncode']=1
        with patch.object(ladder,'read_reference',side_effect=[(MANIFEST,real),(MANIFEST,fault),(MANIFEST,fault)]):
            _,roles=self.plan(value)
        self.assertEqual([row[0]['after'] for row in roles[1:]],[['real-native-parent'],['real-native-parent']])

    def test_cli_flag_must_equal_owner_bound_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'candidate.json';path.write_text(json.dumps(self.descriptor()))
            with self.assertRaisesRegex(ValueError,'CLI flags equal'):ladder.plan(path,{'CANONICAL_PIPE_STAGES':0})

    def test_packaging_quote_is_cached_not_a_new_provider_call(self):
        with patch.object(ladder.queue,'hourly_provider',side_effect=AssertionError('no new cost evaluation')):
            value=ladder.budget_from_hourly()
        self.assertEqual(value['provider'],'gcp');self.assertEqual(value['total_allowance_usd'],100)

    def test_real_closed_p16_localbase_ladder_and_flag_refusals(self):
        path=ladder.ROOT/'results/throughput-20260929/s4-p16-timing7-qualification-ladder-v1/candidate.json'
        value,roles=ladder.plan(path)
        self.assertEqual(len(roles),3)
        self.assertTrue(all(x[3]['build']['parameters']['CANONICAL_LOCALBASE']==1 for x in roles))
        self.assertTrue(all(ladder.LOCALBASE in {Path(n).name for n in x[3]['build']['sv_sources']} for x in roles))
        selected=copy.deepcopy(value);selected['roles']=selected['roles'][:1]
        manifest_path,original=ladder.read_reference(selected['roles'][0]['manifest'])
        for change in ('off','boolean','missing_pipe_flag','wrong_leaf'):
            changed=copy.deepcopy(original)
            if change=='off':changed['build']['parameters']['CANONICAL_LOCALBASE']=0
            elif change=='boolean':changed['build']['parameters']['CANONICAL_LOCALBASE']=True
            elif change=='missing_pipe_flag':changed['build']['parameters'].pop('CANONICAL_PIPE_STAGES')
            else:changed['build']['sv_sources']=[n for n in changed['build']['sv_sources'] if Path(n).name!=ladder.LOCALBASE]
            with self.subTest(change=change),patch.object(ladder,'read_reference',return_value=(manifest_path,changed)),self.assertRaises(ValueError):
                self.plan(selected)


if __name__=='__main__':unittest.main()
