"""Mocked Tcl wrapper lifecycle checks; not Quartus execution evidence."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which('tclsh'),'Tcl interpreter required')
class PostfitWrapperTests(unittest.TestCase):
    def run_wrapper(self,fit='Successful',top='genefer_ntt_banked27_tiled_engine',fail=False):
        wrapper=Path(__file__).resolve().parents[1]/'synthesis/postfit_tiled_audit.tcl'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'output_files').mkdir()
            (root/'output_files/probe.fit.summary').write_text('Fitter Status : '+fit+'\n')
            script='''
proc load_package {p} {}
proc project_open {p} {puts OPEN}
proc project_close {args} {puts "CLOSE $args"}
proc create_timing_netlist {args} {puts NETLIST}
proc delete_timing_netlist {} {puts DELETE}
proc read_sdc {} {}
proc update_timing_netlist {} {}
proc get_registers {pattern} {return {}}
proc get_node_info {args} {error unused}
proc get_edge_info {args} {error unused}
proc get_fanouts {args} {error unused}
proc foreach_in_collection {var items body} {uplevel 1 [list foreach $var $items $body]}
'''
            script+='proc get_global_assignment {args} {return {'+top+'}}\n'
            if fail:script+='proc update_timing_netlist {} {error injected_failure}\n'
            script+='set quartus(args) [list {'+str(root)+'}]\n'
            script+='if {[catch {source {'+str(wrapper)+'}} err]} {puts "FAILED $err"}\n'
            return subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=True)

    def test_completed_flow_does_not_export_assignments(self):
        r=self.run_wrapper();self.assertEqual(r.stderr,'')
        self.assertIn('TILE_AUDIT\tEND\t1',r.stdout)
        self.assertIn('DELETE\nCLOSE -dont_export_assignments',r.stdout)

    def test_failed_fit_cannot_load_netlist(self):
        r=self.run_wrapper(fit='Failed')
        self.assertIn('Requires successful fitting',r.stdout)
        self.assertNotIn('OPEN',r.stdout)

    def test_wrong_top_closes_without_netlist(self):
        r=self.run_wrapper(top='other')
        self.assertIn('CLOSE -dont_export_assignments',r.stdout)
        self.assertNotIn('NETLIST',r.stdout)

    def test_folded_baseline_uses_global_control_patterns(self):
        r=self.run_wrapper(top='genefer_ntt_banked27_folded_engine')
        self.assertIn('*pairing_e*',r.stdout)
        self.assertIn('*rotation_d*',r.stdout)
        self.assertIn('CLOSE -dont_export_assignments',r.stdout)

    def test_query_failure_cleans_up_without_export(self):
        r=self.run_wrapper(fail=True)
        self.assertIn('DELETE\nCLOSE -dont_export_assignments',r.stdout)
        self.assertIn('FAILED injected_failure',r.stdout)


if __name__=='__main__':unittest.main()
