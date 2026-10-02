"""Read-only collection of two already-completed AWS fits; no vendor execution."""
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'results/throughput-20260929'
REMOTE='/home/ubuntu/gfn16-worker/'
SSH='ssh -F /private/tmp/gfn16-aws.nxtVrY/ssh_config'

def main():
    for variant,label in [('orient8','orient8'),('orient8_rootfused','rootfused')]:
        project='square_core27_stream_prefetch_r2_host_broadcast_'+variant+'_ntt64-cpu4-100-v1'
        out=ROOT/('core27-r2-'+label+'64-aws-fit-v1');out.mkdir(exist_ok=False)
        subprocess.run(['rsync','-a','-e',SSH,
            '--include=/rtl/','--include=/rtl/*.sv','--include=/output_files/',
            '--include=/output_files/*.rpt','--include=/output_files/*.summary',
            '--include=/execution-context.json','--include=/execution-result.json','--include=/manifest.json',
            '--include=/probe.qpf','--include=/probe.qsf','--include=/probe.sdc','--include=/run.tcl',
            '--exclude=*','gfn16-aws:'+REMOTE+project+'/',str(out)+'/'],check=True,timeout=180)
        for suffix in ('-fit.log','-summary.json'):
            subprocess.run(['scp','-F','/private/tmp/gfn16-aws.nxtVrY/ssh_config',
                'gfn16-aws:'+REMOTE+project+suffix,str(out)],check=True,timeout=120)
        print(str(out),flush=True)

if __name__=='__main__':main()
