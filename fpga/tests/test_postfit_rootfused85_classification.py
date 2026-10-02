"""Synthetic parser tests only, not native timing measurements."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack,nullcontext
from types import SimpleNamespace
from fpga.cloud import aws_postfit_rootfused85_v1 as a


def report(slack=-1.534,count=1000):
    source='field_lane[0].engine|child|memories[60].data_ram|ram_block~reg1'
    target='coefficient_lane[0].crt|delta2[6]'
    return ('Report Timing: Found '+str(count)+' setup paths ('+str(count if slack<0 else 0)+' violated).\n'
            '; Summary of Paths ;\n'
            '; Slack ; From Node ; To Node ; Launch Clock ; Latch Clock ; Relationship ; Clock Skew ; Data Delay ;\n'+
            ''.join(f'; {slack} ; {source} ; {target} ; kernel_clk ; kernel_clk ; 10.000 ; 0 ; 11.0 ;\n' for _ in range(count))+
            ''.join(f'Path #{i}: Setup slack is {slack}\n' for i in range(1,count+1)))


class ClassificationTests(unittest.TestCase):
    def test_exact_thousand_and_family(self):
        rows=a.parse_path_report(report(),'Slow 900mV 100C Model')
        self.assertEqual(len(rows),1000)
        self.assertEqual(rows[0]['family'],'NTT data RAM -> CRT delta2/delta3')
        self.assertIn('memories[60]',rows[0]['from_node'])

    def test_reject_truncation_clock_count_order_and_nan(self):
        text=report()
        for bad in (report(count=999),text.replace('Path #1000:','Path #999:'),
                    text.replace('10.000','11.764'),text.replace('kernel_clk ; kernel_clk','other ; kernel_clk'),
                    text.replace('-1.534','nan'),text.replace('1000 violated','999 violated')):
            with self.subTest(bad=bad[:60]),self.assertRaises(ValueError):a.parse_path_report(bad,'corner')

    def test_global_selection_and_unique_endpoint_limit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);corners={}
            for i,name in enumerate(sorted(a.CORNERS)):
                slack=-1.534 if i==0 else -.5 if i==1 else .5
                (root/f'baseline100-{i}-setup-paths.rpt').write_text(report(slack))
                corners[name]={'setup':{'status':'measured','slack_ns':slack}}
            result=a.classify_paths(root,corners)
            self.assertEqual(result['observed_paths'],4000)
            self.assertEqual(result['observed_failing_paths'],2000)
            self.assertEqual(result['selected_count'],1000)
            self.assertEqual(result['family_counts'],{'NTT data RAM -> CRT delta2/delta3':1000})
            self.assertTrue(all(x['slack_ns']==-1.534 for x in result['paths']))
            self.assertIn('not unique endpoints',result['scope'])

    def test_unclassified_names_not_dropped(self):
        self.assertTrue(a.path_family('unexpected_register[17]').startswith('other:'))


class InventoryModeTests(unittest.TestCase):
    def launch_mock(self,root,inventory_only,max_copy_bytes):
        top=root/'topology.json';top.write_text('{}')
        for name in ('postfit_rootfused85_proposal_v1.json','postfit_rootfused85_audit_v1.tcl','aws_fit_v6.py','runner.py'):
            (root/name).write_text('{}')
        digest=a.sha(top);selected={'affinity':[4,5,6,7],'physical_cores':[[0,c] for c in range(4,8)],'topology':{}}
        before={'qdb/data':{'sha256':'0'*64,'size':100}}
        with ExitStack() as stack:
            replacements={'ROOT':root,'__file__':str(root/'runner.py'),'PROPOSAL_SHA':digest,'SCRIPT_SHA':digest,
                          'HELPER_SHA':digest,'inventory':lambda p:before,'verify_project':lambda *args:None,
                          'validate_topology':lambda *args:selected,'live_topology':lambda:[],
                          'slot_locks':lambda *args:['b'],'locked':lambda *args:nullcontext(),
                          'live_limits':lambda:{'cpu_max':'400000 100000','memory_max':str(24<<30)}}
            for name,value in replacements.items():stack.enter_context(patch.object(a,name,value))
            stack.enter_context(patch('pathlib.Path.cwd',return_value=root))
            stack.enter_context(patch('socket.gethostname',return_value=a.HOST))
            stack.enter_context(patch('os.geteuid',return_value=1000))
            stack.enter_context(patch('pwd.getpwuid',return_value=SimpleNamespace(pw_name='ubuntu')))
            stack.enter_context(patch('os.sched_getaffinity',return_value={4,5,6,7},create=True))
            stack.enter_context(patch.object(a.resource,'setrlimit'))
            stack.enter_context(patch.object(a,'snapshot',side_effect=AssertionError('snapshot forbidden')))
            stack.enter_context(patch.object(a,'run',side_effect=AssertionError('Quartus forbidden')))
            return a.launch('b',top,'rootfused85-preflight-test',max_copy_bytes,inventory_only=inventory_only)

    def test_inventory_never_copies_or_starts_quartus(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();self.assertEqual(self.launch_mock(root,True,0),0)
            out=root/'rootfused85-preflight-test'
            self.assertEqual([p.name for p in out.iterdir()],['inventory.json'])
            receipt=json.loads((out/'inventory.json').read_text())
            self.assertEqual(receipt['snapshot_bytes'],100)
            self.assertEqual(receipt['status'],'inventory_only_no_copy_no_quartus')

    def test_unapproved_copy_cost_rejects_before_output_or_copy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()
            with self.assertRaisesRegex(ValueError,'reviewed copy cost'):self.launch_mock(root,False,99)
            self.assertFalse((root/'rootfused85-preflight-test').exists())


if __name__=='__main__':unittest.main()
