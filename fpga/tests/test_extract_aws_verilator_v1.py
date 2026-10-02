"""Offline rootless extraction safety checks; no network or native execution."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import extract_aws_verilator_v1 as r


def tar_fixture(path, specs):
    with tarfile.open(path,'w') as archive:
        for name,kind,content in specs:
            member = tarfile.TarInfo(name)
            member.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
            member.type = kind
            if kind == tarfile.REGTYPE:
                member.size = len(content)
                archive.addfile(member,io.BytesIO(content))
            else:
                if kind in (tarfile.SYMTYPE,tarfile.LNKTYPE):
                    member.linkname = content
                archive.addfile(member)


class RootlessVerilatorTests(unittest.TestCase):
    def test_exact_url_metadata_package_and_distinct_profile(self):
        root = Path(__file__).resolve().parents[1]
        observed = json.loads((root/'docs/briefs/replies/2026-10-01-aws-simulation-readonly-inventory-v1.json').read_text())
        from fpga.tools.aws_sim_profile_plan_v1 import package_fields
        metadata = package_fields(observed['apt']['verilator']['show']['stdout'])
        self.assertEqual(r.URL,'http://us-east-1.ec2.archive.ubuntu.com/ubuntu/'+metadata['Filename'])
        self.assertEqual(r.PACKAGE_SHA,metadata['SHA256'])
        self.assertEqual(r.PACKAGE_BYTES,int(metadata['Size']))
        self.assertEqual(r.TOOLS['python'][0],'/usr/bin/python3.12')
        self.assertEqual(r.TOOLS['compiler'][0],'/usr/bin/x86_64-linux-gnu-g++-13')

    def test_resource_caps_affinity_and_smt_faults(self):
        cores = {cpu:(0,cpu) for cpu in range(5)}
        good = ('100000 100000',str(1<<30),'0',[4],cores)
        self.assertEqual(r.validate_limits(*good)['affinity'],[4])
        for index,value in ((0,'max 100000'),(0,'200000 100000'),(1,'max'),(1,str((1<<30)+1)),
                            (2,'max'),(2,'1'),(3,[0]),(3,[4,5])):
            args = list(good); args[index] = value
            with self.subTest(index=index,value=value), self.assertRaises(ValueError):
                r.validate_limits(*args)
        cores[4] = cores[0]
        with self.assertRaisesRegex(ValueError,'disjoint'):
            r.validate_limits(*good)

    def test_off_host_and_wrong_pin_fail_before_mutation(self):
        with patch.object(r,'fresh_destination',side_effect=AssertionError('too early')):
            with self.assertRaisesRegex(ValueError,'helper SHA'):
                r.execute('0'*64)
            with patch.object(r.socket,'gethostname',return_value='Mac'):
                with self.assertRaisesRegex(ValueError,'approved AWS worker'):
                    r.execute(r.sha(Path(r.__file__)))

    def test_existing_target_and_symlink_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve(); destination = base/'tools/v1'
            with patch.object(r,'WORKER',base),patch.object(r,'DEST',destination):
                r.fresh_destination(destination,os.getuid())
                destination.mkdir(parents=True)
                with self.assertRaisesRegex(ValueError,'fresh destination'):
                    r.fresh_destination(destination,os.getuid())
            other = base/'linked'; other.symlink_to(destination)
            with self.assertRaisesRegex(ValueError,'symlink ancestor'):
                r.canonical(other/'child')

    def test_exact_package_size_sha_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'package'; path.write_bytes(b'good')
            digest = hashlib.sha256(b'good').hexdigest()
            with patch.object(r,'PACKAGE_BYTES',4),patch.object(r,'PACKAGE_SHA',digest):
                r.verify_package(path)
                path.write_bytes(b'baad')
                with self.assertRaisesRegex(ValueError,'size/SHA/type'):
                    r.verify_package(path)
                path.write_bytes(b'good')
                link = Path(folder)/'link'; link.symlink_to(path)
                with self.assertRaises(ValueError):
                    r.verify_package(link)
                hard = Path(folder)/'hard'; os.link(path,hard)
                with self.assertRaises(ValueError):
                    r.verify_package(path)

    def test_member_path_faults(self):
        self.assertEqual(r.member_name('./usr/bin/'),'usr/bin')
        for name in ('/escape','../escape','usr/../escape','usr//bin','././usr','usr/\x00x',''):
            with self.subTest(name=name),self.assertRaises(ValueError):
                r.member_name(name)

    def test_special_tar_types_duplicate_paths_and_modes_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'data.tar'
            for kind in (tarfile.LNKTYPE,tarfile.FIFOTYPE,tarfile.CHRTYPE,tarfile.BLKTYPE,tarfile.GNUTYPE_SPARSE):
                tar_fixture(path,[('usr/bin/bad',kind,'usr/bin/good')])
                with self.subTest(kind=kind),self.assertRaises(ValueError):
                    r.validate_tar(path)
            tar_fixture(path,[('usr/bin/x',tarfile.REGTYPE,b'1'),('./usr/bin/x',tarfile.REGTYPE,b'2')])
            with self.assertRaisesRegex(ValueError,'unique'):
                r.validate_tar(path)
            with tarfile.open(path,'w') as archive:
                member = tarfile.TarInfo('usr/bin/x'); member.mode=0o4755; archive.addfile(member)
            with self.assertRaisesRegex(ValueError,'special modes'):
                r.validate_tar(path)

    def test_runtime_link_escape_chain_and_parent_collision_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'data.tar'
            for target in ('/usr/bin/foreign','../../../escape','../share/doc/outside'):
                tar_fixture(path,[('usr/bin/x',tarfile.SYMTYPE,target)])
                with self.subTest(target=target),self.assertRaises(ValueError):
                    r.validate_tar(path)
            tar_fixture(path,[('usr/bin/a',tarfile.SYMTYPE,'b'),('usr/bin/b',tarfile.SYMTYPE,'a')])
            with self.assertRaisesRegex(ValueError,'non-symlink'):
                r.validate_tar(path)
            tar_fixture(path,[('usr/share/verilator',tarfile.DIRTYPE,''),
                              ('usr/bin',tarfile.SYMTYPE,'share/verilator'),('usr/bin/x',tarfile.REGTYPE,b'x')])
            with self.assertRaisesRegex(ValueError,'parent type collision'):
                r.validate_tar(path)

    def test_runtime_only_extraction_retains_opaque_docs_unmaterialized(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve(); path = base/'data.tar'; destination=base/'tool'; destination.mkdir()
            specs=[('./',tarfile.DIRTYPE,''),('usr/bin/tool',tarfile.REGTYPE,b'wrapper'),
                   ('usr/bin/alias',tarfile.SYMTYPE,'tool'),
                   ('usr/share/verilator/include/header.h',tarfile.REGTYPE,b'header'),
                   ('usr/share/doc/verilator/jquery.js',tarfile.SYMTYPE,'/usr/share/javascript/jquery/jquery.js'),
                   ('usr/share/doc/verilator/postinst',tarfile.REGTYPE,b'NOT EXECUTED')]
            tar_fixture(path,specs); rows=r.validate_tar(path)
            calls=[]; r.extract_runtime(path,rows,destination,lambda:calls.append(1))
            self.assertTrue(calls)
            self.assertEqual((destination/'usr/bin/tool').read_bytes(),b'wrapper')
            self.assertEqual((destination/'usr/bin/alias').read_bytes(),b'wrapper')
            self.assertFalse((destination/'usr/share/doc').exists())
            self.assertFalse(rows['usr/share/doc/verilator/jquery.js']['extracted'])
            r.verify_extracted(rows,destination)
            (destination/'usr/bin/unlisted').write_bytes(b'foreign')
            with self.assertRaisesRegex(ValueError,'permissions|closure'):
                r.verify_extracted(rows,destination)

    def test_control_scripts_are_data_not_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'control.tar'
            control=b'Package: verilator\nVersion: 5.020-1\nArchitecture: amd64\n'
            tar_fixture(path,[('control',tarfile.REGTYPE,control),('postinst',tarfile.REGTYPE,b'exit 99')])
            rows=r.validate_tar(path,control=True)
            self.assertEqual(r.validate_control(path,rows)['Version'],'5.020-1')
            self.assertFalse(rows['postinst']['extracted'])
            tar_fixture(path,[('control',tarfile.REGTYPE,control.replace(b'5.020-1',b'5.032-1'))])
            with self.assertRaisesRegex(ValueError,'control package'):
                r.validate_control(path,r.validate_tar(path,control=True))

    def test_no_redirects_or_native_promotion(self):
        with self.assertRaisesRegex(ValueError,'redirect refused'):
            r.NoRedirect().redirect_request(None,None,302,'',{},'https://foreign')
        source=Path(r.__file__).read_text()
        self.assertIn('native_queue_admitted=False,promotion_allowed=False',source)
        self.assertNotIn('extractall(',source)
        self.assertNotIn("'--extract'",source)
        self.assertNotIn('sudo',source[source.index('def execute('):source.index("policy='")])

    def test_download_exact_content_and_partial_failure_retention(self):
        class Response:
            status=200
            headers={}
            def __init__(self,body): self.stream=io.BytesIO(body)
            def geturl(self): return r.URL
            def read(self,count): return self.stream.read(count)
            def __enter__(self): return self
            def __exit__(self,*args): pass
        class Opener:
            def __init__(self,body): self.body=body
            def open(self,url,timeout):
                self.url=url; self.timeout=timeout
                return Response(self.body)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'package'
            opener=Opener(b'good')
            with patch.object(r.urllib.request,'build_opener',return_value=opener),\
                 patch.object(r,'PACKAGE_BYTES',4),patch.object(r,'PACKAGE_SHA',hashlib.sha256(b'good').hexdigest()):
                r.download(path,lambda:None)
                self.assertEqual(path.read_bytes(),b'good')
                self.assertEqual(opener.url,r.URL)
                self.assertEqual(opener.timeout,15)
                failure=Path(folder)/'failure'
                opener.body=b'wrong-and-too-big'
                with self.assertRaisesRegex(ValueError,'byte ceiling'):
                    r.download(failure,lambda:None)
                self.assertTrue(failure.is_file())
                self.assertTrue(path.is_file())

    def test_decompression_failure_keeps_logs_and_typed_step(self):
        class FailedChild:
            returncode=1
            def poll(self): return 1
        with tempfile.TemporaryDirectory() as folder:
            evidence=Path(folder); steps=[]
            with patch.object(r.subprocess,'Popen',return_value=FailedChild()) as launch:
                with self.assertRaisesRegex(ValueError,'return code'):
                    r.decompress('control',evidence/'package',evidence,lambda:None,steps)
                self.assertEqual(launch.call_args.args[0][1],'--ctrl-tarfile')
                self.assertEqual(launch.call_args.kwargs['env'],dict(PATH='/usr/bin:/bin',LC_ALL='C',LANG='C'))
            self.assertTrue((evidence/'control.tar').is_file())
            self.assertTrue((evidence/'control.stderr.log').is_file())
            self.assertEqual(steps[0]['returncode'],1)

    def test_debian_ar_magic_and_extra_member_rejected(self):
        def ar(entries):
            data=b'!<arch>\n'
            for name,content in entries:
                header=(f'{name+"/":<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(content):<10}`\n').encode()
                self.assertEqual(len(header),60)
                data+=header+content+(b'\n' if len(content)%2 else b'')
            return data
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'package'
            entries=[('debian-binary',b'2.0\n'),('control.tar.xz',b'ctrl'),('data.tar.zst',b'data')]
            path.write_bytes(ar(entries)); self.assertEqual(len(r.ar_inventory(path)),3)
            for bad in ([*entries,('foreign',b'x')],entries[:2],[(entries[0][0],b'3.0\n'),*entries[1:]]):
                path.write_bytes(ar(bad))
                with self.assertRaises(ValueError):
                    r.ar_inventory(path)
            path.write_bytes(b'not a deb')
            with self.assertRaisesRegex(ValueError,'ar magic'):
                r.ar_inventory(path)


if __name__ == '__main__':
    unittest.main()
