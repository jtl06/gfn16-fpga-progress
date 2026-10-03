import unittest
from fpga.reference import stream27_r15_protocol_age_bind as v1
from fpga.reference import stream27_r15_protocol_age_bind_v2 as binder
from fpga.reference import stream27_r15_protocol_age_native_v2 as native


class AgeParameterWidth(unittest.TestCase):
    def test_off_exact_and_width_only_private_leaf(self):
        for n in (256,65536):
            self.assertEqual(binder.prepare(n,0),v1.capture(n))
            old=v1.prepare(n,1);new=binder.prepare(n,1)
            self.assertEqual(set(old['files']),set(new['files']))
            changed=[name for name in old['files'] if old['files'][name]!=new['files'][name]]
            self.assertEqual(changed,[v1.PRIVATE_LEAF])
            self.assertEqual(new['files'][v1.PRIVATE_LEAF].replace(binder.AFTER,binder.BEFORE,1),old['files'][v1.PRIVATE_LEAF])
            self.assertEqual(new['parameters'],old['parameters'])
            self.assertEqual(new['geometry'],old['geometry'])
            for value in (0,1):self.assertEqual(bool(value&1),bool(value&0xffffffff))
        for bad in (-1,2,True,None):
            with self.assertRaises(ValueError):binder.prepare(256,bad)

    def test_own_native_source_maps_both_geometries(self):
        for stage,count in (('aw8',60),('full',61)):
            m,f,b=native.role(stage)
            self.assertEqual(len(m['build']['sv_sources']),count)
            self.assertEqual(m['build']['parameters']['EPOCH_AGE_REG'],1)
            self.assertEqual(m['build']['parameters']['EPOCH_SEED0'],65534)
            for path,raw in f.items():self.assertEqual(v1.sha(raw),m['sources'][path])
            for name,text in b['files'].items():self.assertEqual(f['rtl/'+name],text.encode())
            self.assertEqual(m['r15_compute']['production_generated_sha256'],b['generated_sha256'])
            for key in ('host_contexts','r84_explicit_small'):
                if key in m:self.assertEqual(m[key]['generated_sha256'],b['generated_sha256'])
            self.assertEqual(m['r15_protocol_age']['flag_declaration_width'],32)
            self.assertTrue(m['r15_protocol_age']['old_execution_not_inherited'])
            if stage=='full':
                self.assertEqual(m['steps'][0]['validator']['source'],native.SELF)
                self.assertEqual(m['steps'][0]['validator']['config']['epoch_age_flag_width'],32)


if __name__=='__main__':unittest.main()
