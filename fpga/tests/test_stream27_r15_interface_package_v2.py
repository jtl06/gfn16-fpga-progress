import unittest
from fpga.reference import stream27_r15_interface_package_v2 as p


class Package(unittest.TestCase):
    def test_current_adopted_tools_are_exact(self):
        for path,pin in p.PINS.items():self.assertEqual(p.sha(p.ROOT/path),pin)

    def test_no_foreign_namespace_or_launch(self):
        with self.assertRaisesRegex(ValueError,'OWN_ROLE'):
            p.prepare_role(p.ROOT/'results/foreign','foreign-q1-v1')
        text=(p.ROOT/'reference/stream27_r15_interface_package_v2.py').read_text()
        self.assertNotIn('subprocess',text)
        self.assertNotIn('ssh ',text)
        self.assertIn("for suffix in ('1213','1415')",text)
