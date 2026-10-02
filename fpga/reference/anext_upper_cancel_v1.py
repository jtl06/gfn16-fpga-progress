"""Actual upper-normalizer prereg reset/cancel seam, simulation-only binding."""
import json,re,shutil
from pathlib import Path
from fpga.reference import anext_upper_source_v1 as parent
ROOT=parent.ROOT
TOP='genefer_anext_upper_cancel_probe_v1';SV='rtl/tb/'+TOP+'.sv';CPP='rtl/tb/anext_upper_cancel_v1.cpp'
CASES=('reset0','reset1','reset3','cancel0','cancel1','cancel3')
ROLE='artifacts/anext-upper-whole-aw5-role-v1';ROLE_SHA='74cc883d85fef7d696a8ae62e26378b7719e5079b28d0b791cda605435b14351'
CPP_PARENT='rtl/tb/anext_point_cancel_v1.cpp';CPP_PIN='0937d405c3be08cd9140b326ad8afedc6f700e27ed0cedfb5d5f4da413d59de1'
def expected():
    parent.verify();once=parent.point.core.once
    t=(ROOT/'rtl/kernel/genefer_anext_upper_core_v1.sv').read_text()
    t=once(t,'module genefer_anext_upper_core_v1','module '+TOP)
    t=once(t,'    input logic clk,rst_n,cmd_valid,rsp_ready,','    input logic sim_cancel,\n    output logic [2:0] monitor_upper,monitor_read,monitor_write,\n    output logic monitor_done,monitor_image_write,monitor_cache,\n    input logic clk,rst_n,cmd_valid,rsp_ready,')
    t=once(t,'.cancel(square_cancel),','.cancel(square_cancel || sim_cancel),')
    t=once(t,'endmodule','''    assign monitor_done=square_done;
    assign monitor_image_write=compute_write_en || compute_boundary_commit;
    assign monitor_cache=square_backend.sequencer.profile_cache_valid;
    for(genvar f=0;f<3;f=f+1)begin: native_observer
        assign monitor_upper[f]=square_backend.sequencer.field_lane[f].engine.arithmetic[0].butterfly.upper_launch_valid;
        assign monitor_read[f]=|square_backend.sequencer.field_lane[f].engine.data_re;
        assign monitor_write[f]=|square_backend.sequencer.field_lane[f].engine.data_we;
    end
endmodule''')
    if parent.point.sha(ROOT/CPP_PARENT)!=CPP_PIN:raise ValueError('upper cancel exact predecessor harness')
    cpp=(ROOT/CPP_PARENT).read_text().replace('genefer_anext_point_cancel_probe_v1',TOP).replace('ANEXT_POINT','ANEXT_UPPER').replace('monitor_point','monitor_upper')
    return {SV:t,CPP:cpp}
def validate(stdout_text,stderr_text,returncode_int,config_dict,assets_text_map):
    if set(config_dict)!={'case'} or config_dict['case'] not in CASES or assets_text_map:raise ValueError('upper finite cancel cases')
    m=re.fullmatch(r'ANEXT_UPPER_CANCEL_PASS case=(reset[013]|cancel[013]) fields=3 captured=1 quiet=16 recovered=32 ntt=115 ticks=([1-9][0-9]*)\n',stdout_text)
    if type(returncode_int) is not int or returncode_int!=0 or stderr_text or not m or m[1]!=config_dict['case'] or int(m[2])>=10000:raise ValueError('upper exact native contract')
    return dict(status='PASS_expected_contracts',case=m[1],ticks=int(m[2]),quiet_edges=16,recovery_words=32,
                scope='Actual upper_launch_valid observed across3fields; reset/cancel ages0/1/3 then fullreload. Simulation backendcancel seam, not publiccancelAPI.',promotion_allowed=False)
def prepare(output):
    output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists() or parent.point.sha(ROOT/ROLE/'manifest.json')!=ROLE_SHA:raise ValueError('fresh exact upper role')
    for name,text in expected().items():
        if (ROOT/name).read_text()!=text:raise ValueError('upper cancel source delta')
    m=json.loads((ROOT/ROLE/'manifest.json').read_text())
    for name,pin in m['sources'].items():
        if parent.point.sha(ROOT/ROLE/'source/fpga'/name)!=pin:raise ValueError('upper parent source closure')
    shutil.copytree(ROOT/ROLE/'source',output/'source')
    for name in (SV,CPP,CPP_PARENT,'reference/anext_upper_cancel_v1.py','tests/test_anext_upper_cancel_v1.py'):
        dest=output/'source/fpga'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest);m['sources'][name]=parent.point.sha(dest)
    m['build'].update(top=TOP,cpp_source=CPP)
    m['build']['sv_sources']=[SV if n=='rtl/kernel/genefer_anext_upper_core_v1.sv' else n for n in m['build']['sv_sources']]
    m['steps']=[dict(name='upper-'+case,argv=['{exe}',case],expected_returncode=0,expected_stderr='',validator=dict(source='reference/anext_upper_cancel_v1.py',function='validate',config=dict(case=case),assets={})) for case in CASES]
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(manifest_sha256=parent.point.sha(output/'manifest.json'),sources=len(m['sources']),cases=list(CASES),native_executed=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.output),indent=2))
