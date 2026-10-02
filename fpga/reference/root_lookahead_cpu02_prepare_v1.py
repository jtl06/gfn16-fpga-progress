"""One L16/field1 root-lookahead gate on the explicit aethia CPU0/2 profile.

Pure source preparation; no remote staging, scheduler, native tools or dispatch.
The frozen lint-first runner supplies every execution/evidence mechanism.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
PARENT='tools/native_source_gate_lint_v1.py'
PARENT_SHA='301aec824e091571ca2348cbbada903bbcbbd471b59962de42de8111eeae9f0b'
LAUNCHER='tools/native_source_gate_aethia_cpu02_v1.py'
PROFILE='aethia-physical-0-2-v1'
PARENT_PACKET='artifacts/root-lookahead-v1-prepared'
PARENT_MANIFEST_SHA='40562530962855f5566a5aabece43eaf5ff6f66077becc95dd3000ab25083b09'
SELF='reference/root_lookahead_cpu02_prepare_v1.py'
TEST='tests/test_native_source_gate_aethia_cpu02_v1.py'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,reason):
    if not ok:raise ValueError(reason)


def replace(text,old,new):
    require(text.count(old)==1,'unique CPU02 adapter anchor: '+old)
    return text.replace(old,new,1)


def launcher_source(original):
    require(hashlib.sha256(original.encode()).hexdigest()==PARENT_SHA,'frozen lint-first launcher SHA')
    text=replace(original,"SELF = '"+PARENT+"'","SELF = '"+LAUNCHER+"'")
    start=text.index("    'gfn16-pilot-c4': dict(");end=text.index('\n}\n',start)
    text=text[:start]+text[end:]  # This successor admits no cloud/old CPU profile.
    text=replace(text,"cpus=[4, 6]","cpus=[0, 2]")
    text=replace(text,"    profile = PROFILES[manifest['host']]",
        "    require(manifest.get('cpu_profile') == '"+PROFILE+"', 'explicit CPU0/2 profile required')\n    profile = PROFILES[manifest['host']]")
    text=replace(text,"    quota = (directory / 'cpu.max').read_text().split()",
        "    quota = (directory / 'cpu.max').read_text().split()\n"
        "    require((directory / 'memory.swap.max').read_text().strip() == '0', 'requires cgroup no swap')")
    text=replace(text,"    require(len(cpus) == 2 and len({tuple(row) for row in cores}) == 2, 'two distinct physical cores')",
        "    require(cpus == [0, 2] and cores == [[0, 0], [0, 1]], 'exact observed CPU0/2 physical topology')\n"
        "    other_cores = []\n"
        "    for cpu in (4, 6):\n"
        "        topology = Path('/sys/devices/system/cpu') / f'cpu{cpu}/topology'\n"
        "        other_cores.append([int((topology / key).read_text()) for key in ('physical_package_id', 'core_id')])\n"
        "    require(other_cores == [[0, 2], [0, 3]], 'CPU4/6 topology drift; separate slot required')\n"
        "    require(not {tuple(row) for row in cores} & {tuple(row) for row in other_cores}, 'CPU0/2 overlaps CPU4/6 physical cores')")
    text=replace(text,"return dict(cgroup=group, memory_max_bytes=int(memory), cpu_max=quota, affinity=actual, physical_cores=cores)",
        "return dict(cgroup=group, memory_max_bytes=int(memory), swap_max_bytes=0, cpu_max=quota, affinity=actual, physical_cores=cores, excluded_cpu46_physical_cores=other_cores)")
    # A user step named lint would collide with the newly inherited log name.
    text=replace(text,"n not in ('build', 'probe', 'verilator-version', 'compiler-version')",
        "n not in ('lint', 'build', 'probe', 'verilator-version', 'compiler-version')")
    return text


def prepare(output,root=ROOT):
    require(not (root/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    parent=root/PARENT_PACKET;old_manifest=parent/'aethia-component-l16-f1.json'
    require(sha(old_manifest)==PARENT_MANIFEST_SHA,'frozen L16 field1 manifest SHA')
    manifest=json.loads(old_manifest.read_text());source=parent/'source/fpga'
    actual={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}
    require(actual==manifest['sources'],'exact parent snapshot closure')
    require((root/LAUNCHER).read_text()==launcher_source((root/PARENT).read_text()),'only explicit CPU02/noSwap delta')
    require(manifest['build']['parameters']==dict(LANES=16,P=104857601,Q=4190109697,TAG_W=32),'first-field L16 geometry')
    output=Path(output).resolve();require(not output.exists(),'fresh output only')
    dest=output/'source/fpga';shutil.copytree(source,dest)
    for name in (LAUNCHER,SELF,TEST):
        target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
    lineage=dest/'evidence/root-lookahead-parent-manifest.json';lineage.parent.mkdir()
    shutil.copyfile(old_manifest,lineage)
    closure={p.relative_to(dest).as_posix():sha(p) for p in dest.rglob('*') if p.is_file()}
    require(all(closure[name]==pin for name,pin in actual.items()),'parent sources preserved')
    base='/home/jtl/gfn-fpga-lab/agent-work/root-lookahead-cpu02-v1'
    manifest.update(cpu_profile=PROFILE,source_root=base+'/snapshot-v1/fpga',output_parent=base,sources=closure)
    manifest['admission'].update(launcher=LAUNCHER,cpus=[0,2],cpu_profile=PROFILE,
        concurrent_runtime_only='Compilation and lint remain under the existing exclusive global compile lock.')
    path=output/'manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    with tarfile.open(output/'source.tar.gz','x:gz') as archive:
        for name in sorted(closure):archive.add(dest/name,arcname='fpga/'+name,recursive=False)
    report=dict(status='prepared_not_executed',parent_manifest_sha256=PARENT_MANIFEST_SHA,
        launcher_parent_sha256=PARENT_SHA,launcher_sha256=sha(root/LAUNCHER),
        manifest_sha256=sha(path),archive_sha256=sha(output/'source.tar.gz'),
        archive_bytes=(output/'source.tar.gz').stat().st_size,source_members=len(closure),
        cpu_profile=PROFILE,topology_observation=dict(host='aethia',cpus={
            '0':dict(package=0,core=0,siblings='0-1'),'2':dict(package=0,core=1,siblings='2-3'),
            '4':dict(package=0,core=2,siblings='4-5'),'6':dict(package=0,core=3,siblings='6-7')}),
        scope='Only L16 first-field root-lookahead component control; no other tests automatically admitted.',
        limits='CPU0/2 two physical cores, external200%/4GiB/noSwap/3700s+15s grace; frozen inner3600s, command1800s, existing exclusive compile lock; main dispatch only.')
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output),indent=2))
