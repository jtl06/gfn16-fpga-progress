import copy
import json
import unittest
from fpga.reference.stream27_r15_host_window_application_gmp_native import role,PARENT,CPP,identity
from fpga.reference.stream27_r15_host_window_application_gmp_output import expected,validate


class Source(unittest.TestCase):
    def test_all70_and_observer_header_build_probe_literal(self):
        m,files,bundle=role();old=json.loads((PARENT/'manifest.json').read_bytes())
        self.assertEqual(len(bundle['files']),70)
        for name,text in bundle['files'].items():self.assertEqual(files['rtl/'+name],text.encode())
        for key in ('parameters','sv_sources','runtime_threads','cflags'):
            self.assertEqual(m['build'][key],old['build'][key])
        self.assertEqual(m['probe'],old['probe'])
        cpp=files[CPP].decode();self.assertEqual(cpp.count('DUT d(&context)'),1)
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('DUT d(&context)'))

    def test_source_steps_bound_and_schema_not_mislabelled_direct65(self):
        m,_,_=role();self.assertEqual(identity(m),m['metadata']['r15_native_gmp']['fixture_sha256'])
        self.assertEqual(m['metadata']['r15_native_gmp']['schema'],'r15-application70-gmp-link-v1')
        bad=copy.deepcopy(m);bad['build']['ldflags']=['-lgmp']
        self.assertNotEqual(identity(bad),identity(m))
        self.assertNotEqual(identity(role('faults')[0]),identity(m))

    def test_exact_healthy_and_controls_no_board_promotion(self):
        self.assertFalse(validate(expected(),'',0)['board'])
        self.assertFalse(validate(expected('rollback'),'',0,mode='rollback')['hardware_reset_delivery'])
        self.assertFalse(validate(expected(),'R15_APP_WINDOW_SIGNED96_ORACLE_WITNESS\n',1,
                                  mode='oracle-negative')['promotion'])
        for out,rc in ((expected()+'x',0),(expected().replace('board=0','board=1'),0),(expected(),False)):
            with self.assertRaises(ValueError):validate(out,'',rc)


if __name__=='__main__':unittest.main()
