import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import stream27_shared_field_v3 as old_fields
from fpga.reference import stream27_shared_field_v4 as fields
from fpga.reference import stream27_host_chain_param_v1 as old_host
from fpga.reference import stream27_host_chain_param_v2 as host
from fpga.reference import stream27_host_chain_native_v3 as old_native
from fpga.reference import stream27_host_chain_native_v4 as native


class InternalStartEligibility(unittest.TestCase):
    def test_only_field_top_start_expression_changes(self):
        for n,p in ((32,16),(32,8),(256,16),(256,8)):
            for mode in ('probe','warm','warm_signed'):
                old=old_fields.prepare(n,p,0,mode=mode);new=fields.prepare(n,p,0,mode=mode)
                self.assertEqual(old['geometry'],new['geometry'])
                a=dict(old['files']);b=dict(new['files'])
                if mode!='probe':
                    text=b.pop(new['top']+'.sv').replace(new['top'],old['top'])
                    text=text.replace('.frame_start(digit_slot && ','.frame_start(')
                    self.assertEqual(text,a.pop(old['top']+'.sv'))
                self.assertEqual(a,b)

    def test_invalid_payload_cannot_start_ct_but_real_cadence_faults_remain(self):
        def cadence(slot,start,remaining):
            return (start and (not slot or remaining!=0)) or (slot and not start and remaining==0) or (not slot and remaining!=0)
        self.assertTrue(cadence(False,True,0))
        for slot in (False,True):
            for tag in (False,True):
                for remaining in (0,1):
                    revised=cadence(slot,slot and tag,remaining)
                    if slot:self.assertEqual(revised,cadence(slot,tag,remaining))
                    if remaining and not slot:self.assertTrue(revised)
                    if not slot and not remaining:self.assertFalse(revised)

    def test_whole_host_other_bytes_and_calendar_unchanged(self):
        for n,p in ((32,16),(32,8),(256,16),(256,8)):
            a=old_host.prepare(n,p,paired=True);b=host.prepare(n,p,paired=True)
            self.assertEqual(a['geometry'],b['geometry']);self.assertEqual(a['cycle_contract'],b['cycle_contract'])
            normalized={name.replace('_valid_start_v4',''):text.replace('_valid_start_v4','').replace('.frame_start(digit_slot && ','.frame_start(') for name,text in b['files'].items()}
            self.assertEqual(a['files'],normalized)

    def test_p16_native_assertions_vectors_and_steps_not_relaxed(self):
        with tempfile.TemporaryDirectory(prefix='s4-valid-start-source-') as root:
            a=Path(root)/'old';b=Path(root)/'new'
            old_native.prepare(a,n=32);native.prepare(b,n=32,p=16)
            ma=json.loads((a/'manifest.json').read_text());mb=json.loads((b/'manifest.json').read_text())
            self.assertEqual(ma['steps'],mb['steps'])
            for key,value in ma['build'].items():
                if key=='sv_sources':
                    self.assertEqual(sorted(value),sorted(name.replace('_valid_start_v4','') for name in mb['build'][key]))
                else:self.assertEqual(value,mb['build'][key],key)
            bench='rtl/tb/stream27_host_chain_v1.cpp'
            self.assertEqual((a/'inputs/fpga'/bench).read_bytes(),(b/'inputs/fpga'/bench).read_bytes())
            for path in (a/'inputs/fpga/assets').iterdir():
                self.assertEqual(path.read_bytes(),(b/'inputs/fpga/assets'/path.name).read_bytes())
            self.assertIn('S4_LONG_RESET_NO_STALE_WORK',(b/'inputs/fpga'/bench).read_text())

    def test_p8_real_binding_and_ordinal_true_final_rows(self):
        with tempfile.TemporaryDirectory(prefix='s4-valid-start-source-') as root:
            b=Path(root)/'packet';r=native.prepare(b,n=32,p=8,ordinal=True)
            m=json.loads((b/'manifest.json').read_text());s=b/'inputs/fpga'
            self.assertEqual(m['build']['parameters'],dict(AW=5,P=8,CONTEXTS=1,EPOCH_SEED=65534))
            self.assertIn('true_final_rows=4',m['steps'][0]['expected_stdout'])
            self.assertIn('operations=65540',m['steps'][0]['expected_stdout'])
            self.assertIn('MIN_BASE=172',(s/'rtl/tb/s4_host_config_v1.h').read_text())
            self.assertIn('d.final_image_rows==N/P',(s/'rtl/tb/stream27_host_chain_v1.cpp').read_text())
            self.assertEqual(r['geometry']['p'],8)


if __name__=='__main__':unittest.main()
