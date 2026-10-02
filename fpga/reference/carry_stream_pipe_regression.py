"""Ordered CRT coefficient stream into carry; aethia-only, two build workers."""
from pathlib import Path
import argparse,hashlib,json,resource,socket,subprocess,time

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--vectors',type=Path,required=True);ap.add_argument('--tiny-vectors',type=Path,required=True)
    ap.add_argument('--lanes',type=int,nargs='+',default=[4,16]);ap.add_argument('--mutations',action='store_true')
    a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    shared=[root/'rtl/kernel'/s for s in ['genefer_div_recip_narrow.sv','genefer_sp_ram.sv']]
    top='genefer_carry_prefix_stream_pipe';src=root/f'rtl/kernel/{top}.sv';cpp=root/'rtl/tb/carry_prefix_stream_pipe.cpp'
    size_cpp=root/'rtl/tb/carry_stream_pipe_size.cpp'
    scan_cpp=root/'rtl/tb/carry_stream_scan_pipe.cpp'
    files=shared+[src,cpp,size_cpp,scan_cpp,Path(__file__),a.vectors,a.tiny_vectors]
    report={'status':'running','host':socket.gethostname(),'steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    def run(name,cmd,reject=False):
        then=time.monotonic();r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(r.stdout);report['steps'].append({'name':name,'returncode':r.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,r.returncode,r.stdout[-950:],flush=True)
        if not reject and r.returncode:raise RuntimeError(name+' failed')
        if reject and (r.returncode==0 or not any(t in r.stdout for t in ['mismatch','regression','unexpected error','rejection missing','stream stall','ready after','wide split','outside signed'])):
            raise RuntimeError(name+' mutant not rejected')
    def build(name,w,aw,source=src,bench=cpp):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module',top,'--Mdir',str(directory),
                  f'-GLANES={w}',f'-GAW={aw}','-CFLAGS',f'-DTEST_LANES={w} -DTEST_AW={aw}',*map(str,shared+[source]),str(bench)])
        return str(directory/f'V{top}')
    try:
        for w in a.lanes:
            directory=out/f'build-scan-w{w}';scan_top='genefer_carry_stream_scan_pipe'
            run(f'build-scan-w{w}',['verilator','--cc','--exe','--build','-j','2','--top-module',scan_top,
                '--Mdir',str(directory),f'-GLANES={w}','-GPAYLOAD_W=32','-CFLAGS',f'-DTEST_LANES={w}',str(src),str(scan_cpp)])
            run(f'test-scan-w{w}',[str(directory/f'V{scan_top}')])
        for w in a.lanes:
            for aw,v in [(16,a.vectors),(1,a.tiny_vectors)]:
                name=f'w{w}-aw{aw}';exe=build('build-'+name,w,aw);run('test-'+name,[exe,str(v)])
        exe=build('build-size-aw17',4,17,bench=size_cpp);run('test-size-aw17',[exe])
        if a.mutations:
            defects=[
                ('mask','stream_mask==active_mask',"1'b1"),
                ('address',"stream_addr==AW'(issue<<LGW)","1'b1"),
                ('bounds',"if(active_mask[g] && (stream_word[g]<-$signed(bound) || stream_word[g]>$signed(bound)))","if(1'b0)"),
                ('valid','stream_fire && stream_ok && active_mask[g]','stream_ready && stream_ok && active_mask[g]'),
                ('last-ready','state==SPLIT && issue<groups','state==SPLIT'),
                ('digit-sign','.write_data(mem_data[g][31:0])',".write_data({1'b0,mem_data[g][30:0]})"),
                ('read-sign',"{{64{digit_q[h][31]}},digit_q[h]}","{64'd0,digit_q[h]}"),
                ('host-width',"write_data=={{64{write_data[31]}},write_data[31:0]}","1'b1"),
                ('summary-valid','summary_input_valid<=(state==SPLIT && split_valid[0]) || state==WRAP;',
                    'summary_input_valid<=(state==SPLIT) || state==WRAP;'),
                ('summary-last','if(summary_payload[AW:0]==groups-1)state<=WRAP;',
                    'if(summary_payload[AW:0]==groups-2)state<=WRAP;'),
                ('wrap-order','compose(summary_prefix[(LANES-1)*15+:15],suffix)',
                    'compose(suffix,summary_prefix[(LANES-1)*15+:15])'),
                ('scan-high-sign','$signed(extended[33:17])<$signed(thresholds[t*34+17+:17])',
                    'extended[33:17]<thresholds[t*34+17+:17]'),
                ('scan-low-equality','high_eq[lane][k*4+t] && low_lt[lane][k*4+t]',
                    'low_lt[lane][k*4+t]'),
                ('scan-mask','if(!comparison_mask[lane])maps[lane][k*3+:3]<=IDENTITY[k*3+:3];',
                    "if(1'b0)maps[lane][k*3+:3]<=IDENTITY[k*3+:3];"),
                ('emit-payload','digit_small[g]<=emit_payload[g*33+:33];',
                    'digit_small[g]<=leaf_small[g];'),
                ('emit-carry','if(prefix_valid)current_carry<=next_group;',
                    'if(leaf_valid)current_carry<=next_group;')]
            for name,old,new in defects:
                text=src.read_text()
                if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                path=out/f'mutant-{name}.sv';path.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,4,16,path);run('reject-'+name,[exe,str(a.vectors)],True)
            scan_defects=[
                ('reset','if(!rst_n)valid<=0;else valid<=scan[level-1].valid;',
                    "if(!rst_n)valid<=1;else valid<=scan[level-1].valid;"),
                ('payload','payload<=scan[level-1].payload;', 'payload<=payload_in;'),
                ('tree-order','compose(scan[level-1].value[lane-(1<<(level-1))],scan[level-1].value[lane])',
                    'compose(scan[level-1].value[lane],scan[level-1].value[lane-(1<<(level-1))])')]
            for name,old,new in scan_defects:
                text=src.read_text()
                if text.count(old)!=1:raise RuntimeError('scan mutation anchor '+name)
                path=out/f'mutant-scan-{name}.sv';path.write_text(text.replace(old,new))
                directory=out/f'build-mutant-scan-{name}';scan_top='genefer_carry_stream_scan_pipe'
                run(f'build-mutant-scan-{name}',['verilator','--cc','--exe','--build','-j','2','--top-module',scan_top,
                    '--Mdir',str(directory),'-GLANES=4','-GPAYLOAD_W=32','-CFLAGS','-DTEST_LANES=4',str(path),str(scan_cpp)])
                run(f'reject-scan-{name}',[str(directory/f'V{scan_top}')],True)
        report['status']='passed'
    except BaseException as exc:report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
