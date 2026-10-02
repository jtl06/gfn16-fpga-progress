"""Three-field real pending-write cancellation and physical RAM quiet tail."""
import json,re,shutil
from pathlib import Path
from fpga.reference import anext_writeback_source_v1 as source
ROOT=source.ROOT
TOP='genefer_anext_writeback_cancel_probe_v1';SV='rtl/tb/'+TOP+'.sv';CPP='rtl/tb/anext_writeback_cancel_v1.cpp'
PARENT_CPP='rtl/tb/anext_upper_cancel_v1.cpp';CPP_SHA='8948a8681bb8780eec1f9614d1e1a37ba595f7c5de5c16dcc6edffbfbb01adcd'
ROLE='artifacts/anext-writeback-aw5-role-v1';ROLE_SHA='427d71082ef57518da15820e3e8f4020ec285fe5d10e10165c1e46e9a0e480d5'
CASES=('reset0','reset1','reset3','cancel0','cancel1','cancel3')
def expected():
    source.verify();once=source.upper.point.core.once;t=(ROOT/'rtl/kernel/genefer_anext_writeback_core_v1.sv').read_text()
    t=once(t,'module genefer_anext_writeback_core_v1','module '+TOP)
    t=once(t,'    input logic clk,rst_n,cmd_valid,rsp_ready,','    input logic sim_cancel,\n    output logic [2:0] monitor_pending,monitor_read,monitor_write,\n    output logic monitor_done,monitor_image_write,monitor_cache,\n    input logic clk,rst_n,cmd_valid,rsp_ready,')
    t=once(t,'.cancel(square_cancel),','.cancel(square_cancel || sim_cancel),')
    t=once(t,'endmodule','''    assign monitor_done=square_done;
    assign monitor_image_write=compute_write_en || compute_boundary_commit;
    assign monitor_cache=square_backend.sequencer.profile_cache_valid;
    for(genvar f=0;f<3;f=f+1)begin: native_observer
        wire [127:0] physical_write;
        assign monitor_pending[f]=|square_backend.sequencer.field_lane[f].engine.writeback_pending_mask;
        assign monitor_read[f]=|square_backend.sequencer.field_lane[f].engine.data_re;
        for(genvar b=0;b<128;b=b+1)begin: bank_observer
            assign physical_write[b]=square_backend.sequencer.field_lane[f].engine.memories[b].ram_write_en;
        end
        assign monitor_write[f]=|physical_write;
    end
endmodule''')
    source.need(source.upper.point.sha(ROOT/PARENT_CPP)==CPP_SHA,'frozen whole cancel parent')
    cpp=(ROOT/PARENT_CPP).read_text().replace('genefer_anext_upper_cancel_probe_v1',TOP).replace('ANEXT_UPPER','ANEXT_WRITEBACK').replace('monitor_upper','monitor_pending').replace('ntt_cycles==115','ntt_cycles==126').replace('ntt=115','ntt=126')
    return {SV:t,CPP:cpp}
def validate(stdout_text,stderr_text,returncode_int,config_dict,assets_text_map):
    source.need(set(config_dict)=={'case'} and config_dict['case'] in CASES and not assets_text_map,'finite writeback cancel contract')
    m=re.fullmatch(r'ANEXT_WRITEBACK_CANCEL_PASS case=(reset[013]|cancel[013]) fields=3 captured=1 quiet=16 recovered=32 ntt=126 ticks=([1-9][0-9]*)\n',stdout_text)
    source.need(type(returncode_int) is int and returncode_int==0 and not stderr_text and m and m[1]==config_dict['case'] and int(m[2])<10000,'typed whole writeback cancel witness')
    return dict(status='PASS_expected_contracts',case=m[1],ticks=int(m[2]),quiet_edges=16,recovery_words=32,physical_RAM_enables_observed=True,promotion_allowed=False)
def prepare(output):
    output=Path(output).resolve();source.need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'fresh output/no PAUSE');source.need(source.upper.point.sha(ROOT/ROLE/'manifest.json')==ROLE_SHA,'frozen F3 normal role')
    for n,t in expected().items():source.need((ROOT/n).read_text()==t,'exact writeback cancellation derivative')
    m=json.loads((ROOT/ROLE/'manifest.json').read_text())
    for n,h in m['sources'].items():source.need(source.upper.point.sha(ROOT/ROLE/'source/fpga'/n)==h,'normal closure')
    shutil.copytree(ROOT/ROLE/'source',output/'source')
    for n in (SV,CPP,PARENT_CPP,'reference/anext_writeback_cancel_v1.py','tests/test_anext_writeback_cancel_v1.py'):
        d=output/'source/fpga'/n;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,d);m['sources'][n]=source.upper.point.sha(d)
    m['build'].update(top=TOP,cpp_source=CPP);m['build']['sv_sources']=[SV if n=='rtl/kernel/genefer_anext_writeback_core_v1.sv' else n for n in m['build']['sv_sources']]
    m['steps']=[dict(name='writeback-'+c,argv=['{exe}',c],expected_returncode=0,expected_stderr='',validator=dict(source='reference/anext_writeback_cancel_v1.py',function='validate',config=dict(case=c),assets={})) for c in CASES]
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');return dict(manifest_sha256=source.upper.point.sha(output/'manifest.json'),cases=CASES,native_executed=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);print(json.dumps(prepare(p.parse_args().output),indent=2))
