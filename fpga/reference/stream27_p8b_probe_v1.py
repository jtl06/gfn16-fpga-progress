"""P8-b canonical27 + small-register delays + merged roots + registered faults.

Uses the frozen connected P16-c emitter only as a checked topology/transport
template. No lazy arithmetic or 28-bit token is retained in the emitted P8-b.
Full-size generation is scalar ROM constants only, never a numerical NTT.
"""
import hashlib
import json
from pathlib import Path
import re
import tarfile
from . import stream27_p16c_physical_probe_v1 as parent

ROOT=Path(__file__).resolve().parents[1]
PARENT_SHA='a16996d16f0ad79a71b5a2941150441fee23b55a16a418329dbc3105cc933fab'
CELL='genefer_stream27_canonical_butterfly_transport_v1'


def canonical_cell():
    return '''// Canonical27 six-edge transport over the frozen canonical butterfly.
module genefer_stream27_canonical_butterfly_transport_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697,parameter int TAG_W=1)(
 input logic clk,rst_n,in_valid,gs,input logic [26:0] u,v,w,
 input logic [TAG_W-1:0] in_tag,output logic out_valid,
 output logic [26:0] y0,y1,output logic [TAG_W-1:0] out_tag);
 wire [31:0] wide_y0,wide_y1;
 logic [TAG_W-1:0] tags[0:5];
 genefer_ntt_difdit_butterfly27 #(.P(P),.Q(Q)) arithmetic (
  .clk,.rst_n,.in_valid,.dif(gs),.u({5'b0,u}),.v({5'b0,v}),.w({5'b0,w}),
  .out_valid,.y0(wide_y0),.y1(wide_y1));
 assign y0=wide_y0[26:0];assign y1=wide_y1[26:0];assign out_tag=tags[5];
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin for(int i=0;i<6;i=i+1)tags[i]<='0;end
  else begin tags[0]<=in_tag;for(int i=1;i<6;i=i+1)tags[i]<=tags[i-1];end
 end
 // synthesis translate_off
 always @(posedge clk)if(rst_n && in_valid && ({5'b0,u}>=P || {5'b0,v}>=P || {5'b0,w}>=P))
  $fatal(1,"P8B_NONCANONICAL_BUTTERFLY_INPUT");
 always @(posedge clk)if(rst_n && out_valid && (wide_y0>=P || wide_y1>=P))
  $fatal(1,"P8B_NONCANONICAL_BUTTERFLY_OUTPUT");
 // synthesis translate_on
endmodule
'''


