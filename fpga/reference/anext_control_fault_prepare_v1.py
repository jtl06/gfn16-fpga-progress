"""Closed simulation-only profile/completion integration tests on the prototype."""
import hashlib,json
from pathlib import Path
from fpga.reference.anext_control_fault_source_v1 import ROOT,sources,verify,SEQ,BACK,CORE
from fpga.reference.anext_control_fault_output_v1 import CASES
BASE='artifacts/anext-whole-aw5-role-v2'
PIN='0e51a47a61a9860a9a3937deedb47d54c554b158d721b6906db4d4ba47637505'
def sha(data):return hashlib.sha256(data).hexdigest()
def prepare(output):
    output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh output/no PAUSE')
    verify();raw=(ROOT/BASE/'manifest.json').read_bytes()
    if sha(raw)!=PIN:raise ValueError('frozen wholeAW5 source')
    m=json.loads(raw);files={}
    for name,pin in m['sources'].items():
        data=(ROOT/BASE/'source/fpga'/name).read_bytes()
        if sha(data)!=pin:raise ValueError('source drift')
        files[name]=data
    for name in [*sources(),'rtl/tb/anext_control_fault_v1.cpp','reference/anext_control_fault_source_v1.py','reference/anext_control_fault_output_v1.py','reference/anext_control_fault_prepare_v1.py','tests/test_anext_control_fault_v1.py']:files[name]=(ROOT/name).read_bytes()
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    m['sources']={n:sha(d) for n,d in files.items()};b=m['build'];b['top']='genefer_anext_control_fault_probe_v1';b['cpp_source']='rtl/tb/anext_control_fault_v1.cpp'
    b['sv_sources']=[n for n in b['sv_sources'] if n not in ('rtl/kernel/genefer_anext_core_v1.sv','rtl/kernel/genefer_anext_square_backend_v1.sv','rtl/kernel/genefer_anext_ntt_sequencer_v1.sv')]+[SEQ,BACK,CORE]
    m['steps']=[dict(name='control-'+case,argv=['{exe}',case],expected_returncode=0,expected_stderr='',validator=dict(source='reference/anext_control_fault_output_v1.py',function='validate',config=dict(case=case),assets={})) for case in CASES]
    m['source_root']='/home/jtl/gfn-fpga-lab/agent-work/anext-control-fault/source/fpga';m['output_parent']='/home/jtl/gfn-fpga-lab/agent-work/anext-control-fault/output'
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(status='prepared_not_executed',manifest_sha256=sha((output/'manifest.json').read_bytes()),cases=len(CASES),sources=len(files),simulation_only=True,promotion_allowed=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.output),indent=2))
