"""Resume the timed-out atomic27 gate with byte-exact reset-boundary segments.

Preserves the original failed report. Completed prior steps are provenance, not
rerun claims. Every previously incomplete normal case and every remaining fault
is actually executed; no resource/timeout increase or cached correctness PASS.
"""
import argparse,copy,hashlib,json,os,re,resource,shutil,signal,socket,subprocess,time
from pathlib import Path
from .square_core27_regression import write_vectors

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def segments(raw):
    lines=raw.splitlines(keepends=True)
    loads=[i for i,line in enumerate(lines) if line.startswith(b'LOAD ')]
    if not loads:raise ValueError('missing reset-defined LOAD')
    cuts=[1,*loads[1:],len(lines)]
    result=[(start,end,lines[0]+b''.join(lines[start:end])) for start,end in zip(cuts,cuts[1:])]
    if lines[0]+b''.join(b''.join(payload.splitlines(keepends=True)[1:]) for _,_,payload in result)!=raw:
        raise ValueError('segmented bytes do not reproduce original stream')
    commands={b'LOAD',b'LOAD_KEEP',b'RUN',b'RUN_NOREAD',b'ABORT',b'BADBASE',b'BADDIGIT',b'BADDIGIT_AT'}
    original=[i for i,line in enumerate(lines) if line.split(maxsplit=1)[0] in commands]
    union=[i for start,end,_ in result for i in range(start,end) if lines[i].split(maxsplit=1)[0] in commands]
    if union!=original or len(union)!=len(set(union)):raise ValueError('transaction omission/duplication')
    run_ids=[line.split()[1].decode() for line in lines if line.startswith((b'RUN ',b'RUN_NOREAD '))]
    if len(run_ids)!=len(set(run_ids)):raise ValueError('duplicate original case ID')
    return lines,result,run_ids,original

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--previous',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    root=Path(__file__).resolve().parents[1];previous=args.previous.resolve();out=args.output.resolve()
    original_path=previous/'report.json';original_bytes=original_path.read_bytes();original=json.loads(original_bytes)
    if original['status']!='failed' or 'TimeoutExpired' not in original.get('error',''):raise ValueError('not the expected timed-out gate')
    executable=previous/'build-w64-aw16/Vgenefer_square_core27'
    if str(executable) not in original['error']:raise ValueError('different timeout target')
    if any(s['returncode']!=0 for s in original['steps']):raise ValueError('prior arithmetic/build failure is not a timeout-only continuation')
    if not any(s['name']=='build-w64-aw16' for s in original['steps']):raise ValueError('original executable build not recorded')
    if any(m['ntt_lanes']==64 and m['aw']==16 for m in original['metrics']):raise ValueError('ambiguous incomplete-case evidence')
    for name,sha in original['sources'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or digest(path)!=sha:raise ValueError('source/bench identity changed: '+name)
    vectors=previous/'vectors-aw16.txt'
    if digest(vectors)!=original['vectors']['16']['sha256']:raise ValueError('original full-size vector changed')
    lines,parts,run_ids,transaction_ids=segments(vectors.read_bytes())
    out.mkdir(parents=True,exist_ok=False);(out/'executables').mkdir()
    exe_sha=digest(executable);frozen=out/'executables/core27-64-aw16';shutil.copy2(executable,frozen);frozen.chmod(0o555)
    if digest(frozen)!=exe_sha:raise ValueError('executable copy differs')
    report=copy.deepcopy(original);report['status']='running';report.pop('error',None)
    report['recovery']=dict(original_report=str(original_path),original_sha256=hashlib.sha256(original_bytes).hexdigest(),
        original_status=original['status'],original_error=original['error'],normalizer=None,
        executable_original=str(executable),executable_copy=str(frozen),executable_sha256=exe_sha,
        executable_identity_note='The original run did not record an executable SHA; this recovery pins the preserved successful-build artifact and verifies its byte-exact copy before and after every segment.',
        memory_limit_bytes=6<<30,build_workers=2,command_timeout_seconds=600,
        original_vector_sha256=digest(vectors),transaction_ids=[i+1 for i in transaction_ids],original_case_ids=run_ids,segments=[])
    report['sources']['reference/square_core27_recovery.py']=digest(__file__)
    report['mutation_sources']={}
    for step in report['steps']:
        step['evidence_log']=str(previous/(step['name']+'.log'));step['origin']='preserved_completed_step'
    def run(name,command,reject=False):
        log=out/f'{name}.log';then=time.monotonic();timed_out=False
        with log.open('x') as stream:
            proc=subprocess.Popen(command,cwd=root,stdout=stream,stderr=subprocess.STDOUT,text=True,start_new_session=True)
            try:proc.wait(timeout=600)
            except subprocess.TimeoutExpired:
                timed_out=True
                try:os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        output=log.read_text();report['steps'].append(dict(name=name,command=command,returncode=proc.returncode,
            seconds=time.monotonic()-then,rejection=reject,timed_out=timed_out,evidence_log=str(log),origin='executed_recovery'))
        print(name,proc.returncode,output[-800:],flush=True)
        if timed_out:raise RuntimeError(name+' hit unchanged600s cap')
        if not reject and proc.returncode:raise RuntimeError(name+' failed')
        if reject and (proc.returncode==0 or not any(x in output for x in ['mismatch','accepted','quarantine','lane skew','word skew','noncanonical','unsupported sparse','invalid sparse'])):
            raise RuntimeError(name+' mutant escaped')
        return output
    names=['genefer_montgomery_mul32_pipe','genefer_montgomery_mul27_sparse_pipe','genefer_digit_reduce27_pipe',
        'genefer_sdp_ram32','genefer_ntt_banked27_engine','genefer_ntt_banked27_host_engine','genefer_mod64_pipe',
        'genefer_crt3_27_pipe','genefer_carry_transfer_tree','genefer_sp_ram','genefer_div_recip_narrow',
        'genefer_carry_prefix_vector_pipe_v2','genefer_square_core27']
    sources=[root/'rtl/kernel'/f'{name}.sv' for name in names];cpp=root/'rtl/tb/square_core27.cpp'
    def build(name,w,aw,selected=None):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module','genefer_square_core27','--Mdir',str(directory),
            f'-GAW={aw}',f'-GNTT_LANES={w}','-CFLAGS','-O0',*map(str,selected or sources),str(cpp)])
        path=directory/'Vgenefer_square_core27';report.setdefault('built_executables',{})[name]=digest(path);return str(path)
    try:
        observed=[]
        for index,(start,end,payload) in enumerate(parts):
            path=out/f'vectors-aw16-segment{index}.txt';path.write_bytes(payload)
            ids=[line.split()[1].decode() for line in payload.splitlines() if line.startswith((b'RUN ',b'RUN_NOREAD '))]
            report['recovery']['segments'].append(dict(path=str(path),sha256=digest(path),first_original_line=start+1,
                last_original_line=end,case_ids=ids,transaction_ids=[i+1 for i in transaction_ids if start<=i<end]))
            if digest(executable)!=exe_sha or digest(frozen)!=exe_sha:raise ValueError('executable identity changed')
            output=run(f'test-w64-aw16-segment{index}',[str(frozen),str(path),'cache'])
            for line in output.splitlines():
                if ' cycles=' not in line:continue
                values={k:int(v) for k,v in re.findall(r'(cycles|conversion|roots|ntt|crt|carry|passes|base|cache_before|root_loads|root_hits|readback)=(\d+)',line)}
                label=line.split()[0];observed.append(label)
                report['metrics'].append(dict(ntt_lanes=64,io_lanes=16,aw=16,case=label,segment=index,**values))
            if digest(frozen)!=exe_sha or digest(executable)!=exe_sha:raise ValueError('executable changed during segment')
        if observed!=run_ids:raise ValueError('completed case IDs do not reproduce original order exactly')
        report['recovery']['completed_case_ids']=observed
        exe=build('build-unsupported-profile',32,1);run('test-unsupported-profile',[exe,'reject-profile'])
        path=previous/'vectors-aw5.txt'
        if digest(path)!=original['vectors']['5']['sha256']:raise ValueError('mutation oracle changed')
        vector_lines=path.read_text().splitlines();chain_index=next(i for i,line in enumerate(vector_lines) if line.startswith('LOAD_KEEP no-host-chain '))
        chain=out/'mutation-immediate-chain.txt';chain.write_text('\n'.join([vector_lines[0],*vector_lines[chain_index:]])+'\n')
        defects=[
            ('raw-truncate',".digit(carry_words[h][31:0])",".digit({5'b0,carry_words[h][26:0]})"),
            ('convert-radix',".rhs(R2[f])",".rhs(32'd1)"),
            ('conversion-word',".digit(carry_words[h][31:0])",".digit(carry_words[0][31:0])"),
            ('root-order',".GENERATOR(G[f])",".GENERATOR(32'd1)"),
            ('inverse-phase',"step==3 ? 2'd2 : 2'd3","step==3 ? 2'd1 : 2'd3"),
            ('double',"double_reg ? (coefficient_words[h] <<< 1) : coefficient_words[h]","coefficient_words[h]"),
            ('coefficient-row',"AW'(issue_count) : AW'(write_count);","AW'(issue_count) : AW'(write_count+IO_STEP);"),
            ('digit-base',"carry_words[h]>=$signed({64'd0,base_reg})","carry_words[h]>$signed({64'd0,base_reg})"),
            ('cache-reset',"root_phases_loaded<=0; root_cache_hits<=0; root_cache_valid<=0;","root_phases_loaded<=0; root_cache_hits<=0; root_cache_valid<=15;"),
            ('cache-reload',"ROOT_CACHE && root_cache_valid[0]","1'b0"),
            ('immediate-start',"IDLE: if(start) begin","IDLE: if(start && !done) begin"),
            ('reducer-error',"assign reduction_error[f]=|reduce_error_words[f];",
                "assign reduction_error[f]=(|reduce_error_words[f]) || (state==CONVERT && convert_input_valid);"),
            ('wrong-r2',"32'd45971250,32'd50081300,32'd63576045","32'd45971250,32'd50081300,32'd63576046"),
        ]
        for name,old,new in defects:
            text=sources[-1].read_text()
            if text.count(old)!=1:raise ValueError('mutation anchor '+name)
            changed=out/f'mutant-{name}.sv';changed.write_text(text.replace(old,new));report['mutation_sources'][str(changed)]=digest(changed)
            exe=build('build-mutant-'+name,16,5,[*sources[:-1],changed])
            run('reject-'+name,[exe,str(chain if name=='immediate-start' else path),'cache'],True)
        oldcrt=root/'rtl/kernel/genefer_crt3_pipe.sv';report['mutation_sources'][str(oldcrt)]=digest(oldcrt)
        changed=out/'mutant-old-crt.sv';changed.write_text(sources[-1].read_text().replace('genefer_crt3_27_pipe crt','genefer_crt3_pipe crt'))
        report['mutation_sources'][str(changed)]=digest(changed)
        exe=build('build-mutant-old-crt',16,5,[*sources[:-1],oldcrt,changed]);run('reject-old-crt',[exe,str(path),'cache'],True)
        host=sources[5];old='read_group<=host_group;'
        if host.read_text().count(old)!=1:raise ValueError('host quarter mutation anchor')
        changed=out/'mutant-host-quarter.sv';changed.write_text(host.read_text().replace(old,'read_group<=0;'));report['mutation_sources'][str(changed)]=digest(changed)
        quarter=out/'mutation-host-quarter-vectors.txt';write_vectors(quarter,7,original['vectors']['5']['seed'],True)
        exe=build('build-mutant-host-quarter',64,7,[changed if p==host else p for p in sources])
        run('reject-host-quarter',[exe,str(quarter),'cache'],True)
        for name,sha in original['sources'].items():
            if digest(root/name)!=sha:raise ValueError('source identity changed during recovery')
        report['status']='passed'
    except BaseException as error:report.update(status='failed',error=repr(error));raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
