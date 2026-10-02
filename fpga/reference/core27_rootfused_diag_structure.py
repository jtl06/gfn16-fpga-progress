"""A5 mechanical hierarchy-only extraction; no HDL/native/physical gate.

The parent stays frozen. Generated bodies are literal slices, not rewrites.
No new preservation, partition or hierarchy attributes are introduced.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

ENGINE='genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine'
ADAPTER='genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_engine'
CORE='genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont'
PREFIX='genefer_ntt_rootfused_diag'
ROOT=Path(__file__).resolve().parents[1]
PINS={
    'rtl/kernel/'+ENGINE+'.sv':'d52351bdf53c6809208f7a466848b4376cbd8ff87c52f633dc8c2814026b47ee',
    'rtl/kernel/'+ADAPTER+'.sv':'b3d06d1e5f90e4944fdf88ff264cb7edbd73d0daf9f46ccf93389ab4889d9e3f',
    'rtl/kernel/'+CORE+'.sv':'b6dbd4fccc6d7708fd295d3c82e2ebec444c4a2fbde8612851f10f979da04895',
    'rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont.cpp':'5680df12450b1c301361b23264f3a56a386e5e8dbecd5ca7ad1324ecd1dcd526',
    'rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_threaded.cpp':'2667f3662c90d931372d8f946deee2d54d898be61bae5bee8c2361fb84dc022e',
}


def require(ok,why):
    if not ok:raise ValueError(why)


def slice_once(text,start,end):
    require(text.count(start)==1,'unique start: '+start)
    a=text.index(start);b=text.index(end,a)
    return text[a:b]


def replace_once(text,before,after):
    require(text.count(before)==1,'unique replacement')
    return text.replace(before,after,1)


def signals(text):
    """Extract original packed/unpacked types for automatic control ports."""
    result={}
    header=text[text.index(') (')+3:text.index('\n);')]
    declarations=re.findall(r'(?:input|output) logic\s+(.+?)(?=\n\s*(?:input|output)|\Z)',header,re.S)
    declarations+=re.findall(r'^    logic\s+([^;]+);',text,re.M)
    for declaration in declarations:
        declaration=declaration.strip().rstrip(',')
        match=re.match(r'(\[[^\]]+\]\s*)?(.*)',declaration,re.S)
        packed=(match[1] or '').strip()
        for item in match[2].split(','):
            found=re.fullmatch(r'\s*(\w+)\s*((?:\[[^\]]+\]\s*)*)',item.strip())
            if found:result[found[1]]=('logic '+packed).strip()+'|'+found[2].strip()
    result['state']=PREFIX+'_types::state_t|'
    result['prefetch_state']=PREFIX+'_types::prefetch_t|'
    return result


def port(direction,name,types):
    kind,array=types[name].split('|')
    return '    '+direction+' '+kind+' '+name+(' '+array if array else '')


def generate(root=ROOT):
    root=Path(root)
    for name,digest in PINS.items():require(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,'frozen parent drift: '+name)
    old=(root/'rtl/kernel'/(ENGINE+'.sv')).read_text();new=old
    state_enum=slice_once(old,'    typedef enum logic [3:0]','    state_t state;')
    pf_enum=slice_once(old,'    typedef enum logic [1:0]','    prefetch_t prefetch_state;')
    params=slice_once(old,'    localparam int LW=','    typedef enum logic [3:0]')
    bankfun=slice_once(old,'    function automatic logic [KW-1:0] bank_of','    function automatic logic [KW-1:0] ror')
    rorfun=slice_once(old,'    function automatic logic [KW-1:0] ror','    function automatic int insert_zero')
    insertfun=slice_once(old,'    function automatic int insert_zero','    function automatic int remove_bit')
    removefun=slice_once(old,'    function automatic int remove_bit','    function automatic logic [RRW-1:0] phase_base')
    phasefun=slice_once(old,'    function automatic logic [RRW-1:0] phase_base','    function automatic bit fixed_position')
    types=signals(old)
    helpers=['// A5 diagnostic hierarchy only; literal frozen bodies, no new attributes.\n',
        'package '+PREFIX+'_types;\n'+state_enum+pf_enum+'endpackage\n']
    extracted={}
    def module(name,ports,body,functions=''):
        return ('module '+PREFIX+'_'+name+' #(parameter int AW=16,LANES=64,LANE=0,BANK=0,\n'
            '    parameter logic [31:0] P=32\'d104857601,Q=32\'d4190109697) (\n'+
            ',\n'.join(ports)+'\n);\n    import '+PREFIX+'_types::*;\n'+params+functions+body+'endmodule\n')
    def instance(name,inputs,outputs,extra=''):
        names=inputs+outputs
        return ('    '+PREFIX+'_'+name+' #(.AW(AW),.LANES(LANES),.P(P),.Q(Q)'+extra+') diagnostic_'+name+' (\n        '+
            ','.join('.'+n for n in names)+'\n    );\n')

    write=slice_once(old,'    for(genvar d=0;d<=LW;d=d+1) begin : vector_write_route','    for(genvar d=0;d<=LW;d=d+1) begin : vector_read_route')
    read=slice_once(old,'    for(genvar d=0;d<=LW;d=d+1) begin : vector_read_route','    assign host_bank=')
    host_common=['vector_base_bank','vector_base_bank_d','vector_write_data','effective_mask','data_q']
    for name,body,inputs,outs in (
        ('host_write_route',write,['vector_base_bank','vector_write_data','effective_mask'],['host_write_words','host_write_mask']),
        ('host_read_route',read,['vector_base_bank_d','data_q'],['host_read_words'])):
        t=dict(types,host_write_words='logic [31:0]|[0:LANES-1]',host_write_mask='logic [LANES-1:0]|',host_read_words='logic [31:0]|[0:LANES-1]')
        suffix=('    for(genvar h=0;h<LANES;h=h+1)begin\n        assign '+outs[0]+'[h]='+('vector_write_route' if name=='host_write_route' else 'vector_read_route')+'[LW].words[h];\n'+
            ('        assign host_write_mask[h]=vector_write_route[LW].mask[h];\n' if name=='host_write_route' else '')+'    end\n')
        helpers.append(module(name,[port('input',x,t) for x in inputs]+[port('output',x,t) for x in outs],body+suffix))
        new=replace_once(new,body,instance(name,inputs,outs));extracted[name]=body
    new=new.replace('vector_read_route[LW].words[h]','host_read_words[h]').replace('vector_write_route[LW].words[bank%LANES]','host_write_words[bank%LANES]').replace('vector_write_route[LW].mask[bank%LANES]','host_write_mask[bank%LANES]')
    declarations='    logic [31:0] host_write_words[0:LANES-1],host_read_words[0:LANES-1];\n    logic [LANES-1:0] host_write_mask;\n'

    rootbody=slice_once(old,'    logic [KW-1:0] route_xor,root_lane_mask;','    // Same-edge replicas:')
    # point_bank_d remains owned by the original control edge, not the route.
    rootbody=rootbody.replace('    logic [LW:0] point_bank_d;\n','')
    t=dict(types,root_words='logic [31:0]|[0:LANES-1]')
    inputs=['active_op','low_stage_d','stage_bit_d','base_bank_d','pairing_d','point_bank_d','generated_roots']
    outs=['root_words']
    helpers.append(module('root_clip_route',[port('input',x,t) for x in inputs]+[port('output',x,t) for x in outs],rootbody+
        '    for(genvar j=0;j<LANES;j=j+1)assign root_words[j]=generated_route[LW].words[j];\n',removefun))
    original=slice_once(old,'    logic [KW-1:0] route_xor,root_lane_mask;','    // Same-edge replicas:')
    new=replace_once(new,original,'    logic [LW:0] point_bank_d;\n'+instance('root_clip_route',inputs,outs))
    new=new.replace('generated_route[LW].words[lane]','root_words[lane]')
    declarations+='    logic [31:0] root_words[0:LANES-1];\n';extracted['root_clip_route']=rootbody

    bfbody=slice_once(old,'        for(genvar p=0;p<KW;p=p+1) begin : pair_patterns','        assign w=')
    bfbody=bfbody.replace('insert_zero(lane,p)','insert_zero(LANE,p)').replace('orientation_tiles[lane/ORIENT_TILE_LANES].orientation_q','orientation_q')
    t=dict(types,orientation_q='logic|',u='logic [31:0]|',v='logic [31:0]|')
    inputs=['data_q','pairing_d','orientation_q'];outs=['u','v']
    helpers.append(module('butterfly_read_route',[port('input',x,t) for x in inputs]+[port('output',x,t) for x in outs],
        '        logic [31:0] data_lo [0:KW-1],data_hi [0:KW-1];\n'+bfbody,insertfun))
    original=slice_once(old,'        for(genvar p=0;p<KW;p=p+1) begin : pair_patterns','        assign w=')
    new=replace_once(new,original,'        '+PREFIX+'_butterfly_read_route #(.AW(AW),.LANES(LANES),.LANE(lane),.P(P),.Q(Q)) diagnostic_read_pair (\n            .data_q,.pairing_d,.orientation_q(orientation_tiles[lane/ORIENT_TILE_LANES].orientation_q),.u,.v\n        );\n')
    new=replace_once(new,'        logic [31:0] data_lo [0:KW-1],data_hi [0:KW-1];\n','');extracted['butterfly_read_route']=bfbody

    writebody=slice_once(old,'        logic [31:0] bf_write_option [0:KW-1];','        genefer_sdp_ram32 #')
    # Literal body, with only generated bank index and boundary nets renamed.
    bankbody=re.sub(r'\bbank\b','BANK',writebody)
    for n in ('data_re','data_we','root_re','data_ra','data_wa','root_ra','data_w'):
        bankbody=bankbody.replace(n+'[BANK]',n)
    bankbody=bankbody.replace('vector_write_route[LW].words[BANK%LANES]','host_write_words[BANK%LANES]').replace('vector_write_route[LW].mask[BANK%LANES]','host_write_mask[BANK%LANES]')
    outs=['data_re','data_we','root_re','data_ra','data_wa','root_ra','data_w','bf_address','root_address','root_variable']
    t=dict(types,host_write_words='logic [31:0]|[0:LANES-1]',host_write_mask='logic [LANES-1:0]|',
        data_re='logic|',data_we='logic|',root_re='logic|',data_ra='logic [RW-1:0]|',data_wa='logic [RW-1:0]|',root_ra='logic [RRW-1:0]|',data_w='logic [31:0]|',
        bf_address='logic [31:0]|',root_address='logic [31:0]|',root_variable='logic [KW-1:0]|')
    ids=set(re.findall(r'\b\w+\b',bankbody));inputs=sorted((ids&set(t))-set(outs)-{'bf_write_option','bf_valid_option'})
    # Remove locally declared exported wires; ports are their declarations.
    bankbody=bankbody.replace('        logic [KW-1:0] bf_valid_option,root_variable;','        logic [KW-1:0] bf_valid_option;').replace('        logic [31:0] bf_address,root_address;\n','')
    helpers.append(module('bank_access_route',[port('input',x,t) for x in inputs]+[port('output',x,t) for x in outs],bankbody,removefun+rorfun))
    connections=[('.'+x+'('+x+'[bank])') if x in ('data_re','data_we','root_re','data_ra','data_wa','root_ra','data_w') else '.'+x for x in inputs+outs]
    current_writebody=writebody.replace('vector_write_route[LW].words[bank%LANES]','host_write_words[bank%LANES]').replace('vector_write_route[LW].mask[bank%LANES]','host_write_mask[bank%LANES]')
    new=replace_once(new,current_writebody,'        logic [31:0] bf_address,root_address;\n        logic [KW-1:0] root_variable;\n        '+PREFIX+'_bank_access_route #(.AW(AW),.LANES(LANES),.BANK(bank),.P(P),.Q(Q)) diagnostic_access (\n            '+','.join(connections)+'\n        );\n')
    extracted['bank_access_route']=bankbody

    reset='            for(int t=0;t<7;t=t+1) for(int b=0;b<BANKS;b=b+1) row_tag[t][b]<=0;\n'
    rowbody=slice_once(old,'            for(int b=0;b<BANKS;b=b+1) begin\n                row_tag[0]','            for(int lane=0;lane<LANES;lane=lane+1) begin')
    helpers.append(module('row_tag_pipeline',[port('input',x,types) for x in ('clk','rst_n','data_ra')]+[port('output','row_tag',types)],
        '    always_ff @(posedge clk or negedge rst_n)begin\n        if(!rst_n)begin\n'+reset+'        end else begin\n'+rowbody+'        end\n    end\n'))
    new=replace_once(new,reset,'');new=replace_once(new,rowbody,'');extracted['row_tag_pipeline']=reset+rowbody
    declarations+=instance('row_tag_pipeline',['clk','rst_n','data_ra'],['row_tag'])

    a=new.rfind('    always_ff @(posedge clk or negedge rst_n) begin');control=new[a:new.rfind('endmodule')]
    outputs=sorted(set(re.findall(r'\b(\w+)(?:\[[^\n]*?\])?\s*<=',control)))
    require(set(outputs)<=set(types),'all control outputs typed: '+str(set(outputs)-set(types)))
    inputs=sorted((set(re.findall(r'\b\w+\b',control))&set(types))-set(outputs))
    helpers.append(module('stage_phase_control',[port('input',x,types) for x in inputs]+[port('output',x,types) for x in outputs],control,bankfun+phasefun))
    new=replace_once(new,control,instance('stage_phase_control',inputs,outputs));extracted['stage_phase_control']=control
    new=replace_once(new,state_enum,'    import '+PREFIX+'_types::*;\n')
    new=replace_once(new,pf_enum,'')
    new=replace_once(new,'    assign next_stage=',declarations+'    assign next_stage=')
    new=replace_once(new,'module '+ENGINE+' #','module '+ENGINE+'_diag #')
    helpers_text='\n'.join(helpers)
    # Attribute count is invariant: inherited orientation tile attributes only.
    require(new.count('(*')==old.count('(*') and '(*' not in helpers_text,'no new hierarchy/placement attributes')
    result={'rtl/kernel/'+ENGINE+'_diag.sv':new,'rtl/kernel/'+PREFIX+'_blocks.sv':helpers_text}
    adapter=(root/'rtl/kernel'/(ADAPTER+'.sv')).read_text()
    adapter=replace_once(adapter,'module '+ADAPTER+' #','module '+ADAPTER+'_diag #')
    adapter=replace_once(adapter,ENGINE+' #',ENGINE+'_diag #')
    result['rtl/kernel/'+ADAPTER+'_diag.sv']=adapter
    core=(root/'rtl/kernel'/(CORE+'.sv')).read_text()
    core=replace_once(core,'module '+CORE+' #','module '+CORE+'_diag #')
    core=replace_once(core,ADAPTER+' #',ADAPTER+'_diag #')
    result['rtl/kernel/'+CORE+'_diag.sv']=core
    bench=CORE.removeprefix('genefer_')
    for suffix in ('.cpp','_threaded.cpp'):
        text=(root/'rtl/tb'/(bench+suffix)).read_text()
        # Only exact top/header/include identities change. Metrics, arithmetic
        # oracle, readbacks, priorities, return0 and thread guards are unchanged.
        text=text.replace(CORE,CORE+'_diag').replace(bench+'.cpp',bench+'_diag.cpp')
        result['rtl/tb/'+bench+'_diag'+suffix]=text
    return result,extracted


def validate(root=ROOT):
    generated,blocks=generate(root)
    for name,text in generated.items():require((Path(root)/name).read_text()==text,'diagnostic body/connection drift: '+name)
    return dict(status='source_only_not_HDL_qualified',parent_sha256=PINS,
        generated_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in generated.items()},
        extracted_bodies={name:hashlib.sha256(text.encode()).hexdigest() for name,text in blocks.items()},
        added_preserve_partition_attributes=0,
        native_required=['AW5 andAW16 matched whole-core outputs and EVERY cycle metric identical to rootfused_crtmont',
            'Exact profile/host arbitration, reset/error/readback tests; paired parent control',
            'Synthesis-only matched settings/part/seed/version; totals within approximately1percent, explain larger change',
            'Per-field entity ALMs/ALUTs/registers/M20K/DSP table; synthesis estimates are not fitted-needed resources'])


def manifest(root=ROOT):
    root=Path(root);report=validate(root)
    parent=root/'reference/core27_prefetch_r2_rootfused_crtmont_regression.py'
    require(hashlib.sha256(parent.read_bytes()).hexdigest()=='95898756fd1c8c547343341428836379e90400644659635bd7dc77010107b208','frozen G4 runner pin')
    order=None
    for node in ast.parse(parent.read_text()).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='COMPILED_ORDER' for t in node.targets):order=ast.literal_eval(node.value)
    require(order is not None and len(order)==16,'exact parent16kernel closure')
    replacements={n+'.sv':n+'_diag.sv' for n in (ENGINE,ADAPTER,CORE)}
    compiled=['rtl/kernel/'+PREFIX+'_blocks.sv']+['rtl/kernel/'+replacements.get(n,n) for n in order]
    require(len(compiled)==len(set(compiled))==17,'diagnostic17kernel closure')
    pins={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in compiled}
    generated,_=generate(root);pins.update(report['generated_sha256'])
    for name in ('reference/core27_rootfused_diag_structure.py','tests/test_core27_rootfused_diag_structure.py'):
        pins[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    return dict(task='B20260930A-A5',status='source_prepared_NOT_native_or_synthesis_qualified',
        parent='rootfused_crtmont',top=CORE+'_diag',compiled_order=compiled,sources=pins,
        ancestry=report['parent_sha256'],extracted_bodies=report['extracted_bodies'],
        diagnostic_modules=[PREFIX+'_'+n for n in report['extracted_bodies']],
        diagnostic_split_only=True,added_constraints_or_preservation_attributes=0,
        inherited_orientation_tile_preserve_dont_merge_unchanged=True,
        source_only_tests=dict(count=9,status='PASS',class_='Python source/mapping, not HDL'),
        dispatch_authorized=False,native_gates_required=report['native_required'],
        synthesis_plan='After native identity: matched parent/control and diagnostic AW16 whole-core SYNTHESIS ONLY, same26.1/part/constraints/settings/seed. No fit/route/STA. Capture all3field entities and residual engine/profile logic; compiler flattening may limit attribution, do not add preservation to force it.',
        limitations=['Package enum type extracted unchanged to allow strongly typed ports; native elaboration still required.',
            'No arithmetic optimization, new register, pipeline cycle, profile behavior or RAM ownership intended.',
            'Synthesis totals/entities may change from boundary optimization: approximately1percent identity budget is a diagnostic gate, not a guarantee.',
            'No measured synthesis/neededALM/LAB, clock, cycle saving or hardware claim.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--emit-patch',action='store_true');parser.add_argument('--manifest',action='store_true')
    args=parser.parse_args()
    if args.emit_patch:
        generated,_=generate();print('*** Begin Patch')
        for name,text in generated.items():
            require(not (ROOT/name).exists(),'fresh diagnostic source required')
            print('*** Add File: '+str(ROOT/name))
            for line in text.splitlines():print('+'+line)
        print('*** End Patch')
    else:print(json.dumps(manifest() if args.manifest else validate(),indent=2))
