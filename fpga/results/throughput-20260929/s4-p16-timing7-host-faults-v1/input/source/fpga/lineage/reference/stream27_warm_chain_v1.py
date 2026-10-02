"""Faithful streamed-control long recurrence; frozen field/arithmetic reused."""
import hashlib
from . import stream27_host_core_v1 as host
from . import stream27_warm_recurrence_v1 as parent

ROOT=host.ROOT


def source(n,child,g):
    top,text=parent.source(n,child,g);newtop=top.replace('warm_recurrence','warm_chain')
    changes=[('module '+top+' #','module '+newtop+' #'),
        ('output logic frame_done,output logic [15:0] done_epoch);',
         '''input logic feed_mode,command_valid,command_double,
 input logic [31:0] command_index,input logic [7:0] command_generation,
 output logic command_accept,output logic [31:0] started_frames,digit_sequence,boundary_sequence,
 output logic [3:0] chain_error_code,
 output logic frame_done,output logic [15:0] done_epoch);'''),
        ('logic [31:0] remaining,launched,latched_mask,latched_count;',
         'logic [31:0] remaining,launched,latched_mask,latched_count,result_sequence;\n logic latched_feed_mode,current_feedback_double;'),
        ('wire child_slot=feedback_slot || cold_slot;',
         '''wire command_needed=latched_feed_mode && feedback_slot && feedback_start && !local_error;
 // Intrinsic head eligibility, not generic fault_pending gating. An empty or
 // wrong head never supplies an old/zero bit to an accepted first warm row.
 wire command_bad=command_needed && (!command_valid || command_index!=launched || command_generation!=chain_generation);
 wire child_slot=(feedback_slot || cold_slot) && !command_bad;'''),
        ('wire child_start=feedback_slot ? feedback_start : frame_start;',
         'wire child_start=(feedback_slot ? feedback_start : frame_start) && !command_bad;'),
        ('wire count_bad=cold_slot && frame_start && (square_count==0 || square_count>32\'d32);',
         "wire count_bad=cold_slot && frame_start && (square_count==0 || (!feed_mode && square_count>32'd32));"),
        ('assign fault_pending=out_error || child_pending || count_bad || collision;',
         '''assign fault_pending=out_error || child_pending || count_bad || collision || command_bad;
 assign command_accept=internal_frame_accept && latched_feed_mode && !command_bad;
 assign started_frames=launched;
 // Physical carry blocks never overlap: previous done precedes next first
 // digit. This producer's completed counter is therefore its full ordinal,
 // captured intrinsically on first digit and held through the boundary pair.
 assign digit_sequence=digit_start ? completed_frames : result_sequence;
 assign boundary_sequence=result_sequence;'''),
        ('.double_in(feedback_slot ? latched_mask[launched[4:0]] : double_in),',
         '.double_in(feedback_slot ? (feedback_start ? (latched_feed_mode ? command_double : latched_mask[launched[4:0]]) : current_feedback_double) : double_in),'),
        ('remaining<=0;launched<=0;latched_count<=0;latched_mask<=0;cold_remaining<=0;',
         'remaining<=0;launched<=0;latched_count<=0;latched_mask<=0;cold_remaining<=0;\n   result_sequence<=0;latched_feed_mode<=0;current_feedback_double<=0;chain_error_code<=0;'),
        ('if(count_bad || collision || child_error)local_error<=1;',
         '''if(count_bad || collision || child_error || command_bad)local_error<=1;
   if(chain_error_code==0)begin
    if(command_bad)chain_error_code<=!command_valid ? 4'd1 : (command_generation!=chain_generation ? 4'd2 : 4'd3);
    else if(count_bad)chain_error_code<=4'd4;
    else if(collision)chain_error_code<=4'd5;
    else if(child_error)chain_error_code<=4'd6;
   end
   if(digit_valid && digit_start)result_sequence<=completed_frames;'''),
        ('active<=1;remaining<=square_count-32\'d1;launched<=1;latched_count<=square_count;latched_mask<=double_mask;',
         "active<=1;remaining<=square_count-32'd1;launched<=1;latched_count<=square_count;latched_mask<=double_mask;latched_feed_mode<=feed_mode;result_sequence<=0;"),
        ('if(internal_frame_accept)begin remaining<=remaining-32\'d1;launched<=launched+32\'d1;end',
         "if(internal_frame_accept)begin remaining<=remaining-32'd1;launched<=launched+32'd1;current_feedback_double<=latched_feed_mode ? command_double : latched_mask[launched[4:0]];end")]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('S4_LONG_RECURRENCE_ANCHOR:'+old)
        text=text.replace(old,new)
    return newtop,text


def prepare(n=32,p=16,*,contexts=1,allow_full_constants=False):
    def field(n,p,field,**kwargs):
        kwargs['mode']='warm_signed';return host.shared.prepare(n,p,field,**kwargs)
    arithmetic=host.bind(host.three,compile_field=field,source=host.renamed(host.three.source))
    compiler=host.bind(parent,compile_core=arithmetic,source=source)
    b=compiler(n,p,contexts=contexts,allow_full_constants=allow_full_constants)
    g=b['geometry']
    if g['warm_interval']<=g['carry_done']-g['first_digit']:raise ValueError('S4_FULL_RESULT_ORDINAL_NONOVERLAP_PROOF')
    path='reference/stream27_warm_chain_v1.py';b['source_dependencies'].append(path);b['source_sha256'][path]=host.sha(path)
    b['scope']='Streamed-control1..UINT32_MAX recurrence source gate; frozen field/CRT/carry and accepted-edge calendar unchanged; host/canonical wrappers required.'
    b['control_contract']=dict(initial='double_in at actual cold first-row accept',next='Exact command index=launched and intrinsic generation before actual internal first-row accept; no empty bypass.',
        full_ordinal='Producer completed_frames on first digit, held through boundary; justified by carry_done-first_digit<warm_interval.',
        error_codes=dict(underflow=1,generation=2,index=3,count=4,collision=5,child=6),no_feedback_latency_added=True)
    return b
