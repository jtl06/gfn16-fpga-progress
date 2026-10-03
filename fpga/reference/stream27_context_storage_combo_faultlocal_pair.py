"""R7 paired full-GEN25 native seam; never a production source mutation."""
from datetime import datetime,timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_storage_combo_faultlocal_pair.py'
CAPTURE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-native-v1/aw8-normal/production-bundle.json'
CAPTURE_PIN='7f17f9e1410eac6d1fbfc3909717bbd28296e943833b15230aeab53dcc625608'
OLD='genefer_stream27_mdc_commutator_shared_packed_v1'
NEW='genefer_stream27_mdc_commutator_shared_packed_faultlocal_v1'
PINS={OLD:'30b2ce81f3bff93dc40da9e3d3d15a741c0aeba779f5e1e7e392c5d4c3f2e366',NEW:'b5fe6006fc2731f51deed81b47640d0ded34b1ee14c8164f5c9747924a062213'}
DONOR=ROOT/'results/throughput-20260929/trackS-p16-diet-analysis-v1/commutator-shared-mlab-v1'
TOP='genefer_stream27_r7_comm_pair_v1'
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-native-v1'
DEPTHS=(1,2,4,8,16,32,64,2048)
def need(ok,why):
    if not ok:raise ValueError('R7_PAIR_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def replace(text,a,b,count=1):
    need(text.count(a)==count,'UNIQUE_ADAPTER:'+a[:50]);return text.replace(a,b)
def clone(text,module,side):
    need(sha(text.encode())==PINS[module],'PRODUCTION_LEAF_PIN')
    name='genefer_stream27_r7_comm_'+side+'_probe_v1'
    sites=[('module '+module+' #','module '+name+' #'),
        (' input logic quarantine,\n',' input logic quarantine,\n input logic [GEN_W+1:0] diag_head_xor,\n output logic diag_owner_bad,diag_phase,diag_head_raw_valid,diag_malformed,\n'),
        (' assign head_upper_tag=head_upper_word[PAIRS*VALUE_W+:TAG_W];',
         ' assign head_upper_tag=head_upper_word[PAIRS*VALUE_W+:TAG_W] ^ diag_head_xor;\n assign diag_owner_bad=owner_bad;assign diag_phase=phase;assign diag_malformed=malformed;\n assign diag_head_raw_valid=head_upper_word[PAIRS*VALUE_W+TAG_W-1];')]
    out=text
    for a,b in sites:out=replace(out,a,b)
    reverse=out
    for a,b in reversed(sites):reverse=replace(reverse,b,a)
    need(reverse==text,'PROBE_LITERAL_BYTE_REVERSE')
    return name,out
def top_source(names):
    text='''module genefer_stream27_r7_comm_pair_v1 (
 input logic clk,rst_n,
 input logic [15:0] in_slot_valid,frame_start,context_in,quarantine,
 input logic [399:0] generation_in,
 input logic [127:0] upper_payload,lower_payload,
 input logic [31:0] context_enabled,
 input logic [799:0] live_generations,
 input logic [431:0] head_tag_xor,
 input logic [3583:0] upper_in,lower_in,
 output wire [15:0] new_slot,new_start,new_eligible,new_error,new_pending,new_context,
 output wire [15:0] old_bad,new_bad,old_phase,new_phase,old_head_valid,new_head_valid,old_malformed,new_malformed,
 output wire [399:0] new_generation,
 output wire [127:0] new_upper_payload,new_lower_payload,
 output wire [3583:0] new_upper,new_lower,old_upper,old_lower,
 output wire [127:0] old_slot,old_start,old_eligible,old_error,old_pending,old_context,
 output wire [3199:0] old_generation,
 output wire [127:0] old_upper_payload,old_lower_payload);
'''
    for g in range(16):
        depth=DEPTHS[g%8];contexts=1+g//8;frame=max(128,2*depth)
        text+=f' wire old_slot_g{g},old_start_g{g},old_eligible_g{g},old_error_g{g},old_pending_g{g},old_context_g{g};wire [24:0] old_generation_g{g};\n'
        for side in ('old','new'):
            tail=lambda key: f'old_{key}_g{g}' if side=='old' else (f'new_generation[{g*25}+:25]' if key=='generation' else f'new_{key}[{g}]')
            text+=f''' {names[side]} #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),.GEN_W(25),.DEPTH({depth}),.FRAME_T({frame}),.CONTEXTS({contexts})) {side}_g{g} (
 .clk,.rst_n,.in_slot_valid(in_slot_valid[{g}]),.frame_start(frame_start[{g}]),.context_in(context_in[{g}]),
 .generation_in(generation_in[{g*25}+:25]),.context_enabled(context_enabled[{g*2}+:{contexts}]),.live_generations(live_generations[{g*50}+:{contexts*25}]),.quarantine(quarantine[{g}]),
 .diag_head_xor(head_tag_xor[{g*27}+:27]),.diag_owner_bad({side}_bad[{g}]),.diag_phase({side}_phase[{g}]),.diag_head_raw_valid({side}_head_valid[{g}]),.diag_malformed({side}_malformed[{g}]),
 .upper_in(upper_in[{g*224}+:224]),.lower_in(lower_in[{g*224}+:224]),.upper_payload(upper_payload[{g*8}+:8]),.lower_payload(lower_payload[{g*8}+:8]),
 .out_slot_valid({tail('slot')}),.out_frame_start({tail('start')}),.out_eligible({tail('eligible')}),.out_error({tail('error')}),.fault_pending({tail('pending')}),.context_out({tail('context')}),.generation_out({tail('generation')}),
 .upper_out({side}_upper[{g*224}+:224]),.lower_out({side}_lower[{g*224}+:224]),.upper_payload_out({side}_upper_payload[{g*8}+:8]),.lower_payload_out({side}_lower_payload[{g*8}+:8]));
'''
        for lane in range(8):
            i=g*8+lane
            for key in ('slot','start','eligible','error','pending','context'):text+=f' assign old_{key}[{i}]=old_{key}_g{g};\n'
            text+=f' assign old_generation[{i*25}+:25]=old_generation_g{g};\n'
    return text+'endmodule\n'
def normal_source():
    text=(DONOR/'tb/shared_comm_normal_v1.cpp').read_text()
    text=text.replace('genefer_stream27_shared_comm_normal_v1',TOP).replace('SHARED_COMM_NORMAL_PASS','R7_COMM_PAIR_NORMAL_PASS')
    text=replace(text,'uint8_t owner=0,gen=0,payload=0;','uint8_t owner=0,payload=0;uint32_t gen=0;')
    text=replace(text,'for(unsigned i=0;i<4;i++){d.generation_in[i]=0;d.upper_payload[i]=0;d.lower_payload[i]=0;}','for(unsigned i=0;i<13;i++)d.generation_in[i]=0;\n  for(unsigned i=0;i<4;i++){d.upper_payload[i]=0;d.lower_payload[i]=0;}\n  for(unsigned i=0;i<14;i++)d.head_tag_xor[i]=0;')
    text=replace(text,'for(unsigned i=0;i<8;i++)d.live_generations[i]=0;','for(unsigned i=0;i<25;i++)d.live_generations[i]=0;')
    text=replace(text,'uint8_t gen=uint8_t(5+f);','uint32_t gen=0x1555500u+5+f;')
    text=replace(text,'uint8_t live0=uint8_t(g<8?5+f:5+(f/2)*2),live1=uint8_t(6+(f/2)*2);','uint32_t live0=0x1555500u+(g<8?5+f:5+(f/2)*2),live1=0x1555500u+6+(f/2)*2;')
    text=replace(text,'live0^=0x80;','live0^=0x1000000;')
    for a,b in [('g*16,8,','g*50,25,'),('g*16+8,8,','g*50+25,25,'),('g*8,8,gen','g*25,25,gen'),('g*8,8)==ref[g].held_upper.gen','g*25,25)==ref[g].held_upper.gen'),('i*8,8)==get(d.new_generation,g*8,8)','i*25,25)==get(d.new_generation,g*25,25)')]:text=replace(text,a,b)
    text=replace(text,'d.eval();require(d.new_pending==0,"SHARED_COMM_LEGAL_PREEDGE_FAULT");','d.eval();require(d.new_pending==0,"SHARED_COMM_LEGAL_PREEDGE_FAULT");\n   require(d.old_bad==d.new_bad && d.old_phase==d.new_phase && d.old_head_valid==d.new_head_valid && d.old_malformed==d.new_malformed,"R7_PAIR_PRE_CONTROL");')
    return text
def fault_source():
    text=(DONOR/'tb/shared_comm_fault_v1.cpp').read_text()
    text=replace(text,'#include "shared_comm_normal_v1.cpp"','#include "r7_comm_pair_normal.cpp"')
    text=replace(text,'for(unsigned i=0;i<4;i++){d.generation_in[i]=0;d.upper_payload[i]=0;d.lower_payload[i]=0;}','for(unsigned i=0;i<13;i++)d.generation_in[i]=0;\n  for(unsigned i=0;i<4;i++){d.upper_payload[i]=0;d.lower_payload[i]=0;}\n  for(unsigned i=0;i<14;i++)d.head_tag_xor[i]=0;')
    text=replace(text,'for(unsigned i=0;i<8;i++)d.live_generations[i]=0;','for(unsigned i=0;i<25;i++)d.live_generations[i]=0;')
    text=replace(text,'get(d.old_generation,i*8,8)==get(d.new_generation,g*8,8)','get(d.old_generation,i*25,25)==get(d.new_generation,g*25,25)')
    text=replace(text,'put(d.generation_in,g*8,8,5);put(d.live_generations,g*16,8,5);put(d.live_generations,g*16+8,8,5);','put(d.generation_in,g*25,25,0x1555505);put(d.live_generations,g*50,25,0x1555505);put(d.live_generations,g*50+25,25,0x1555505);')
    text=replace(text,'put(h.d.generation_in,g*8,8,6)','put(h.d.generation_in,g*25,25,0x1555506)')
    text=replace(text,'void compare(){','void compare(){\n  require(d.old_bad==d.new_bad && d.old_phase==d.new_phase && d.old_head_valid==d.new_head_valid && d.old_malformed==d.new_malformed,"R7_PAIR_PRE_OWNER_PHASE");')
    insert='''  unsigned tag_cases=0;
  for(unsigned geometry=0;geometry<16;geometry++)for(unsigned phase=0;phase<2;phase++)for(unsigned bit=0;bit<27;bit++){
   h.clear();h.legal(0,5000);unsigned age=5000;
   for(;;){
    h.drive(age);h.d.eval();h.compare();
    require(h.d.new_pending==0,"R7_TAG_LEGAL_BEFORE_MUTATION");
    if(((h.d.new_head_valid>>geometry)&1) && ((h.d.new_phase>>geometry)&1)==phase)break;
    h.edge();require(++age<10000,"R7_TAG_PHASE_WATCHDOG");
   }
   put(h.d.head_tag_xor,geometry*27,27,1u<<bit);h.d.eval();h.compare();
   require(((h.d.new_malformed>>geometry)&1)==0,"R7_TAG_NO_INPUT_MALFORMED_CONFOUND");
   require(((h.d.new_bad>>geometry)&1) && ((h.d.new_pending>>geometry)&1),"R7_TAG_ACTUAL_PRE_OWNER_FAULT");
   h.edge();require((h.d.new_error>>geometry)&1,"R7_TAG_REGISTERED_STICKY_ERROR");
   put(h.d.head_tag_xor,geometry*27,27,0);
   for(unsigned quiet=0;quiet<8;quiet++){
    h.drive(++age);h.edge();
    require(((h.d.new_error>>geometry)&1) && !((h.d.new_slot>>geometry)&1),"R7_TAG_ADMITTED_EDGE_THEN_QUIET");
   }
   tag_cases++;
  }
  require(tag_cases==864,"R7_TAG_CASES");
'''
    text=replace(text,'  for(unsigned test=0;test<6;test++){',insert+'  for(unsigned test=0;test<6;test++){')
    text=replace(text,'SHARED_COMM_FAULT_PASS geometries=16 protocol_cases=6 quarantine_cases=1 reset_cases=1',
        'R7_COMM_PAIR_FAULT_PASS geometries=16 gen25_bits=25 phase_pairs=2 tag_cases=864 protocol_cases=6 quarantine_cases=1 reset_cases=1')
    return text
def role():
    raw=CAPTURE.read_bytes();need(sha(raw)==CAPTURE_PIN,'OWN_R7_CAPTURE')
    bundle=json.loads(raw);names={};files={}
    old=(ROOT/'rtl/kernel'/(OLD+'.sv')).read_text()
    for side,module,leaf in [('old',OLD,old),('new',NEW,bundle['files'][NEW+'.sv'])]:
        names[side],text=clone(leaf,module,side);files['rtl/'+names[side]+'.sv']=text.encode()
    files['rtl/'+TOP+'.sv']=top_source(names).encode()
    for name in ('genefer_stream27_delay_mlab_v1.sv','genefer_stream27_mdc_fifo_smallreg_v1.sv','genefer_stream27_mdc_commutator_sync.sv'):
        files['rtl/'+name]=(ROOT/'rtl/kernel'/name).read_bytes()
    files['rtl/tb/r7_comm_pair_normal.cpp']=normal_source().encode()
    files['rtl/tb/native_runtime_context_v1.h']=(ROOT/'rtl/tb/native_runtime_context_v1.h').read_bytes()
    files['lineage/'+SELF]=(ROOT/SELF).read_bytes();files['lineage/r7-production-bundle.json']=raw
    pins={n:sha(value) for n,value in files.items()}
    snapshot={n:v for n,v in pins.items() if n.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-p16-c2-combo-r7-paired-fullgen25',source_snapshot=snapshot,
        candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND',source_root='UNBOUND',output_parent='UNBOUND',sources=pins,
        build=dict(top=TOP,sv_sources=[n for n in files if n.endswith('.sv')],cpp_source='rtl/tb/r7_comm_pair_normal.cpp',parameters={},
            cflags=['-std=c++17','-O2','-Werror=return-type'],runtime_threads=1),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='r7-paired-fullgen25-normal',argv=['{exe}'],expected_returncode=0,
            expected_stdout='R7_COMM_PAIR_NORMAL_PASS geometries=16 cycles=18000 lane_checks=2304000\n',expected_stderr='')],
        rtl_readiness=readiness,test_role='normal',r7_pair=dict(full_gen25=True,normal_injection_zero=True,diagnostic_tag_clones_reverse_exact=True,
            independent_deque_reference=True,original_packed_leaf_sha256=PINS[OLD],candidate_packed_leaf_sha256=PINS[NEW],
            no_production_RAM_fault_or_unknown_input_claim=True,promotion_allowed=False))
    return manifest,files
