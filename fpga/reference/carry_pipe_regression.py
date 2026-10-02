"""Retimed prefix normalization stage/tag checks; aethia only."""
from pathlib import Path
import argparse,hashlib,json,socket,subprocess,time

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--vectors',type=Path,required=True);ap.add_argument('--tiny-vectors',type=Path,required=True)
    ap.add_argument('--mutations',action='store_true');a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    shared=[root/'rtl/kernel'/s for s in ['genefer_div_recip_narrow.sv','genefer_carry_transfer_tree.sv','genefer_sp_ram.sv']]
    tops={k:root/f'rtl/kernel/genefer_carry_prefix_{k}_pipe.sv' for k in ['wide','vector']}
    cpp={k:root/f'rtl/tb/carry_prefix_{k}_pipe.cpp' for k in tops}
    files=shared+list(tops.values())+list(cpp.values())+[Path(__file__),a.vectors,a.tiny_vectors]
    report={'status':'running','host':socket.gethostname(),'steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    vectors=out/'vectors.txt';tiny=out/'vectors-aw1.txt'
    vectors.write_text(a.vectors.read_text());tiny.write_text(a.tiny_vectors.read_text())
    with vectors.open('a') as f:
        for label in ['emit4','emit5','emit6','drain']:
            f.write(f'ABORT {label} 8 604832956\n'+' '.join(['123456']*256)+'\n')
            f.write(f'OK after-{label} 8 604832956\n'+' '.join(['0']*256)+'\n'+' '.join(['0']*256)+'\n')
    report['generated_vectors']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [vectors,tiny]}
    def run(name,cmd,reject=None):
        then=time.monotonic();p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(p.stdout);report['steps'].append({'name':name,'returncode':p.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,p.returncode,p.stdout[-650:],flush=True)
        if reject is None and p.returncode:raise RuntimeError(name+' failed')
        if reject is not None and (p.returncode==0 or not any(t in p.stdout for t in reject)):raise RuntimeError(name+' mutant not rejected')
    def build(name,kind,lanes,aw,source=None):
        top=f'genefer_carry_prefix_{kind}_pipe';directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module',top,'--Mdir',str(directory),
                  f'-GLANES={lanes}',f'-GAW={aw}','-CFLAGS',f'-DTEST_LANES={lanes} -DTEST_AW={aw}',*map(str,shared+[source or tops[kind]]),str(cpp[kind])])
        return str(directory/f'V{top}')
    try:
        for kind,lanes_set in [('wide',[4,8,16]),('vector',[4,16])]:
            for lanes in lanes_set:
                for aw,v in [(16,vectors),(1,tiny)]:
                    name=f'{kind}-w{lanes}-aw{aw}';exe=build('build-'+name,kind,lanes,aw);run('test-'+name,[exe,str(v)])
        if a.mutations:
            defects=[
                ('leaf-tag',"leaf_row<=RW'(written)","leaf_row<=RW'(issue)"),
                ('small-tag','digit_small[g]<=leaf_small[g]','digit_small[g]<=small_q[g]'),
                ('carry-tag',"$signed({31'b0,digit_in[g]})","$signed({31'b0,lane_in[g]})"),
                ('output-tag','emit_row<=digit_row','emit_row<=leaf_row'),
                ('early-done',"if(emit_valid && emit_row==RW'(groups-1))","if(digit_valid && digit_row==RW'(groups-1))"),
                ('feedback-valid','if(leaf_valid)current_carry<=next_group','if(small_d)current_carry<=next_group')]
            for name,old,new in defects:
                text=tops['wide'].read_text()
                if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                path=out/f'mutant-{name}.sv';path.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,'wide',4,16,path)
                run('reject-'+name,[exe,str(vectors)],['carry mismatch','carry cycle regression','unexpected error','completion mismatch'])
        report['status']='passed'
    except BaseException as exc:report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
