"""Isolated correction wrappers/normal manifest, no shared generator edits."""
import importlib.util
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
spec=importlib.util.spec_from_file_location('corr_serial_small_model',HERE/'model.py')
model=importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
TOP='genefer_stream27_correction_serial_normal_v1'


def wrappers():
    files={}
    for lanes in (8,16):
        for field in range(3):
            prime=model.FIELDS[field][0]
            roots=model.roots(lanes,field)
            packed=sum(v<<(27*i) for i,v in enumerate(roots))
            width=len(roots)*27
            name=f'genefer_stream27_correction_serial_p{lanes}_f{field}_v1'
            files['rtl/'+name+'.sv']=f'''module {name} #(parameter int GEN_W=24) (
 input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,
 input logic [GEN_W-1:0] generation_in,live_generation,
 input logic [{lanes*27-1}:0] data_in,
 output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
 output logic [GEN_W-1:0] generation_out,
 output logic [{lanes*27-1}:0] data_out);
 genefer_stream27_correction_serial_v1 #(.LANES({lanes}),.GEN_W(GEN_W),
 .MODULUS(32'd{prime}),.Q(32'd{(2-prime)%(1<<32)}),.ROOTS({width}'h{packed:x})) engine (.*);
endmodule
'''
    top=f'''module {TOP} (
 input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,
 input logic [23:0] generation_in,live_generation,
 input logic [2591:0] data_in,
 output logic [5:0] out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
 output logic [143:0] generation_out,
 output logic [2591:0] data_out);
'''
    for index,(lanes,field) in enumerate((p,f) for p in (8,16) for f in range(3)):
        top+=f''' genefer_stream27_correction_serial_p{lanes}_f{field}_v1 dut{index} (
 .clk,.rst_n,.in_slot_valid,.frame_start,.quarantine,.context_enabled,
 .generation_in,.live_generation,.data_in(data_in[{index*432}+:{lanes*27}]),
 .out_slot_valid(out_slot_valid[{index}]),.out_frame_start(out_frame_start[{index}]),
 .out_eligible(out_eligible[{index}]),.out_error(out_error[{index}]),.fault_pending(fault_pending[{index}]),
 .generation_out(generation_out[{index*24}+:24]),.data_out(data_out[{index*432}+:{lanes*27}]));
'''
        if lanes==8:top+=f" assign data_out[{index*432+216}+:216]='0;\n"
    files['rtl/'+TOP+'.sv']=top+'endmodule\n'
    return files


def role():
    model.check()
    files=wrappers()
    files['rtl/genefer_stream27_correction_serial_v1.sv']=(HERE/'rtl/genefer_stream27_correction_serial_v1.sv').read_text()
    for name in ('genefer_ntt_banked27_engine.sv','genefer_montgomery_mul27_sparse_pipe.sv'):
        files['rtl/'+name]=(ROOT/'rtl/kernel'/name).read_text()
    files['rtl/tb/corr_serial_normal_v1.cpp']=(HERE/'tb/corr_serial_normal_v1.cpp').read_text()
    files['rtl/tb/native_runtime_context_v1.h']=(ROOT/'rtl/tb/native_runtime_context_v1.h').read_text()
    for name in ('model.py','compiler.py'):
        files['lineage/'+name]=(HERE/name).read_text()
    pins={k:hashlib.sha256(v.encode()).hexdigest() for k,v in files.items()}
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        host='UNBOUND_NO_DISPATCH',source_root='UNBOUND',output_parent='UNBOUND',sources=pins,
        build=dict(top=TOP,sv_sources=[k for k in files if k.endswith('.sv')],
            cpp_source='rtl/tb/corr_serial_normal_v1.cpp',parameters={},
            cflags=['-std=c++17','-O2','-Werror=return-type'],runtime_threads=1),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='corr-serial-six-geometry-normal',argv=['{exe}'],expected_returncode=0,
            expected_stdout='CORR_SERIAL_NORMAL_PASS geometries=6 pairs=384 vectors=768 words=9216 latency_p8=32 latency_p16=58\n',expected_stderr='')],
        scope='Normal-only small P8/P16 correction DIF, all3 fields,64 paired cases/geometry, direct DFT and exact output/tag/latency checks. No fullN/whole integration/fault coverage/physical or promotion claim.',
        readiness='Normal test submission precedes new deliberate-fault suite; promotion fault gates remain outstanding.')
    return manifest,files


if __name__=='__main__':
    import argparse
    from datetime import datetime,timezone
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    m,f=role()
    if args.output:
        out=args.output.resolve()
        assert not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists()
        source=out/'source/fpga'
        source.mkdir(parents=True)
        for name,raw in f.items():
            p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('x') as stream:stream.write(raw)
        m['source_root']=str(source);m['output_parent']=str(out/'UNBOUND_OUTPUT')
        with (out/'manifest.json').open('x') as stream:json.dump(m,stream,indent=2);stream.write('\n')
        readiness=dict(status='RTL_and_normal_reference_complete_NOT_native_qualified',
            rtl_complete_at_utc=datetime.now(timezone.utc).isoformat(),
            source_pins=m['sources'],model_result=model.check(),normal_submitted=False,
            independent_review=False,promotion_allowed=False)
        with (out/'source-readiness.json').open('x') as stream:json.dump(readiness,stream,indent=2);stream.write('\n')
        print(json.dumps(dict(output=str(out),manifest_sha256=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest(),rtl_complete_at_utc=readiness['rtl_complete_at_utc'],files=len(f))))
    else:
        print(json.dumps(dict(manifest=m,files=f),separators=(',',':')))