def fault_role():
    normal=BASE/'paired-normal-v1';raw=(normal/'manifest.json').read_bytes();manifest=json.loads(raw)
    files={name:(normal/'source/fpga'/name).read_bytes() for name in manifest['sources']}
    need(all(sha(files[n])==pin for n,pin in manifest['sources'].items()),'FROZEN_PAIRED_NORMAL')
    need(manifest['r7_pair']['normal_injection_zero'] and len(manifest['build']['sv_sources'])==6,'EXACT_PAIR_NORMAL_PARENT')
    cpp='rtl/tb/r7_comm_pair_fault.cpp';files[cpp]=fault_source().encode()
    files['lineage/r7-pair-fault-adapter.py']=(ROOT/SELF).read_bytes()
    manifest['build']['cpp_source']=cpp;manifest['sources']={name:sha(value) for name,value in files.items()}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='deliberate_fault')
    manifest['steps']=[dict(name='r7-paired-fullgen25-tag-faults',argv=['{exe}'],expected_returncode=0,
        expected_stdout='R7_COMM_PAIR_FAULT_PASS geometries=16 gen25_bits=25 phase_pairs=2 tag_cases=864 protocol_cases=6 quarantine_cases=1 reset_cases=1\n',expected_stderr='')]
    manifest['r7_pair'].update(normal_injection_zero=False,tag_xor_only=True,tag_cases=864,
        generation_bits=25,occupied_phases=2,pre_owner_bad_and_pending_lockstep=True,
        post_sticky_error_and_admitted_raw_output_lockstep=True,quarantine_reset_held_payload=True,
        no_input_malformed_confound_for_tag_cases=True,normal_manifest_sha256=sha(raw))
    return manifest,files
