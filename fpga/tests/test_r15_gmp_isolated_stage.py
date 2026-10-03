"""Execute the real flat-transport stager, never a compiler/model/candidate."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

from fpga.tools import native_class_package_v4 as package,native_package_v6 as stage
from fpga.tests import test_r15_f16_existing_native as fixtures

ROOT=Path(__file__).resolve().parents[1]
SIDECARS=('native_package_v6.py','native_package_v5.py','native_package_v3.py','native_package_v2.py')
HARNESS=r'''
import copy,hashlib,json,pathlib,sys
sys.path.insert(0,sys.argv[1])
import native_package_v6 as stage
worker=stage.worker();inspect=worker.inspect_archive
base=pathlib.Path(sys.argv[5]).resolve()
def measured_host_placement(*args):
    payload,ticket,manifest,profile=inspect(*args)
    # Exact source/profile/namespace guards above are real. Only the Linux
    # host/user and test destination mapping are mocked; no resource waiver.
    profile=copy.deepcopy(profile);ticket=copy.deepcopy(ticket)
    profile.update(base=str(base),scratch_base=str(base/'scratch'),lock=str(base/'compile.lock'))
    ticket['native_root']=str(base/'jobs'/ticket['id'])
    return payload,ticket,manifest,profile
worker.inspect_archive=measured_host_placement
worker.host_check=lambda profile:None
result=worker.stage(pathlib.Path(sys.argv[2]),sys.argv[3],sys.argv[4])
root=pathlib.Path(result['root'])
assert result['status']=='staged_exact_inputs'
assert (root/'capture/source/fpga/tools/native_class_v2.py').is_file()
assert (root/'output').is_dir()
assert not (root/'queue-report.json').exists()
assert not (root/'output/native').exists()
assert not (pathlib.Path(sys.argv[1])/'native_class_v2.py').exists()
print(json.dumps({'status':result['status'],'files':result['files'],'no_runtime_import':True,
 'actual_filesystem_stage':True,'host_measurements_mocked':True,'native_commands':False}))
'''


def mutate_manifest(archive,out,change):
    # Produce internally consistent metadata mutation archives, never inputs
    # submitted to a worker. All source bytes and frozen policy stay unchanged.
    with tarfile.open(archive,'r:gz') as source:
        payload={member.name:source.extractfile(member).read() for member in source.getmembers()}
    manifest=json.loads(payload['manifest.json']);change(manifest)
    raw=(json.dumps(manifest,indent=2)+'\n').encode();pin=hashlib.sha256(raw).hexdigest()
    payload['manifest.json']=raw;payload['capture/approved-manifest.json']=raw
    ticket=json.loads(payload['ticket.json']);ticket['manifest_sha256']=pin
    payload['ticket.json']=(json.dumps(ticket,indent=2)+'\n').encode()
    capture=json.loads(payload['capture/capture.json']);capture['manifest_sha256']=pin
    payload['capture/capture.json']=(json.dumps(capture,indent=2)+'\n').encode()
    with tarfile.open(out,'x:gz') as target:
        for name,raw in sorted(payload.items()):
            member=tarfile.TarInfo(name);member.size=len(raw);member.mode=0o644
            target.addfile(member,io.BytesIO(raw))
    return hashlib.sha256(out.read_bytes()).hexdigest(),hashlib.sha256(payload['ticket.json']).hexdigest()


class IsolatedStageTests(unittest.TestCase):
    def test_actual_flat_transport_cli_and_filesystem_stage_defaults_and_gmp_both_profiles(self):
        roles=(ROOT/'results/throughput-20261003/trackS-r15-storage-ram-v1/aw8-normal-v2',
               ROOT/'results/throughput-20261003/r15-host-window-gmp-native-v1/normal',
               ROOT/'results/throughput-20261003/r15-host-window-application-gmp-native-v1/normal')
        with tempfile.TemporaryDirectory(prefix='r15-flat-stage-proof-',dir=ROOT/'artifacts') as temporary:
            out=Path(temporary).resolve();flat=out/'qstage';flat.mkdir()
            for name in SIDECARS:shutil.copyfile(ROOT/'tools'/name,flat/name)
            self.assertEqual({p.name for p in flat.iterdir()},set(SIDECARS))
            for index,rolepath in enumerate(roles):
                role=json.loads((rolepath/'manifest.json').read_bytes())
                budget=fixtures.R15ExistingF16Tests.fixture_budget(self,out,role)
                budgetpath=out/f'budget-{index}.json';budgetpath.write_text(json.dumps(budget))
                for pair in ('1213','1415'):
                    profile='azure-f16-static'+pair+'-v1';packet=out/f'packet-{index}-{pair}'
                    prepared=package.prepare(rolepath/'manifest.json',Path(role['source_root']),profile,
                        f'isolated-source-{index}-{pair}','run',packet,budgetpath)
                    archive=packet/'package.tar.gz';args=[str(archive),prepared['archive_sha256'],prepared['ticket_sha256']]
                    # Actual public CLI with precisely transported sidecars.
                    # Mac is not the admitted Linux host: it must reach the
                    # real host guard, not fail from missing runtime imports.
                    cli=subprocess.run([sys.executable,'-I','-B',str(flat/'native_package_v6.py'),'stage',
                        '--archive',args[0],'--archive-sha256',args[1],'--ticket-sha256',args[2]],
                        cwd=flat,capture_output=True,text=True,timeout=60)
                    self.assertNotEqual(cli.returncode,0)
                    self.assertIn('approved staging host/user',cli.stderr)
                    self.assertNotIn('FileNotFoundError',cli.stderr)
                    # Execute the same real stage/extraction/locks/receipt,
                    # substituting only host/user and a private test target.
                    native=out/f'native-{index}-{pair}'
                    run=subprocess.run([sys.executable,'-I','-B','-c',HARNESS,str(flat),*args,str(native)],
                        cwd=flat,capture_output=True,text=True,timeout=60)
                    self.assertEqual(run.returncode,0,run.stderr)
                    self.assertEqual(json.loads(run.stdout)['status'],'staged_exact_inputs')
                    staged=next((native/'jobs').iterdir())
                    for name,pin in role['sources'].items():
                        self.assertEqual(hashlib.sha256((staged/'capture/source/fpga'/name).read_bytes()).hexdigest(),pin)
                    if index in (1,2) and pair=='1213':
                        self.check_refusals(flat,archive,out)

    def check_refusals(self,flat,archive,out):
        changes=(('flags',lambda m:m['build'].update(ldflags=['-lgmpxx','-lgmp','-lm']),'only exact GMP linker flags'),
                 ('metadata',lambda m:m['metadata']['r15_native_gmp'].update(fixture_sha256='0'*64),'source-pinned'),
                 ('inventory',lambda m:m['metadata']['r15_native_gmp']['inventory'].update(sha256='0'*64),'source-pinned'))
        for label,change,error in changes:
            changed=out/(archive.parent.name+'-'+label+'-mutant.tar.gz');sha,ticket=mutate_manifest(archive,changed,change)
            run=subprocess.run([sys.executable,'-I','-B',str(flat/'native_package_v6.py'),'stage',
                '--archive',str(changed),'--archive-sha256',sha,'--ticket-sha256',ticket],
                cwd=flat,capture_output=True,text=True,timeout=60)
            self.assertNotEqual(run.returncode,0);self.assertIn(error,run.stderr)
            self.assertNotIn('approved staging host/user',run.stderr)


if __name__=='__main__':unittest.main()
