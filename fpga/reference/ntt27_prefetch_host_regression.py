"""Isolated 16/64 prefetch adapter gate; fresh inherited value oracles, aethia only."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import resource
import shutil
import socket
import time
from .ntt27_prefetch_regression import PrefetchLab, LOCK
from .ntt27_generated_regression import PRIMES,SOURCES
from .ntt_cached_regression import cases_for,encode
from .rns_reference import centered_crt

TOP='genefer_ntt_banked27_prefetch_host_engine'


class AdapterLab(PrefetchLab):
    def build_ntt(self,field,aw,lanes=64,override=None):
        if lanes!=64:raise ValueError('only64 arithmetic lanes approved')
        if shutil.disk_usage(self.root).free<10<<30:raise RuntimeError('free disk below10GiB')
        prime=PRIMES[field]
        paths=[self.root/'rtl/kernel'/s for s in SOURCES[:-1]]
        paths += [self.root/'rtl/kernel/genefer_ntt_banked27_prefetch_engine.sv',
                  override or self.root/'rtl/kernel'/f'{TOP}.sv']
        name=f'build-p{field+1}-aw{aw}'+('-'+override.parent.name if override else '')
        with open(LOCK,'a') as lock:
            began=time.monotonic()
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()-began>900:raise RuntimeError('compile lock timeout')
                    time.sleep(.25)
            exe=self.build(name,TOP,paths,self.root/'rtl/tb/ntt_banked27_prefetch_host_engine.cpp',
                [f'-GAW={aw}','-GLANES=64','-GHOST_LANES=16',f'-GP={prime.p}',f'-GQ={prime.q}',
                 '-CFLAGS',f'-DNTT_LANES=64 -DNTT_AW={aw} -DNTT_P={prime.p}u'])
        self.report.setdefault('executables',[]).append(dict(path=exe,
            sha256=hashlib.sha256(Path(exe).read_bytes()).hexdigest(),field=field+1,aw=aw,ntt_lanes=64,host_lanes=16))
        return exe


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--aw',type=int,nargs='+',default=[1,5,8])
    args=parser.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('RTL only on aethia')
    if args.output.exists():raise FileExistsError(args.output)
    if any(aw not in range(1,17) for aw in args.aw):raise ValueError('invalidAW')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    lab=AdapterLab(args.output,'verilator')
    try:
        for aw in args.aw:
            cases=cases_for(aw);planes=[]
            for field in range(3):
                exe=lab.build_ntt(field,aw)
                for lg in sorted({1,min(5,aw),aw}):lab.transforms(field,aw,lg,64,exe,lg==aw)
                planes.append(lab.squares(field,aw,aw,64,exe,cases))
                lab.resets(field,aw,64,exe)
                lab.size_reload(field,aw,64,exe)
            for i,(_,digits,base) in enumerate(cases):
                coeff=[centered_crt((planes[f][i][j] for f in range(3)),PRIMES) for j in range(1<<aw)]
                modulus=pow(base,1<<aw)+1
                assert encode(coeff,base)%modulus==pow(encode(digits,base),2,modulus)
        for path,digest in lab.report['source_sha256'].items():
            if hashlib.sha256((lab.root/path).read_bytes()).hexdigest()!=digest:raise RuntimeError('source changed '+path)
        lab.report.update(status='passed',source_hashes_rechecked=True,whole_integer_crt=True)
    except BaseException as error:
        lab.report.update(status='failed',failure=repr(error));raise
    finally:(lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')


if __name__=='__main__':main()
