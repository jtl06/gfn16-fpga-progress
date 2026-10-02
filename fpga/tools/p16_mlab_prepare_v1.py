"""Prepare isolated P2 delay native normal/reset packets using standing tooling."""
import argparse,hashlib,importlib.util,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOP='genefer_stream27_p16_mlab_test_v1'
WIDTHS=(1,10,28,29,37,38,64,224)
DEPTHS=(1,2,4,8,16,32,64)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def top_source():
    count=len(WIDTHS)*len(DEPTHS);bits=count*224
    text=f'''module {TOP}(input logic clk,rst_n,input logic [{count-1}:0] advance,
input logic [{bits-1}:0] write_words,output logic [{bits-1}:0] head_parent,head_candidate);
'''
    for g,(width,depth) in enumerate((w,d) for w in WIDTHS for d in DEPTHS):
        for label,module,port in [('old','genefer_stream27_mdc_fifo_smallreg_v1','head_parent'),
                                 ('new','genefer_stream27_delay_mlab_v1','head_candidate')]:
            text+=f'''{module} #(.WORD_W({width}),.DEPTH({depth})) {label}{g} (
.clk,.rst_n,.advance(advance[{g}]),.write_word(write_words[{g*224}+:{width}]),.head({port}[{g*224}+:{width}]));
'''
            if width<224:text+=f"assign {port}[{g*224+width}+:{224-width}]='0;\n"
    return text+'endmodule\n'

def prepare(out,reset=False):
    assert not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists()
    out.mkdir(parents=True);source=out/'source/fpga';source.mkdir(parents=True)
    files={'rtl/'+TOP+'.sv':top_source()}
    for path in ['rtl/kernel/genefer_stream27_delay_mlab_v1.sv','rtl/kernel/genefer_stream27_mdc_fifo_smallreg_v1.sv',
                 'rtl/kernel/genefer_stream27_mdc_commutator_sync.sv','rtl/tb/p16_mlab_v1.cpp','rtl/tb/native_runtime_context_v1.h']:
        files['rtl/'+('tb/' if '/tb/' in path else '')+Path(path).name]=(ROOT/path).read_text()
    files['lineage/p16_mlab_prepare_v1.py']=Path(__file__).read_text()
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('x') as stream:stream.write(raw)
    pins={name:sha(source/name) for name in files}
    role='reset' if reset else 'normal';identifier='s4-p2-mlab-'+role+'-q1-v1'
    stdout=('P2_MLAB_RESET_PASS geometries=56 reset_ages=130 comparisons=4990496\n' if reset else
            'P2_MLAB_NORMAL_PASS geometries=56 cycles=4096 comparisons=688184\n')
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND',source_root=str(source),
        output_parent=str(out/'UNBOUND_OUTPUT'),sources=pins,
        build=dict(top=TOP,sv_sources=[name for name in files if name.endswith('.sv')],cpp_source='rtl/tb/p16_mlab_v1.cpp',
                   parameters={},cflags=['-std=c++17','-O2','-Werror=return-type'],runtime_threads=1),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='p2-mlab-'+role,argv=['{exe}']+(['--reset-test'] if reset else []),expected_returncode=0,
                    expected_stdout=stdout,expected_stderr='')],
        scope='Isolated P2 exact parent plus independent deque, 8 widths x 7 depths; payload/stall/reset calendar. Physical MLAB inference requires separate fit.',
        promotion_allowed=False)
    dump(out/'manifest.json',manifest)
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-p2-mlab-v1',source_snapshot={k:v for k,v in pins.items() if k.endswith('.sv')},
                   candidate_source_sha256=hashlib.sha256(json.dumps({k:v for k,v in pins.items() if k.endswith('.sv')},sort_keys=True,separators=(',',':')).encode()).hexdigest(),rtl_ready_at_utc=now)
    dump(out/'source-readiness.json',readiness)
    # Preserve the original conservative GCP observation, within its six-hour validity.
    budget=ROOT/'results/throughput-20260929/trackS-p16-diet-analysis-v1/fifo-ram-v1/normal-role-v1/budget.json'
    spec=importlib.util.spec_from_file_location('_mlab_native',ROOT/'tools/native_class_package_v2.py')
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    packet=out/'packet-01';worker.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1','s4-p2-mlab-'+role+'-01-v1','run',packet,budget)
    native=json.loads((packet/'ticket.json').read_text())
    donor=ROOT/'results/throughput-20260929/trackS-p16-diet-analysis-v1/fifo-ram-v1/normal-role-v1/global-ticket.json'
    ticket=json.loads(donor.read_text());ticket.update(id=identifier,candidate_id='s4-p2-mlab-v1',owner='p16-mlab',created=now,
        test_role='deliberate_fault' if reset else 'normal',source_gate=dict(scope=manifest['scope'],physical_memory_inference=False,promotion_allowed=False))
    package=ticket['packages'][0]
    package.update(archive=str(packet/'package.tar.gz'),sha256=sha(packet/'package.tar.gz'),ticket_sha256=sha(packet/'ticket.json'),
                   manifest_sha256=native['manifest_sha256'],worker_id=native['id'],native_root=native['native_root'])
    if reset:ticket.pop('rtl_readiness',None)
    else:ticket['rtl_readiness']=readiness
    dump(out/'global-ticket.json',ticket)
    print(out/'global-ticket.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--reset',action='store_true')
    args=parser.parse_args();prepare(args.output.resolve(),args.reset)
