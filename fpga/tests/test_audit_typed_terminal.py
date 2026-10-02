"""Exit2 is a timing result only with trusted manager and exact native evidence."""
import copy
import importlib.util
from pathlib import Path
import unittest

P=Path(__file__).resolve().parents[1]/'tools/collect_plain_fit_audit_noexceptions_terminal_v1.py'
spec=importlib.util.spec_from_file_location('collector',P);c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class TerminalTests(unittest.TestCase):
    def fixture(self):
        unit='gfn16-test-audit.service'
        proof=dict(unit=unit,manager_elapsed_seconds=200,terminal_kind='failed',
            manager_terminal_message=unit+": Failed with result 'exit-code'.",
            manager_main_exit_messages=[unit+': Main process exited, code=exited, status=2/INVALIDARGUMENT'])
        result=dict(returncode=2,native_execution_complete=True,final_errors=[],status='native_timing_violation',timing_closes=False)
        receipt=dict(status='native_timing_violation',timing_closes=False,original_unchanged=True,
                     compiled_input_unchanged=True,final_verification_errors=[],fit_commands=0)
        return proof,result,receipt

    def test_exact_collected_timing_failure_is_typed_not_pass(self):
        p,r,e=self.fixture();c.typed_terminal(p,r,e);self.assertFalse(e['timing_closes'])

    def test_arbitrary_exit2_and_manager_drift_are_rejected(self):
        for field,value in [('manager_main_exit_messages',[]),('manager_main_exit_messages',['untrusted stdout exit2']),
            ('manager_terminal_message',"gfn16-test-audit.service: Failed with result 'timeout'."),
            ('terminal_kind','deactivated_successfully'),('manager_elapsed_seconds',2281)]:
            p,r,e=self.fixture();p[field]=value
            with self.assertRaises(ValueError):c.typed_terminal(p,r,e)

    def test_native_tool_or_source_failures_remain_blocked(self):
        for field,value in [('native_execution_complete',False),('final_errors',['tool failed']),
                            ('returncode',1),('returncode',124),('status','native_error')]:
            p,r,e=self.fixture();r[field]=value
            with self.assertRaises(ValueError):c.typed_terminal(p,r,e)
        for field,value in [('original_unchanged',False),('compiled_input_unchanged',False),
                            ('final_verification_errors',['source drift']),('fit_commands',1),('timing_closes',True)]:
            p,r,e=self.fixture();e[field]=value
            with self.assertRaises(ValueError):c.typed_terminal(p,r,e)

    def test_success_requires_exact_zero_and_closing_receipt(self):
        p,r,e=self.fixture();p['terminal_kind']='deactivated_successfully';r['returncode']=0
        r['status']=e['status']='native_scoped_timing_closes_pending_independent_review'
        r['timing_closes']=e['timing_closes']=True;c.typed_terminal(p,r,e)
        p['terminal_kind']='failed'
        with self.assertRaises(ValueError):c.typed_terminal(p,r,e)

if __name__=='__main__':unittest.main()
