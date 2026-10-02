from datetime import datetime,timezone
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.cloud import azure_fit_v2 as p


class AzurePolicyV2Tests(unittest.TestCase):
    def test_exact_two_guard_delta_and_identity_renames(self):
        old=Path(p.__file__).with_name('azure_fit_v1.py').read_text()
        self.assertEqual(hashlib.sha256(old.encode()).hexdigest(),'834c1991ac7076485fa8346c74117db8fc2215c80ce11cd2ea29ee137510933c')
        expected=old.replace('azure_fit_v1','azure_fit_v2').replace('run-azure-fit-v1','run-azure-fit-v2').replace('azure-f16ams-v7-v1','azure-f16ams-v7-v2')
        expected=expected.replace('current+TIMEOUT+120<DEADLINE','current+TIMEOUT+180<DEADLINE')
        expected=expected.replace('approved,context=verify_approval(approval_path,approval_sha,ROOT/probe,topology_path)',
                                  "approved,context=verify_approval(approval_path,approval_sha,ROOT/probe,topology_path)\n    require(approved.get('slot')==slot,'approved slot drift')")
        self.assertEqual(Path(p.__file__).read_text(),expected)

    def test_actual_launch_refuses_approval_slot_mismatch(self):
        with patch.object(Path,'cwd',return_value=p.ROOT),patch.object(p.socket,'gethostname',return_value=p.HOST),\
             patch.object(p.resource,'setrlimit'),patch.object(p,'verify_approval',return_value=({'slot':'a'},{})),\
             patch.object(p,'deadline_guard') as deadline:
            with self.assertRaisesRegex(ValueError,'slot drift'):
                p.launch('probe','b',Path('/topology'),Path('/approval'),'0'*64)
            deadline.assert_not_called()

    def test_deadline_includes_outer_timeout_and_stop_grace(self):
        with patch.object(p,'PROTECTED',{}),patch.object(p.subprocess,'run') as call:
            now=datetime.fromtimestamp(p.DEADLINE-p.TIMEOUT-180,timezone.utc)
            with self.assertRaisesRegex(ValueError,'deadline'):p.deadline_guard(now)
            call.assert_not_called()
            call.side_effect=[type('R',(),{'returncode':0,'stdout':'active'})(),type('R',(),{'returncode':0,'stdout':'enabled'})()]
            safe=datetime.fromtimestamp(p.DEADLINE-p.TIMEOUT-181,timezone.utc)
            self.assertEqual(p.deadline_guard(safe)['epoch'],1791189913)

    def test_shell_capture_identity_only(self):
        root=Path(p.__file__).parent
        self.assertEqual((root/'run-azure-fit-v2.sh').read_text(),(root/'run-azure-fit-v1.sh').read_text().replace('azure_fit_v1','azure_fit_v2'))
        self.assertEqual((root/'capture_azure_fit_v2.py').read_text(),(root/'capture_azure_fit_v1.py').read_text().replace('azure_fit_v1','azure_fit_v2'))


if __name__=='__main__':unittest.main()
