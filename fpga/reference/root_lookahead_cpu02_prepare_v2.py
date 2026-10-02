"""Additive mandatory -Wall lint-first successor for the single F2 CPU0/2 gate.

All original policy/component sources and packets remain immutable. Preparation
only: main owns remote staging, slot admission and execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
PARENT='tools/native_source_gate_aethia_cpu02_v1.py'
PARENT_SHA='a0ec27d3221c5a9a3f4452c022aac7936d89bf560f6e2d7073585a20cecc6631'
LAUNCHER='tools/native_source_gate_aethia_cpu02_v2.py'
PARENT_PACKET='artifacts/root-lookahead-cpu02-v1-prepared'
PARENT_MANIFEST_SHA='5683f79b97baac69a3418c09d499f04ccb1d1485766b7750c88a261901416c2f'
SELF='reference/root_lookahead_cpu02_prepare_v2.py'
TEST='tests/test_native_source_gate_aethia_cpu02_v2.py'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,reason):
    if not ok:raise ValueError(reason)


def launcher_source(original):
    require(hashlib.sha256(original.encode()).hexdigest()==PARENT_SHA,'frozen CPU02 launcher SHA')
    old="SELF = '"+PARENT+"'";require(original.count(old)==1,'launcher identity anchor')
    text=original.replace(old,"SELF = '"+LAUNCHER+"'",1)
    old="lint = [str(toolpaths['verilator']), '--lint-only', '--threads', '1',"
    require(text.count(old)==1,'single locked lint anchor')
    return text.replace(old,"lint = [str(toolpaths['verilator']), '--lint-only', '-Wall', '--threads', '1',",1)


def prepare(output,root=ROOT):
    require(not (root/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    parent=root/PARENT_PACKET;path=parent/'manifest.json'
    require(sha(path)==PARENT_MANIFEST_SHA,'frozen CPU02 component manifest')
    manifest=json.loads(path.read_text());source=parent/'source/fpga'
    original={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}
    require(original==manifest['sources'],'parent exact source closure')
    require((root/LAUNCHER).read_text()==launcher_source((root/PARENT).read_text()),'only SELF and mandatory Wall lint delta')
    output=Path(output).resolve();require(not output.exists(),'fresh output only')
    target=output/'source/fpga';shutil.copytree(source,target)
    for name in (LAUNCHER,SELF,TEST):
        dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,dest)
    lineage=target/'evidence/root-lookahead-cpu02-v1-manifest.json';shutil.copyfile(path,lineage)
    sources={p.relative_to(target).as_posix():sha(p) for p in target.rglob('*') if p.is_file()}
    require(all(sources[name]==pin for name,pin in original.items()),'all predecessor sources unchanged')
    base='/home/jtl/gfn-fpga-lab/agent-work/root-lookahead-cpu02-wall-v2'
    manifest.update(source_root=base+'/snapshot-v1/fpga',output_parent=base,sources=sources)
    manifest['admission'].update(launcher=LAUNCHER,lint_first=True,lint_all_warnings=True,
        lint_warning_waivers=[],lint_success_required_before_build=True,
        limitation='Exact same top, HDL parameters, ordered SV sources and pinned native tool; -Wall lint is mandatory and warning-fatal under the shared compile lock. No predecessor warning waiver.')
    out_manifest=output/'manifest.json';out_manifest.write_text(json.dumps(manifest,indent=2)+'\n')
    with tarfile.open(output/'source.tar.gz','x:gz') as archive:
        for name in sorted(sources):archive.add(target/name,arcname='fpga/'+name,recursive=False)
    result=dict(status='prepared_not_executed',parent_manifest_sha256=PARENT_MANIFEST_SHA,
        launcher_parent_sha256=PARENT_SHA,launcher_sha256=sha(root/LAUNCHER),manifest_sha256=sha(out_manifest),
        archive_sha256=sha(output/'source.tar.gz'),archive_bytes=(output/'source.tar.gz').stat().st_size,
        source_members=len(sources),original_sources_preserved=len(original),
        exact_build_probe_steps_unchanged=True,mandatory_lint='--lint-only -Wall, no warning suppressions, under existing compile lock before build',
        limits='aethiaCPU0/2; two distinct physical cores disjoint4/6; <=200%/4GiB/noSwap; inherited floors/lock/timeouts/evidence',
        scope='Only root-lookahead L16 first-field control; main dispatch only; no native execution by preparer.')
    (output/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output),indent=2))
