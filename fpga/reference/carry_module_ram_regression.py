"""Module-scoped carry RAM equivalence and protocol checks; aethia only."""
from pathlib import Path
import argparse
import hashlib
import json
import socket
import subprocess
import time

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--vectors',type=Path,required=True)
    ap.add_argument('--tiny-vectors',type=Path,required=True)
    ap.add_argument('--mutations',action='store_true')
    args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    ram=root/'rtl/kernel/genefer_sp_ram.sv'
    shared=[root/'rtl/kernel/genefer_div96_recip_prefix.sv',root/'rtl/kernel/genefer_carry_transfer_tree.sv',ram]
    tops={kind:root/f'rtl/kernel/genefer_carry_prefix_{kind}_ram.sv' for kind in ['wide','vector']}
    cpp={kind:root/f'rtl/tb/carry_prefix_{kind}_ram.cpp' for kind in tops}
    ram_cpp=root/'rtl/tb/sp_ram.cpp'
    files=shared+list(tops.values())+list(cpp.values())+[ram_cpp,Path(__file__),args.vectors,args.tiny_vectors]
    report={'host':socket.gethostname(),'status':'running','steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    def run(name,cmd,reject=False):
        then=time.monotonic();p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(p.stdout)
        report['steps'].append({'name':name,'returncode':p.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,p.returncode,p.stdout[-700:],flush=True)
        if not reject and p.returncode:raise RuntimeError(name+' failed')
        if reject and (p.returncode==0 or not any(s in p.stdout for s in ['RAM combinational/reset hold mismatch','RAM registered data/hold mismatch'])):
            raise RuntimeError(name+' mutant not rejected for RAM behavior')
    def build(name,top,sources,bench,params,flags=''):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module',top,'--Mdir',str(directory),
                  *params,*(['-CFLAGS',flags] if flags else []),*map(str,sources),str(bench)])
        return str(directory/f'V{top}')
    try:
        for width in [33,96]:
            for aw,depth in [(1,1),(6,64)]:
                exe=build(f'build-ram-w{width}-d{depth}','genefer_sp_ram',[ram],ram_cpp,
                          [f'-GWIDTH={width}',f'-GAW={aw}',f'-GDEPTH={depth}'],f'-DTEST_WIDTH={width} -DTEST_DEPTH={depth}')
                run(f'test-ram-w{width}-d{depth}',[exe])
        for kind,lanes_set in [('wide',[4,8,16]),('vector',[4,16])]:
            for lanes in lanes_set:
                for aw,vectors in [(16,args.vectors),(1,args.tiny_vectors)]:
                    top=f'genefer_carry_prefix_{kind}_ram';name=f'{kind}-w{lanes}-aw{aw}'
                    exe=build('build-'+name,top,shared+[tops[kind]],cpp[kind],[f'-GLANES={lanes}',f'-GAW={aw}'],f'-DTEST_LANES={lanes} -DTEST_AW={aw}')
                    run('test-'+name,[exe,str(vectors)])
        if args.mutations:
            for name,old,new in [
                ('reset-gate','if(rst_n && en)begin','if(en)begin'),
                ('enable-gate','if(rst_n && en)begin','if(rst_n)begin'),
                ('write-hold','else read_data<=mem[addr];','read_data<=mem[addr];')]:
                text=ram.read_text()
                if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                path=out/f'mutant-{name}.sv';path.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,'genefer_sp_ram',[path],ram_cpp,['-GWIDTH=96','-GAW=6','-GDEPTH=64'],'-DTEST_WIDTH=96 -DTEST_DEPTH=64')
                run('reject-'+name,[exe],True)
        report['status']='passed'
    except BaseException as exc:
        report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
