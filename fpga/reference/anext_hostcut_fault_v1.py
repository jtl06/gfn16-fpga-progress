"""Existing eleven whole fault seams plus actual same-edge image-cancel sampling."""
import json,re,shutil,types
from pathlib import Path
from fpga.reference import anext_hostcut_source_v1 as s
ROOT=s.ROOT
PARENT='reference/anext_control_fault_source_v1.py';PIN='692911fa75245971aa9d14fe9af138c3db354d1d9582c50d1a86357abab6bef3'
CPP_PARENT='rtl/tb/anext_control_fault_v1.cpp';CPP_PIN='d1a5b45d4243db454e7b855c6fe0bbc262663c0e253f3b3031b593219cba679d'
CPP='rtl/tb/anext_hostcut_fault_v1.cpp';TOP='genefer_anext_hostcut_control_fault_probe_v1'
CASES=('header0','header3','reset-word3','reset-commit','reset-check','done0','done1','done2','error0','error1','error2')
ROLE='artifacts/anext-hostcut-aw5-role-v1';ROLE_SHA='73006a1ede704f7fe3243f7ba1fb7c71f889e17e4390f811d30cdef28f5ab0ea'
def expected():
    s.verify();s.need(s.upper.point.sha(ROOT/PARENT)==PIN and s.upper.point.sha(ROOT/CPP_PARENT)==CPP_PIN,'frozen eleven-seam parent')
    t=(ROOT/PARENT).read_text().replace('from fpga.reference.anext_core_source_v1 import verify as direct_verify','from fpga.reference.anext_hostcut_source_v1 import verify as direct_verify')
    for a,b in [('genefer_anext_ntt_sequencer_v1','genefer_anext_upper_ntt_sequencer_v1'),('genefer_anext_square_backend_v1','genefer_anext_upper_square_backend_v1'),('genefer_anext_core_v1','genefer_anext_hostcut_core_v1'),('genefer_anext_control_','genefer_anext_hostcut_control_')]:t=t.replace(a,b)
    m=types.ModuleType('_hostcut_seams');m.__file__=str(ROOT/PARENT);exec(compile(t,'[frozen eleven-seam binding]','exec'),m.__dict__);out=m.sources();core=out[m.CORE]
    core=s.upper.point.core.once(core,'    input logic sim_header_corrupt,sim_drop_done,sim_child_error,','    output logic monitor_image_write,monitor_image_read,monitor_cancel,\n    input logic sim_header_corrupt,sim_drop_done,sim_child_error,')
    core=s.upper.point.core.once(core,'    assign monitor_state=','    assign monitor_image_write=host.image.write_accept;\n    assign monitor_image_read=host.image.read_accept;\n    assign monitor_cancel=host.bus.cancel;\n    assign monitor_state=');out[m.CORE]=core
    cpp=(ROOT/CPP_PARENT).read_text().replace('genefer_anext_control_fault_probe_v1',TOP).replace('ANEXT_CONTROL','ANEXT_HOSTCUT').replace('d.ntt_cycles==114','d.ntt_cycles==115')
    cpp=s.upper.point.core.once(cpp,'uint64_t ticks=0;','uint64_t ticks=0;unsigned cancel_samples=0;')
    cpp=s.upper.point.core.once(cpp,'auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();++ticks;};','auto tick=[&](){d.clk=0;d.eval();if(d.monitor_cancel){++cancel_samples;need(!d.monitor_image_write && !d.monitor_image_read,"ANEXT_HOSTCUT_SAME_EDGE_IMAGE_KILL");}d.clk=1;d.eval();++ticks;};')
    cpp=s.upper.point.core.once(cpp,'!d.monitor_ram_read && !d.monitor_ram_write && !d.rsp_valid','!d.monitor_ram_read && !d.monitor_ram_write && !d.monitor_image_read && !d.monitor_image_write && !d.rsp_valid')
    cpp=s.upper.point.core.once(cpp,'    need(context.threads()==1 && d.threads()==1,"ANEXT_HOSTCUT_THREADS");','    need(reset_case || cancel_samples>0,"ANEXT_HOSTCUT_ACTUAL_CANCEL_SAMPLE");\n    need(context.threads()==1 && d.threads()==1,"ANEXT_HOSTCUT_THREADS");')
    cpp=s.upper.point.core.once(cpp,'<<ticks<<"\\n";','<<ticks<<" cancel_samples="<<cancel_samples<<"\\n";');out[CPP]=cpp;return out
def validate(stdout,stderr,rc,config,assets):
    s.need(set(config)=={'case'} and config['case'] in CASES and not assets,'finite hostcut seams')
    m=re.fullmatch(r'ANEXT_HOSTCUT_PASS case=([a-z0-9-]+) injected=1 errors=([01]) recovered=1 words=32 quiet=12 ticks=([1-9][0-9]*) cancel_samples=([0-9]+)\n',stdout)
    s.need(type(rc) is int and rc==0 and not stderr and m and m[1]==config['case'] and int(m[2])==int(not m[1].startswith('reset-')) and int(m[3])<50000 and (m[1].startswith('reset-') or int(m[4])>0),'exact hostcut fault/cancel witness')
    return dict(status='PASS_expected_contracts',case=m[1],ticks=int(m[3]),cancel_samples=int(m[4]),quiet_edges=12,recovery_words=32,promotion_allowed=False)
def prepare(output):
    output=Path(output).resolve();s.need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and s.upper.point.sha(ROOT/ROLE/'manifest.json')==ROLE_SHA,'fresh pinned hostcut role')
    generated=expected()
    for n,t in generated.items():s.need((ROOT/n).read_text()==t,'exact hostcut seam derivative')
    m=json.loads((ROOT/ROLE/'manifest.json').read_text())
    for n,h in m['sources'].items():s.need(s.upper.point.sha(ROOT/ROLE/'source/fpga'/n)==h,'closed normal role')
    shutil.copytree(ROOT/ROLE/'source',output/'source')
    for n in [*generated,PARENT,CPP_PARENT,'reference/anext_hostcut_fault_v1.py','tests/test_anext_hostcut_fault_v1.py']:
        d=output/'source/fpga'/n;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,d);m['sources'][n]=s.upper.point.sha(d)
    replace={'rtl/kernel/genefer_anext_upper_ntt_sequencer_v1.sv':'rtl/tb/genefer_anext_hostcut_control_seq_probe_v1.sv','rtl/kernel/genefer_anext_upper_square_backend_v1.sv':'rtl/tb/genefer_anext_hostcut_control_backend_probe_v1.sv','rtl/kernel/genefer_anext_hostcut_core_v1.sv':'rtl/tb/'+TOP+'.sv'}
    m['build'].update(top=TOP,cpp_source=CPP,sv_sources=[replace.get(n,n) for n in m['build']['sv_sources']]);m['steps']=[dict(name='hostcut-'+c,argv=['{exe}',c],expected_returncode=0,expected_stderr='',validator=dict(source='reference/anext_hostcut_fault_v1.py',function='validate',config=dict(case=c),assets={})) for c in CASES]
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');return dict(manifest_sha256=s.upper.point.sha(output/'manifest.json'),cases=len(CASES),native_executed=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);print(json.dumps(prepare(p.parse_args().output),indent=2))
