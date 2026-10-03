import unittest
from fpga.reference import stream27_r15_protocol_age_bind as original
from fpga.reference import stream27_r15_protocol_age_bind_v2 as v2
from fpga.reference import stream27_r15_protocol_age_bind_v3 as binder
from fpga.reference import stream27_r15_protocol_age_native_v3 as native


class BooleanPredicates(unittest.TestCase):
    def test_only_predicates_and_binary_semantics(self):
        for n in (256,65536):
            self.assertEqual(binder.prepare(n,0),original.capture(n))
            old=v2.prepare(n,1);new=binder.prepare(n,1)
            changed=[name for name in old['files'] if old['files'][name]!=new['files'][name]]
            self.assertEqual(changed,[original.PRIVATE_LEAF])
            text=new['files'][original.PRIVATE_LEAF]
            self.assertEqual(text.count(binder.AFTER),3)
            self.assertEqual(text.replace(binder.AFTER,binder.BEFORE),old['files'][original.PRIVATE_LEAF])
            self.assertEqual(new['parameters'],old['parameters'])
            self.assertEqual(new['geometry'],old['geometry'])
            for value in (0,1):self.assertEqual(bool(value),value!=0)
        for bad in (-1,2,True,None):
            with self.assertRaises(ValueError):binder.prepare(256,bad)

    def test_fresh_source_maps_callbacks_and_flags(self):
        for stage,count in (('aw8',60),('full',61)):
            m,f,b=native.role(stage)
            self.assertEqual(len(m['build']['sv_sources']),count)
            self.assertEqual(m['build']['parameters']['EPOCH_AGE_REG'],1)
            for path,raw in f.items():self.assertEqual(original.sha(raw),m['sources'][path])
            for name,text in b['files'].items():self.assertEqual(f['rtl/'+name],text.encode())
            self.assertTrue(m['r15_protocol_age']['old_execution_not_inherited'])
            self.assertEqual(m['r15_protocol_age']['ternary_condition_width'],1)
            self.assertEqual(m['r15_compute']['production_generated_sha256'],b['generated_sha256'])
            if stage=='full':
                self.assertEqual(m['steps'][0]['validator']['source'],native.SELF)
                self.assertIs(m['steps'][0]['validator']['config']['epoch_age_boolean_condition'],True)


if __name__=='__main__':unittest.main()
