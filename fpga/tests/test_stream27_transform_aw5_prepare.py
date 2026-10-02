import unittest
from fpga.reference.stream27_transform_aw5_vectors import prepare
from fpga.reference.stream27_transform_aw5_prepare import mutated_files, vector_metadata


class TinyTransformPreparation(unittest.TestCase):
    def test_exact_schema_oracle_and_isolated_mutations(self):
        bundle=prepare();files=bundle['files']
        for inverse in (0,1):
            counts=vector_metadata(files[f'transform-aw5-{inverse}.txt'],inverse)
            self.assertGreater(counts['slots'],counts['commits'])
            self.assertGreater(counts['errors'],0)
            self.assertGreater(counts['resets'],40)
        for kind in ('wrong_root','filtered_valid'):
            changed,mutation=mutated_files(files,kind)
            self.assertEqual([name for name in files if files[name]!=changed[name]],[mutation['path']])
        wrong,_=mutated_files(files,'wrong_root')
        path='genefer_stream27_dif_aw5_p8_f0_stage0_root0.hex'
        self.assertEqual(files[path].splitlines()[0],wrong[path].splitlines()[0])
        self.assertNotEqual(files[path].splitlines()[1],wrong[path].splitlines()[1])


if __name__=='__main__':unittest.main()
