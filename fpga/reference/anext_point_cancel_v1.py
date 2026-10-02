"""Simulation-only point-flight cancellation seam; production RTL untouched."""
import json
import re
import shutil
from pathlib import Path
from fpga.reference import anext_point_source_v1 as parent

ROOT=parent.ROOT
TOP='genefer_anext_point_cancel_probe_v1'
SV='rtl/tb/'+TOP+'.sv'
CPP='rtl/tb/anext_point_cancel_v1.cpp'
CASES=('reset0','reset1','reset3','cancel0','cancel1','cancel3')
ROLE='artifacts/anext-point-whole-aw5-role-v1'
ROLE_SHA='11340a6819c863139bff8b50564d44a0b5d1df3b2eaa8b154f969a0e42d7aeeb'

def expected():
    parent.verify()
    t=(ROOT/'rtl/kernel/genefer_anext_point_core_v1.sv').read_text()
    t=parent.core.once(t,'module genefer_anext_point_core_v1','module '+TOP)
    t=parent.core.once(t,'    input logic clk,rst_n,cmd_valid,rsp_ready,',
        '    input logic sim_cancel,\n    output logic [2:0] monitor_point,monitor_read,monitor_write,\n    output logic monitor_done,monitor_image_write,monitor_cache,\n    input logic clk,rst_n,cmd_valid,rsp_ready,')
    t=parent.core.once(t,'.cancel(square_cancel),','.cancel(square_cancel || sim_cancel),')
    return parent.core.once(t,'endmodule','''    assign monitor_done=square_done;
    assign monitor_image_write=compute_write_en || compute_boundary_commit;
    assign monitor_cache=square_backend.sequencer.profile_cache_valid;
    for(genvar f=0;f<3;f=f+1)begin: native_observer
        assign monitor_point[f]=square_backend.sequencer.field_lane[f].engine.arithmetic[0].point_launch_valid;
        assign monitor_read[f]=|square_backend.sequencer.field_lane[f].engine.data_re;
        assign monitor_write[f]=|square_backend.sequencer.field_lane[f].engine.data_we;
    end
endmodule''')

def validate(stdout_text,stderr_text,returncode_int,config_dict,assets_text_map):
    if set(config_dict)!={'case'} or config_dict['case'] not in CASES or assets_text_map:
        raise ValueError('ANEXT_POINT_CANCEL_CASE')
    m=re.fullmatch(r'ANEXT_POINT_CANCEL_PASS case=(reset[013]|cancel[013]) fields=3 captured=1 quiet=16 recovered=32 ntt=115 ticks=([1-9][0-9]*)\n',stdout_text)
    if type(returncode_int) is not int or returncode_int!=0 or stderr_text or not m or m[1]!=config_dict['case'] or int(m[2])>=10000:
        raise ValueError('ANEXT_POINT_CANCEL_EXACT_RESULT')
    return dict(status='PASS_expected_contracts',case=m[1],ticks=int(m[2]),physical_fields=3,
                recovery_words=32,quiet_edges=16,promotion_allowed=False,
                scope='Simulation-only backend cancel/reset at point launch ages0/1/3; no new public host cancel opcode.')

def prepare(output):
    output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh/no PAUSE')
    if (ROOT/SV).read_text()!=expected() or parent.sha(ROOT/ROLE/'manifest.json')!=ROLE_SHA:
        raise ValueError('ANEXT_POINT_CANCEL_SOURCE')
    m=json.loads((ROOT/ROLE/'manifest.json').read_text())
    for name,pin in m['sources'].items():
        if parent.sha(ROOT/ROLE/'source/fpga'/name)!=pin:raise ValueError('ancestor drift')
    shutil.copytree(ROOT/ROLE/'source',output/'source')
    for name in (SV,CPP,'reference/anext_point_cancel_v1.py','tests/test_anext_point_cancel_v1.py'):
        dest=output/'source/fpga'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,dest);m['sources'][name]=parent.sha(dest)
    m['build']['top']=TOP;m['build']['cpp_source']=CPP
    m['build']['sv_sources']=[SV if x=='rtl/kernel/genefer_anext_point_core_v1.sv' else x for x in m['build']['sv_sources']]
    m['steps']=[dict(name='point-'+case,argv=['{exe}',case],expected_returncode=0,expected_stderr='',
                validator=dict(source='reference/anext_point_cancel_v1.py',function='validate',config=dict(case=case),assets={})) for case in CASES]
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(manifest_sha256=parent.sha(output/'manifest.json'),cases=list(CASES),source_only=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output),indent=2))
