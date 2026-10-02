import unittest
from fpga.reference.track_a4_representative_prepare_v1 import pins,CPP,LAUNCHER,LAUNCHER_SHA


class RepresentativePreparationTests(unittest.TestCase):
    def test_source_closure(self):
        source,ticket=pins()
        self.assertEqual(source[LAUNCHER],LAUNCHER_SHA)
        self.assertIn(CPP,source)
        self.assertIn('rtl/tb/track_a4_representative_recipe_v1.hpp',source)
        self.assertEqual(ticket['native_top'],'genefer_track_a4_core_v3')


if __name__=='__main__':unittest.main()
