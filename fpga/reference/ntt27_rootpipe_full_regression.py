"""AW16/L64-only follow-on gate: j4, serial model, unchanged rootpipe oracle.

Requires the completed small/fault gate. No RTL/bench/helper edits, cache hits,
small-model rebuilds or mutation rebuilds are performed by this profile.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import socket

from .ntt27_rootpipe_regression import (NTT27RootpipeLab, bench_proof, validate_files,
    EXPERIMENT_PRIMES, cases_for, centered_crt, encode, cache_context)

TOP='genefer_ntt_banked27_rootpipe_engine'
ENGINE_SHA='cab41579a4b96793f52c31a2864f74aeab3d023f23b50f5c8acce368f07d1967'
BENCH_SHA='a71dbb8a374f0fc0e40c0dd9cd505a5201ba64cf4ec08cb1249db039665ee999'
HARNESS_SHA='1d2544bed56e7e0d6fbd4184928bda795508e21fa618715d3814435443040bd3'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resources(directory):
    available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                       if line.startswith('MemAvailable:')))*1024
    group=next(line.split(':',2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
               if line.startswith('0::'))
    cg=Path('/sys/fs/cgroup')/group.lstrip('/')
    return dict(free_disk_bytes=shutil.disk_usage(directory).free,available_ram_bytes=available,
        cgroup=group,cpu_max=(cg/'cpu.max').read_text().strip(),
        memory_max=(cg/'memory.max').read_text().strip(),
        memory_current_bytes=int((cg/'memory.current').read_text()),
        memory_peak_bytes=int((cg/'memory.peak').read_text()))


class FullLab(NTT27RootpipeLab):
    def build(self,name,top,sources,cpp,params=None):
        before=resources(self.output)
        if before['free_disk_bytes']<10<<30 or before['available_ram_bytes']<6<<30:
            raise RuntimeError('new build blocked by disk/RAM guard')
        if before['memory_max']!=str(6<<30) or before['cpu_max']!='400000 100000':
            raise RuntimeError('full gate requires explicit CPU400/MemoryMax6G scope')
        directory=self.output/name
        if directory.exists():raise RuntimeError('refusing to overwrite earlier build evidence')
        command=[self.verilator,'--cc','--exe','--build','-j','4','--threads','1',
                 '--top-module',top,'--Mdir',str(directory),*(params or []),*map(str,sources),str(cpp)]
        command=['flock','--timeout','600',str(self.compile_lock),*command]
        self.run(name,command)
        after=resources(self.output)
        executable=directory/f'V{top}'
        record=dict(name=name,top=top,compile_workers=4,model_threads=1,
            sources={str(p.relative_to(self.root)):digest(p) for p in [*sources,cpp]},
            parameters=params or [],executable=str(executable),executable_sha256=digest(executable),
            resources_before=before,resources_after=after)
        self.report.setdefault('builds',[]).append(record)
        print('RESOURCE_AFTER_BUILD',json.dumps(after,sort_keys=True),flush=True)
        return str(executable)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--small-report',required=True,type=Path)
    parser.add_argument('--compile-lock',required=True,type=Path)
    args=parser.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    root=Path(__file__).resolve().parents[1]
    for name,sha in ((f'rtl/kernel/{TOP}.sv',ENGINE_SHA),
                     ('rtl/tb/ntt_banked27_rootpipe_engine.cpp',BENCH_SHA),
                     ('reference/ntt27_rootpipe_regression.py',HARNESS_SHA)):
        if digest(root/name)!=sha:raise RuntimeError('frozen source mismatch '+name)
    small_path=args.small_report.resolve();small=json.loads(small_path.read_text())
    if small['status']!='passed' or small['requested_lanes']!=[1,64] or not small['quick']:
        raise RuntimeError('requires complete L1/L64 small gate')
    small_records={}
    for variant in small['variants']:
        path=small_path.parent/variant['report'];report=json.loads(path.read_text())
        if report['status']!='passed' or not all(s['passed'] for s in report['steps']):
            raise RuntimeError('small logical step failed')
        for name,sha in report['source_sha256'].items():
            if digest(root/name)!=sha:raise RuntimeError('small source changed '+name)
        small_records[str(path)]={'sha256':digest(path),'lanes':variant['lanes']}
    args.output.mkdir(parents=True,exist_ok=False)
    lab=FullLab(args.output,'verilator');lab.lanes=64;lab.compile_lock=args.compile_lock.resolve()
    lab.report.update(profile='rootpipe-aw16-l64-j4-runtime1-v1',compile_workers=4,model_threads=1,
        memory_limit_bytes=6<<30,small_gate={'path':str(small_path),'sha256':digest(small_path),'variants':small_records},
        profile_delta='AW16-only; j2 to j4; explicit threads1; exact small RTL/bench/oracles unchanged')
    try:
        lab.report['structural_proof']=validate_files(root);lab.report['bench_proof']=bench_proof(root)
        _,toolchain,environment=cache_context(args.output/'unused-cache-record-only')
        tools_path=args.output/'toolchain.json'
        tools_path.write_text(json.dumps(dict(toolchain=toolchain,environment=environment),indent=2)+'\n')
        lab.report['toolchain_manifest']={'path':str(tools_path),'sha256':digest(tools_path)}
        cases=cases_for(16)+[('max-base1e9',[999999999]*65536,1000000000)];planes=[]
        for field in range(3):
            exe=lab.build_ntt(field,16,64)
            planes.append(lab.cached_squares(field,16,exe,cases))
            lab.canonical_checks(field,16,exe)
            for lg in range(1,17):lab.transform_test(field,lg,exe,'-ntt27-aw16')
            lab.resets(field,exe,64)
        for i,(name,digits,base) in enumerate(cases):
            coeff=[centered_crt((planes[f][i][j] for f in range(3)),EXPERIMENT_PRIMES) for j in range(65536)]
            modulus=pow(base,65536)+1
            if encode(coeff,base)%modulus!=pow(encode(digits,base),2,modulus):
                raise RuntimeError('full bigint square mismatch')
            lab.report.setdefault('integer_squares',[]).append(dict(n=65536,name=name,base=base,passed=True))
        for name,sha in lab.report['source_sha256'].items():
            if digest(root/name)!=sha:raise RuntimeError('source changed '+name)
        if not all(s['passed'] for s in lab.report['steps']):raise RuntimeError('failed logical gate step')
        lab.report['status']='passed'
    except BaseException as error:
        lab.report.update(status='failed',error=repr(error));raise
    finally:
        lab.report['evidence_sha256']={str(p.relative_to(lab.output)):digest(p) for p in lab.output.iterdir()
            if p.suffix in ('.log','.txt')}
        (lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')


if __name__=='__main__':main()
