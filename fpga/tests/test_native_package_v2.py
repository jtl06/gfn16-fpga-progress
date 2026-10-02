"""Safe staging tests: source/archive replay, no network or native compiler."""
import copy
import gzip
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_package_v2 as p

FPGA=Path(__file__).resolve().parents[1]
ARCHIVE=FPGA/'artifacts/native-shared-smoke-v1/packet/package.tar.gz'
ARCHIVE_SHA='35e531b9b9eb223ea2261e966c3fef0002263bc7bcc1f01e4aee3544cf3bb4d5'
TICKET_SHA='7b1ac83e7f4c470f2cea6d5053f65a1579923077462e7d9a754bf8d0f00810ba'


class StageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
        self.payload,self.ticket,self.manifest,self.profile=p.inspect_archive(ARCHIVE,ARCHIVE_SHA,TICKET_SHA)

    def write_archive(self,entries,name='test.tar.gz'):
        path=self.root/name
        with tarfile.open(path,'w:gz') as archive:
            for item,raw in entries:
                info=tarfile.TarInfo(item);info.size=len(raw);archive.addfile(info,io.BytesIO(raw))
        return path

    def stage_fixture(self):
        profile=copy.deepcopy(self.profile);profile['base']=str(self.root/'native');profile['lock']=str(self.root/'native/compile.lock')
        ticket=copy.deepcopy(self.ticket);ticket['native_root']=str(self.root/'native/jobs'/ticket['id'])
        return self.payload,ticket,self.manifest,profile

    def invoke_fixture(self):
        with patch.object(p,'inspect_archive',return_value=self.stage_fixture()),patch.object(p,'host_check'):
            return p.stage(ARCHIVE,ARCHIVE_SHA,TICKET_SHA)

    def test_real_smoke_archive_complete_replay(self):
        self.assertEqual(len(self.payload),13);self.assertEqual(len(self.manifest['sources']),8)
        self.assertEqual(self.profile['cpus'],[0,1])

    def test_hash_drift_before_any_destination_effect(self):
        with self.assertRaises(ValueError):p.stage(ARCHIVE,'0'*64,TICKET_SHA)
        self.assertEqual(list(self.root.iterdir()),[])
        with self.assertRaises(ValueError):p.inspect_archive(ARCHIVE,ARCHIVE_SHA,'0'*64)

    def test_path_traversal_absolute_and_duplicate_members(self):
        for index,names in enumerate([['../escape'],['/escape'],['x','x'],['a/../b'],['a//b']]):
            path=self.write_archive([(n,b'x') for n in names],str(index)+'.tar.gz')
            with self.assertRaises(ValueError):p.inspect_archive(path,p.sha(path),TICKET_SHA)

    def test_symlink_hardlink_and_directory_members_refused(self):
        for index,kind in enumerate((tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.DIRTYPE)):
            path=self.root/(str(index)+'.tar.gz')
            with tarfile.open(path,'w:gz') as archive:
                member=tarfile.TarInfo('link');member.type=kind;member.linkname='../outside';archive.addfile(member)
            with self.assertRaises(ValueError):p.inspect_archive(path,p.sha(path),TICKET_SHA)

    def test_declared_oversize_rejected_without_reading_payload(self):
        info=tarfile.TarInfo('oversize');info.size=p.MAX_FILE+1
        path=self.root/'oversize.tar.gz';path.write_bytes(gzip.compress(info.tobuf()+b'\0'*1024))
        with self.assertRaisesRegex(ValueError,'member size'):p.inspect_archive(path,p.sha(path),TICKET_SHA)

    def test_extra_or_changed_closed_source_rejected(self):
        items=list(self.payload.items())+[('unexpected.txt',b'bad')]
        path=self.write_archive(items)
        with self.assertRaisesRegex(ValueError,'closure'):p.inspect_archive(path,p.sha(path),TICKET_SHA)
        changed=dict(self.payload);name=next(n for n in changed if n.endswith('.sv'));changed[name]+=b'\n'
        path=self.write_archive(list(changed.items()),'changed.tar.gz')
        with self.assertRaisesRegex(ValueError,'source byte'):p.inspect_archive(path,p.sha(path),TICKET_SHA)

    def test_success_then_idempotent_preserves_runtime_outputs_and_claims(self):
        first=self.invoke_fixture();root=Path(first['root'])
        self.assertEqual(first['status'],'staged_exact_inputs')
        (root/'output/runtime-result.json').write_text('preserve runtime')
        claim=self.root/'native/claims/old.json';claim.write_text('preserve claim')
        before={str(x.relative_to(root)):p.sha(x) for x in root.rglob('*') if x.is_file()}
        second=self.invoke_fixture()
        self.assertEqual(second['status'],'already_staged_exact_inputs')
        self.assertEqual(claim.read_text(),'preserve claim')
        self.assertEqual(before,{str(x.relative_to(root)):p.sha(x) for x in root.rglob('*') if x.is_file()})

    def test_unreceipted_existing_root_and_changed_stage_refused(self):
        root=Path(self.stage_fixture()[1]['native_root']);root.mkdir(parents=True);(root/'keep').write_text('keep')
        with self.assertRaises(ValueError):self.invoke_fixture()
        self.assertEqual((root/'keep').read_text(),'keep')

    def test_changed_existing_input_refused_not_repaired(self):
        result=self.invoke_fixture();root=Path(result['root']);path=root/'manifest.json';path.write_text('changed')
        with self.assertRaises(ValueError):self.invoke_fixture()
        self.assertEqual(path.read_text(),'changed')

    def test_copy_failure_is_preserved_no_retry(self):
        original=p.sha
        def fail(path):
            if str(path).startswith(str(self.root/'native')) and str(path).endswith('.sv'):raise OSError('injected copy verification failure')
            return original(path)
        with patch.object(p,'sha',side_effect=fail),self.assertRaises(OSError):self.invoke_fixture()
        root=Path(self.stage_fixture()[1]['native_root'])
        failure=json.loads((root/'stage-failure.json').read_text());self.assertEqual(failure['status'],'failed_stage_preserved')
        with self.assertRaises(ValueError):self.invoke_fixture()
        self.assertTrue((root/'stage-failure.json').exists())

    def test_redirected_base_or_claims_refused(self):
        (self.root/'outside').mkdir();(self.root/'native').symlink_to(self.root/'outside',target_is_directory=True)
        with self.assertRaises(ValueError):self.invoke_fixture()
        self.assertEqual(list((self.root/'outside').iterdir()),[])

    def test_wrong_host_or_user_refused(self):
        with patch.object(p.socket,'gethostname',return_value='wrong-host'),self.assertRaises(ValueError):p.host_check(self.profile)


if __name__=='__main__':unittest.main()
