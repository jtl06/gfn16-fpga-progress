import unittest
import json
from pathlib import Path
from fpga.reference import stream27_r13_floorplan_settings as s


class R13FloorplanSettingsTests(unittest.TestCase):
    def test_actual_current_protected_field100_is_not_R13(self):
        root=Path(s.__file__).resolve().parents[1]
        d=s.source_hierarchy(root/'results/throughput-20260929/trackS-c2-protected-field100-physical-v1/physical-12000-v3/project')
        self.assertEqual(d['production_sv_count'],58)
        self.assertEqual(len(d['fields']),3)
        self.assertEqual(len(d['central_members']),32)
        self.assertFalse(d['settings_artifact_eligible'])
        self.assertEqual(d['source_label'],'NOT_R13_UNLESS_EXACT_CORE_HANDOFF')

    def test_no_partition_preservation_or_other_option_mutation(self):
        old='set_global_assignment -name SEED 2\n'
        self.assertTrue(s.permitted_delta(old,old,[]))
        with self.assertRaises(AssertionError):s.permitted_delta(old,'set_global_assignment -name SEED 3\n',[])
        with self.assertRaises(AssertionError):s.permitted_delta(old,old+'set_instance_assignment -name PRESERVE ON -to x\n',['set_instance_assignment -name PRESERVE ON -to x'])

    def test_captured_R13_literal_sources_match_physical_manifest(self):
        root=Path(s.__file__).resolve().parents[1]
        project=root/'results/throughput-20260929/trackS-c2-protected-relay13-physical-v1/physical-11500-v1/project'
        d=s.source_hierarchy(project)
        manifest=json.loads((project/'manifest.json').read_text())
        self.assertEqual(d['source_label'],'R13')
        self.assertEqual(d['production_sv_count'],58)
        self.assertEqual({Path(k).name:v for k,v in d['source_sha256'].items()},manifest['source_sha256'])
        self.assertEqual(d['top'],manifest['top'])
        self.assertEqual(d['source_sha256']['rtl/'+d['top']+'.sv'],'113b3da5de8d88a52eaf4fac01a7b78ffbb1308741a47e7e83669faa470ec299')
        self.assertEqual([x['hierarchy'] for x in d['fields']],['engine|arithmetic|field'+str(i) for i in range(3)])
        self.assertEqual(len(d['central_members']),32)
        self.assertFalse(d['settings_artifact_eligible'])


if __name__=='__main__':unittest.main()