def prepare(*,fault=False):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    mode='fault' if fault else 'normal';out=BASE/('paired-'+mode+'-v1');need(not out.exists() and not any((ROOT/n).exists() for n in ('queue/PAUSE','docs/briefs/PAUSE')),'FRESH_UNPAUSED')
    manifest,files=fault_role() if fault else role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest);dump(out/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-combo-r7-paired-'+mode+'-'+pair+'-v1';packet=out/('packet-'+pair)
        result=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json');ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes())) for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id='s4-p16-c2-combo-r7-paired-'+mode+'-q1-v1',owner='merged-ntt-model',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,minimum_ram_rationale='Bounded16-geometry component exploration with4GiB cap, not a measured peak; same qualified packed primitive and diagnostic-only ports. DesiredGCP8 retained, failures preserved.',
        est_minutes=20 if fault else 15,promotion_bound=False,test_role='deliberate_fault' if fault else 'normal',rtl_readiness=manifest['rtl_readiness'],packages=variants,allowed_hosts=['gfn16-pilot-c4d','aethia'],after=['s4-p16-c2-combo-r7-paired-normal-q1-v1' if fault else 's4-p16-c2-combo-r7-aw8-normal-q1-v1'],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical);return dict(id=logical['id'],ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--fault',action='store_true');args=parser.parse_args()
    print(json.dumps(prepare(fault=args.fault),indent=2))
