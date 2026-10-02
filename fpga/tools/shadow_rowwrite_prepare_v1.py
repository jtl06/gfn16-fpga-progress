"""Freeze the isolated two-context shadow transport normal role and package."""
import argparse,hashlib,importlib.util,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOP='genefer_stream27_shadow_rowwrite_test_v1'
GEOMETRIES=((5,8),(5,16),(8,8),(8,16))

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def top_source():
    text=f'''module {TOP}(
input logic clk,rst_n,quarantine,
input logic [1:0] owner_enabled,input logic [111:0] live_owner,
input logic [3:0] host_access,load_we,read_en,row_read_req,commit_we,row_write_req,
input logic host_context,commit_context,row_read_context,row_write_context,
input logic [7:0] host_addr,commit_address,
input logic [4:0] row_read_address,row_write_address,
input logic [31:0] write_data,commit_word,input logic [511:0] row_write_data,
input logic [55:0] commit_owner,row_read_owner,row_write_owner,
output logic [3:0] read_valid,read_context,row_read_valid,row_response_context,commit_ack,row_write_ack,rejected,
output logic [383:0] read_data,output logic [2047:0] row_read_data,
output logic [223:0] read_owner,row_response_owner);
'''
    for g,(aw,p) in enumerate(GEOMETRIES):
        rw=aw-(p.bit_length()-1)
        text+=f'''genefer_stream27_host_image_rowwrite_v1 #(.AW({aw}),.P({p})) geo{g} (
.clk,.rst_n,.quarantine,.owner_enabled,.live_owner,
.host_access(host_access[{g}]),.load_we(load_we[{g}]),.read_en(read_en[{g}]),.host_context,
.host_addr(host_addr[{aw-1}:0]),.write_data,
.row_read_req(row_read_req[{g}]),.row_read_context,.row_read_address(row_read_address[{rw-1}:0]),.row_read_owner,
.commit_we(commit_we[{g}]),.commit_context,.commit_address(commit_address[{aw-1}:0]),.commit_word,.commit_owner,
.row_write_req(row_write_req[{g}]),.row_write_context,.row_write_address(row_write_address[{rw-1}:0]),
.row_write_data(row_write_data[{p*32-1}:0]),.row_write_owner,
.read_valid(read_valid[{g}]),.read_context(read_context[{g}]),.read_data(read_data[{g*96}+:96]),.read_owner(read_owner[{g*56}+:56]),
.row_read_valid(row_read_valid[{g}]),.row_response_context(row_response_context[{g}]),
.row_read_data(row_read_data[{g*512}+:{p*32}]),.row_response_owner(row_response_owner[{g*56}+:56]),
.commit_ack(commit_ack[{g}]),.row_write_ack(row_write_ack[{g}]),.rejected(rejected[{g}]));
'''
        if p<16:text+=f"assign row_read_data[{g*512+p*32}+:{(16-p)*32}]='0;\n"
    return text+'endmodule\n'

def prepare(out):
    assert not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists()
    out.mkdir(parents=True);source=out/'source/fpga';source.mkdir(parents=True)
    files={'rtl/'+TOP+'.sv':top_source()}
    for path in ('rtl/kernel/genefer_stream27_host_image_rowwrite_v1.sv','rtl/kernel/genefer_sdp_ram32.sv',
                 'rtl/tb/shadow_rowwrite_v1.cpp','rtl/tb/native_runtime_context_v1.h',
                 'reference/s4_waiting_final_contract.py','tests/test_s4_waiting_final_contract.py'):
        files[path]=(ROOT/path).read_text()
    files['lineage/shadow_rowwrite_prepare_v1.py']=Path(__file__).read_text()
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('x') as stream:stream.write(raw)
    pins={name:sha(source/name) for name in files}
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND',source_root=str(source),output_parent=str(out/'UNBOUND_OUTPUT'),sources=pins,
        build=dict(top=TOP,sv_sources=[name for name in files if name.endswith('.sv')],cpp_source='rtl/tb/shadow_rowwrite_v1.cpp',parameters={},
                   cflags=['-std=c++17','-O2','-Werror=return-type'],runtime_threads=1),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='shadow-row-normal',argv=['{exe}'],expected_returncode=0,
                    expected_stdout='SHADOW_ROW_NORMAL_PASS geometries=4 contexts=2 read_edge=E0\n',expected_stderr='')],
        scope='Two-context RAM transport AW5/AW8 xP8/P16: cold scalar host, ordered dense raw rows B while scalar copy A, natural row/scalar q+owner alignment E0, II1, arbitration. Publication/order/drain controller and arithmetic unqualified. Fault role separate.',promotion_allowed=False)
    dump(out/'manifest.json',manifest)
    rtl_pins={k:v for k,v in pins.items() if k.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-shadow-rowwrite-v1',source_snapshot=rtl_pins,
        candidate_source_sha256=hashlib.sha256(json.dumps(rtl_pins,sort_keys=True,separators=(',',':')).encode()).hexdigest(),rtl_ready_at_utc=now)
    dump(out/'source-readiness.json',readiness)
    spec=importlib.util.spec_from_file_location('_shadow_native',ROOT/'tools/native_class_package_v2.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    budget=ROOT/'results/throughput-20260929/trackS-p16-diet-analysis-v1/fifo-ram-v1/normal-role-v1/budget.json'
    packet=out/'packet-01';worker.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1','s4-shadow-row-normal-01-v1','run',packet,budget)
    native=json.loads((packet/'ticket.json').read_text())
    donor=ROOT/'results/throughput-20260929/trackS-p16-diet-analysis-v1/fifo-ram-v1/normal-role-v1/global-ticket.json'
    ticket=json.loads(donor.read_text());ticket.update(id='s4-shadow-row-normal-q1-v1',candidate_id='s4-shadow-rowwrite-v1',owner='p16-shadow-row',
        created=now,test_role='normal',rtl_readiness=readiness,source_gate=dict(scope=manifest['scope'],promotion_allowed=False))
    ticket['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=sha(packet/'package.tar.gz'),ticket_sha256=sha(packet/'ticket.json'),
        manifest_sha256=native['manifest_sha256'],worker_id=native['id'],native_root=native['native_root'])
    dump(out/'global-ticket.json',ticket);print(out/'global-ticket.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);prepare(parser.parse_args().output.resolve())
