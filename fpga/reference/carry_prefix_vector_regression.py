"""Vector-host carry interface and preserved arithmetic regression, aethia only."""
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
    ap.add_argument('--lanes',type=int,nargs='+',default=[4,16])
    ap.add_argument('--mutations',action='store_true')
    args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    src=[root/'rtl/kernel/genefer_div96_recip_prefix.sv',root/'rtl/kernel/genefer_carry_transfer_tree.sv',root/'rtl/kernel/genefer_carry_prefix_vector.sv']
    cpp=root/'rtl/tb/carry_prefix_vector.cpp'
    files=src+[cpp,Path(__file__),args.vectors,args.tiny_vectors]
    report={'host':socket.gethostname(),'status':'running','lanes':args.lanes,'steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    def run(name,cmd,reject=False):
        then=time.monotonic();p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(p.stdout)
        report['steps'].append({'name':name,'returncode':p.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,p.returncode,p.stdout[-700:],flush=True)
        if not reject and p.returncode:raise RuntimeError(name+' failed')
        if reject and (p.returncode==0 or not any(s in p.stdout for s in ['host valid/mask/error/priority mismatch','scalar host data mismatch','vector host data mismatch','start host suppression mismatch','busy host response leaked'])):
            raise RuntimeError(name+' mutant not rejected for expected host reason')
    def build(name,lanes,aw,sources=src):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module','genefer_carry_prefix_vector','--Mdir',str(directory),
                  f'-GLANES={lanes}',f'-GAW={aw}','-CFLAGS',f'-DTEST_LANES={lanes} -DTEST_AW={aw}',*map(str,sources),str(cpp)])
        return str(directory/'Vgenefer_carry_prefix_vector')
    try:
        for lanes in args.lanes:
            for aw,vectors in [(16,args.vectors),(1,args.tiny_vectors)]:
                exe=build(f'build-w{lanes}-aw{aw}',lanes,aw)
                run(f'test-w{lanes}-aw{aw}',[exe,str(vectors)])
        if args.mutations:
            mutations=[
                ('priority','if(vector_request)begin','if(vector_request && !load_we)begin'),
                ('alignment',"(32'(vector_addr)&32'(LANES-1))==0 && ",''),
                ('range'," && 32'(vector_addr)<host_n",''),
                ('mask','vector_lane_mask[h] &&',"1'b1 &&"),
                ('packing','vector_write_data[g*96+:96]','vector_write_data[(LANES-1-g)*96+:96]'),
                ('response-mask',"vector_ok ? effective_mask : '0","vector_ok ? vector_lane_mask : '0"),
                ('busy-error','host_error<=state==IDLE && !start && vector_request && !vector_ok','host_error<=!start && vector_request && !vector_ok'),
                ('start-error','host_error<=state==IDLE && !start && vector_request && !vector_ok','host_error<=state==IDLE && vector_request && !vector_ok')]
            for name,old,new in mutations:
                text=src[2].read_text()
                if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                path=out/f'mutant-{name}.sv';path.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,4,16,src[:2]+[path])
                run('reject-'+name,[exe,str(args.vectors)],True)
        report['status']='passed'
    except BaseException as exc:
        report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
