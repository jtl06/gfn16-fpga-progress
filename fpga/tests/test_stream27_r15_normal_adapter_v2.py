import importlib.util
import json
from pathlib import Path
import unittest
from fpga.reference import stream27_r15_normal_adapter_v2 as own


class R15NormalAdapterTests(unittest.TestCase):
    def test_source_captures_literal_and_loader_import_safe(self):
        for mode in ('fixed','compute'):
            for stage in ('aw8','full'):
                with self.subTest(mode=mode,stage=stage):
                    manifest,files,bundle=own.role(mode,stage)
                    for name,text in bundle['files'].items():self.assertEqual(files['rtl/'+name],text.encode())
                    self.assertEqual(manifest['sources'],{n:own.sha(v) for n,v in files.items()})
                    self.assertEqual(len(manifest['build']['sv_sources']),len(bundle['files'])+(stage=='full'))
        spec=importlib.util.spec_from_file_location('_native_result_validator',own.ROOT/own.VALIDATOR)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        value=dict(aw=16,p=16,contexts=2,bases=[604832956,999999937],squares=8,reads=393216,
          signed96=True,context_alone_bit_identical=True,independent_reference=True,interval=8461,pair_launch_cycles=8461,
          peer_live_reads=65536,model_threads=1,launches=[[204,8665],[4434,12895]],warm_edges=[21224,25454],
          setup_edges=[99,199],single_first=[104,104],done_edges=[680689,1340153],joint_cycles=1405689,
          single_cycles=[746125,746125],overlap_edges=680688,seconds=1.0)
        stdout='R84_C2_FULL_PASS '+json.dumps(value)+'\n'
        for mode in ('fixed','compute'):
            manifest,_,_=own.role(mode,'full')
            contract=manifest['steps'][0]['validator']
            got=getattr(module,contract['function'])(stdout,'',0,contract['config'],{})
            self.assertEqual(got['status'],'PASS_expected_contracts')
            with self.assertRaises(ValueError):getattr(module,contract['function'])(stdout,'bad',0,contract['config'],{})


if __name__=='__main__':unittest.main()