def transform(n,field,inverse,roots):
    name,text,plan=parent.transform_source(n,8,field,inverse,roots)
    newname=name.replace('stream28_','stream27_').replace('_v1','_p8b_v1')
    text=text.replace(name,newname).replace('[223:0]','[215:0]').replace('Connected P16-c','Connected canonical P8-b')
    text=text.replace('.DATA_W(28)','.DATA_W(27)')
    # Rewrite only explicit data-lane selections; root bit packing stays27.
    pattern=r'((?:row_data|bf_data|data_out|data\[[^\]]+\])\[)([0-9]+)\+:28\]'
    def lane(match):
        offset=int(match[2]);assert offset%28==0
        return match[1]+str(offset//28*27)+'+:27]'
    text=re.sub(pattern,lane,text)
    text=text.replace('genefer_ntt_lazy28_butterfly_v1',CELL)
    if inverse:
        final=plan['stages'][-1]
        for k,(lo,hi) in enumerate(final['pairs']):
            lines=text.splitlines(keepends=True)
            remove=[line for line in lines if any(token in line for token in
                (f'wire [27:0] raw_u{k}=',f'wire [26:0] canonical_u{k}=',f'wire [26:0] canonical_v{k}='))]
            assert len(remove)==3
            for line in remove:text=text.replace(line,'',1)
            text=text.replace(".u({5'b0,canonical_u"+str(k)+"}),.v({5'b0,canonical_v"+str(k)+"}),",
                f".u({{5'b0,row_data[{lo*27}+:27]}}),.v({{5'b0,row_data[{hi*27}+:27]}}),")
        text=re.sub(r"\{1'b0,(y[01]_[0-9]+\[26:0\])\}",r'\1',text)
    assert '+:28]' not in text and 'canonical_u' not in text and 'raw_u' not in text
    return newname,text,plan


def compile_probe(n=32,field=0,*,allow_full_constants=False):
    assert hashlib.sha256((ROOT/'reference/stream27_p16c_physical_probe_v1.py').read_bytes()).hexdigest()==PARENT_SHA
    parent.source_guard()
    base=parent.compile_probe(n,8,field,allow_full_constants=allow_full_constants)
    roots=parent.compile_roots(n,8,field,allow_full_constants=allow_full_constants)
    ct=transform(n,field,False,roots);gs=transform(n,field,True,roots)
    files={name:text for name,text in base['files'].items() if not any(token in name for token in
        ('lazy28_butterfly','mul28x27','stream28_merged_ct','stream28_merged_gs',base['top']))}
    files[CELL+'.sv']=canonical_cell();files[ct[0]+'.sv']=ct[1];files[gs[0]+'.sv']=gs[1]
    oldtop,top=parent.top_source(n,8,field,ct[0],gs[0],'genefer_stream27_square_p8_f'+str(field)+'_v1')
    name=oldtop.replace('p16c','p8b')
    top=top.replace(oldtop,name).replace('[223:0]','[215:0]').replace('[27:0] raw_spectrum','[26:0] raw_spectrum')
    top=top.replace('lane*28+:28','lane*27+:27').replace('lane*28+:27','lane*27+:27')
    top=top.replace("{1'b0,data_in[lane*27+:27]}", 'data_in[lane*27+:27]')
    top=top.replace("{1'b0,square_data[lane*27+:27]}", 'square_data[lane*27+:27]')
    top=re.sub(r"27'\(raw_spectrum>=28'd[0-9]+ \? raw_spectrum-28'd[0-9]+ : raw_spectrum\)", 'raw_spectrum',top)
    # Reject an intrinsically invalid numeric input before canonical arithmetic;
    # controller_error still registers at this origin edge, then freezes work.
    assert top.count('accepted=rst_n && request_slot && !stop;')==1
    top=top.replace('accepted=rst_n && request_slot && !stop;','accepted=rst_n && request_slot && !stop && !range_bad;')
    prime=base['geometry']['prime']
    top=top.replace(f"raw_spectrum>=28'd{2*prime}",f"raw_spectrum>=27'd{prime}")
    top=top.replace(f"inv_data[lane*27+:27]>=28'd{prime}",f"inv_data[lane*27+:27]>=27'd{prime}")
    top=top.replace('P16C_','P8B_');files[name+'.sv']=top
    assert 'lane*28' not in top and 'raw_spectrum>=28' not in top
    geometry=dict(base['geometry'],data_internal_bits=27,token_total_bits=38)
    stages=ct[2]['stages']+gs[2]['stages']
    depths=[s['shuffle_depth_per_buffer'] for s in stages if s['shuffle_depth_per_buffer']]
    delay=8*sum(parent.m20k(depth,38) for depth in depths if depth>32)
    accounting=dict(measured=False,canonical_interior_pairs=(2*geometry['aw']-1)*4,
        canonical_final_GS_pairs=4,pointwise_multipliers=8,extra_upper_normalizers=4,
        DSP_planning_proxy=geometry['aw']*8+12,root_M20K_proxy=base['resource_basis']['root_M20K_proxy'],
        delay_M20K_proxy=delay,IO_root_M20K=0,short_FIFO_declared_data_bits=8*sum(d for d in depths if d<=32)*38,
        declared_token_bits=38,ALM_estimate=None,
        caveat='No lazy-area credit; memory legal-tiling and DSP counts are source proxies, not physical inference or placement.')
    return dict(top=name,files=files,geometry=geometry,calendar=base['calendar'],root_ledger=base['root_ledger'],
        root_data_sha256=base['root_data_sha256'],omitted=base['omitted'],
        resource_basis=accounting,
        source_parent_sha256=PARENT_SHA,
        exact_changes=['Canonical frozen27-bit CT/GS replaces lazy28 interior; no lazy arithmetic remains.',
            'P8, 27-bit physical data/38-bit declared tokens, C1/PAYLOAD1/GEN8.',
            'S-M1 shallow explicitregisters, mergedS-M2 roots/finalupper normalization andregisteredfaults retained.',
            'Invalid top-level input range is intrinsically rejected before canonical arithmetic; stickyfault still posts at origin edge.'],
        full_N_numeric_NTT_performed=False,physical_fit_qualified=False,promotion_allowed=False)


def prepare_physical(destination,n=65536,field=0,*,allow_full_constants=False):
    destination=Path(destination).resolve();assert not destination.exists()
    b=compile_probe(n,field,allow_full_constants=allow_full_constants)
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE '+parent.DEVICE,
        'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4','set_global_assignment -name SEED 1',
        'set_global_assignment -name SDC_FILE probe.sdc','set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on']
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in b['files']]
    qsf+=['set_parameter -name AW '+str(b['geometry']['aw']),'set_parameter -name CONTEXTS 1']
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+pin+'}' for pin in parent.PORTS]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
              'probe.sdc':parent.SDC,'run.tcl':parent.RUN_TCL}
    digest=lambda text:hashlib.sha256(text.encode()).hexdigest()
    manifest={k:v for k,v in b.items() if k!='files'}
    manifest.update(status='source_only_p8b_not_executed',edition='pro',device=parent.DEVICE,
        compile_processors=4,seed=1,clock_period_ns=10,address_width=b['geometry']['aw'],
        core_parameters={'AW':b['geometry']['aw'],'CONTEXTS':1},raw_multiplier_parameters=None,field_parameters=None,
        bitstream_generation=False,allowed_stages=['syn','fit','sta'],
        source_sha256={name:digest(text) for name,text in b['files'].items()},
        control_sha256={name:digest(text) for name,text in controls.items()})
    project=destination/'project';(project/'rtl').mkdir(parents=True)
    for name,text in b['files'].items():(project/'rtl'/name).write_text(text)
    for name,text in controls.items():(project/name).write_text(text)
    (project/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    from fpga.cloud.aws_fit_v6 import verify_project
    verify_project(project)
    closure={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(project.rglob('*')) if p.is_file()}
    receipt=dict(status='source_ready_native_and_physical_gates_pending',project_manifest_sha256=closure['manifest.json'],
        inputs=closure,geometry=b['geometry'],calendar=b['calendar'],resource_basis=b['resource_basis'],fit_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    with tarfile.open(destination/'source.tar.gz','x:gz') as archive:
        for name in closure:archive.add(project/name,arcname='project/'+name,recursive=False)
        archive.add(destination/'preparation.json',arcname='preparation.json',recursive=False)
    return receipt
