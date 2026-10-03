"""Default-OFF fixed internal ingress calendar on immutable FIELD100.

Only feedback/correction proposal controls change. Numeric/tag pipelines,
R6 cold acceptance one-shot, descriptor FIFO and public FAST fences remain.
An observation mismatch is a new typed functional framing fault, never a
permission to stall, skip a row or mask an incorrect payload.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
from . import stream27_r15_fixed_schedule_model as model

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_r15_fixed_schedule_bind.py'
MODEL = 'reference/stream27_r15_fixed_schedule_model.py'
BASE=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1'
PARENTS={256:('aw8-normal','dd8d9196a5ac79381b8e701d021d19a067dde4d319b15799b13f8d8f61441a00'),
         65536:('full-normal-v2','f5f0617d989b64bb965b612a0d0cb8b6074c1ecd4f85f01ed66f970dfbf521f2')}


def sha(raw):
    return hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError('R15_FIXED_SCHEDULE_' + why)


def capture(n):
    need(type(n) is int and n in PARENTS,'CLOSED_CAPTURE')
    stage,pin=PARENTS[n]
    raw=(BASE/stage/'production-bundle.json').read_bytes()
    need(sha(raw)==pin,'IMMUTABLE_FIELD100')
    return json.loads(raw)


def calendar_text(g):
    interval, rows, boundary = model.constants(g)
    bits = (interval-1).bit_length()
    return f''' // R15: PRE-edge calendar anchored only by actual cold frame acceptance.
 localparam int R15_INTERVAL={interval},R15_PHASE_W={bits},R15_BOUNDARY_PHASE={boundary % interval};
 logic [R15_PHASE_W-1:0] r15_phase[0:1];logic [1:0] r15_armed,r15_tail;
 wire [1:0] r15_first,r15_row,r15_correction;
 for(genvar s=0;s<2;s++)begin: r15_internal_calendar
  assign r15_first[s]=r15_armed[s] && active[s] && remaining[s]!=0 && r15_phase[s]==R15_PHASE_W'(R15_INTERVAL-1);
  assign r15_row[s]=r15_first[s] || (r15_armed[s] && active[s] && r15_tail[s] && r15_phase[s]<R15_PHASE_W'(ROWS-1));
  assign r15_correction[s]=r15_armed[s] && feedback_enabled[s] && r15_phase[s]==R15_PHASE_W'(R15_BOUNDARY_PHASE);
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin r15_phase[s]<=0;r15_armed[s]<=0;r15_tail[s]<=0;end
   else if(frame_accept && context_in==s)begin r15_phase[s]<=R15_PHASE_W'(1);r15_armed[s]<=1;r15_tail[s]<=0;end
   else if(r15_armed[s])begin
    r15_phase[s]<=r15_phase[s]==R15_PHASE_W'(R15_INTERVAL-1) ? R15_PHASE_W'(0) : r15_phase[s]+R15_PHASE_W'(1);
    if(r15_phase[s]==R15_PHASE_W'(R15_INTERVAL-1))r15_tail[s]<=active[s] && remaining[s]!=0;
    else if(r15_phase[s]==R15_PHASE_W'(ROWS-2))r15_tail[s]<=0;
   end
  end
 end
 wire observed_feedback_slot,observed_feedback_start;
 wire observed_auto_correction=boundary_valid && feedback_enabled[boundary_context] && !local_error;
 wire feedback_slot=(|r15_row) && !local_error;
 wire feedback_start=(|r15_first);
 wire auto_correction=(|r15_correction) && !local_error;
 wire r15_calendar_bad=!error_barrier && !local_error &&
  ((r15_row==2'b11) || (r15_correction==2'b11) ||
   (feedback_slot!=observed_feedback_slot) ||
   (feedback_slot && (feedback_start!=observed_feedback_start || feedback_owner[24]!=r15_row[1])) ||
   (auto_correction!=observed_auto_correction) ||
   (auto_correction && boundary_context!=r15_correction[1]));
'''


def bind(bundle, fixed_schedule=0):
    need(type(fixed_schedule) is int and fixed_schedule in (0, 1), 'BOOL_FLAG')
    out = copy.deepcopy(bundle)
    if not fixed_schedule:
        return out
    need('FIXED_SCHEDULE' not in bundle['parameters'], 'NOT_ALREADY_BOUND')
    need(bundle['geometry']['n'] in (256, 65536) and bundle['geometry']['p']==16 and
         bundle['parameters'].get('FEEDBACK_INGRESS_REG')==1 and
         bundle['parameters'].get('AUTO_CORRECTION_INGRESS_REG')==1, 'CLOSED_PARENT')
    files = dict(bundle['files'])
    warm = [name for name, text in files.items() if
            ' wire raw_command_needed=feedback_slot && feedback_start' in text]
    need(len(warm)==1, 'ONE_WARM_ROLE')
    warm = warm[0]
    ops = []

    def edit(old, new):
        need(files[warm].count(old)==1, 'UNIQUE_ANCHOR:'+old[:60])
        files[warm] = files[warm].replace(old, new, 1)
        ops.append([old,new])

    edit(' wire auto_correction=boundary_valid && feedback_enabled[boundary_context] && !local_error;\n wire feedback_slot,feedback_start;',
         calendar_text(bundle['geometry']))
    # Preserve the numeric payload producer, including AW8's original D18
    # FIFO and its full25 owner. Only qualified proposal controls are retimed
    # from observation to the zero-latency lockstep calendar.
    for old in ('assign feedback_slot=fifo_valid[17] && !local_error;',
                'assign feedback_slot=feedback_issue;'):
        if old in files[warm]:
            edit(old, old.replace('feedback_slot=', 'observed_feedback_slot='))
            break
    else:
        need(False, 'EXACT_FEEDBACK_VALID_PRODUCER')
    old = 'assign feedback_start=fifo_start[17];' if 'assign feedback_start=fifo_start[17];' in files[warm] else 'assign feedback_start=digit_start;'
    edit(old, old.replace('feedback_start=', 'observed_feedback_start='))
    # Same raw descriptor/collision setter roster remains, with one explicit
    # calendar mismatch added. It reaches local sticky FAST on this edge.
    for old in ('else if(error_barrier || collision || command_bad || count_bad || cold_request_bad)begin',
                'always_ff @(posedge clk)if(rst_n && !error_barrier && !collision && !command_bad && !count_bad && !cold_request_bad)begin',
                'if(child_barrier || collision || count_bad || command_bad || cold_request_bad)local_error<=1;',
                'assign fault_pending=out_error || child_pending || collision || count_bad || command_bad || cold_request_bad;'):
        if old.startswith('always_ff'):
            new=old.replace(' && !cold_request_bad)', ' && !cold_request_bad && !r15_calendar_bad)')
        else:
            new=old.replace('cold_request_bad', 'cold_request_bad || r15_calendar_bad')
        edit(old,new)
    # Clone modified definition and its host caller. Other 56 production
    # definitions are byte-literal unless composed by another distinct flag.
    host = out['top']+'.sv'
    old_host = files[host]
    need(files[host].count('CONTEXTS=2,')==1, 'HOST_PARAMETER_ANCHOR')
    files[host] = files[host].replace('CONTEXTS=2,', 'CONTEXTS=2,FIXED_SCHEDULE=1,',1)
    mapping={warm[:-3]:warm[:-3]+'_r15_fixed_v1',out['top']:out['top']+'_r15_fixed_v1'}
    new_files={}
    records={}
    for name,text in files.items():
        if name not in (warm,host):
            new_files[name]=text
            continue
        for old,new in mapping.items():
            text=re.sub(r'\b'+re.escape(old)+r'\b',new,text)
        newname=mapping[name[:-3]]+'.sv'
        reverse=text
        for old,new in mapping.items():
            reverse=re.sub(r'\b'+re.escape(new)+r'\b',old,reverse)
        if name==warm:
            for old,new in reversed(ops):
                need(reverse.count(new)==1,'UNIQUE_REVERSE');reverse=reverse.replace(new,old,1)
        else:
            reverse=reverse.replace('CONTEXTS=2,FIXED_SCHEDULE=1,','CONTEXTS=2,',1)
        need(reverse==bundle['files'][name], 'LITERAL_REVERSE:'+name)
        new_files[newname]=text
        records[newname]=dict(parent=name,edits=ops if name==warm else [],reverse_exact=True)
    deps=list(dict.fromkeys(out['source_dependencies']+[SELF,MODEL]))
    out.update(files=new_files,top=mapping[out['top']],rtl_sources=list(new_files),
               parameters=dict(out['parameters'],FIXED_SCHEDULE=1),source_dependencies=deps,
               source_sha256={p:sha((ROOT/p).read_bytes()) for p in deps},
               generated_sha256={n:sha(t) for n,t in new_files.items()})
    out['r15_fixed_schedule']=dict(enabled=True,parent_top=bundle['top'],modified=records,
        module_mapping=mapping,proof=model.prove(bundle['geometry']),
        descriptor_fifo_retained=True,descriptor_underflow_typed_fault=True,
        external_IO_CDC_backpressure_retained=True,active_pipeline_stall_added=False,
        cold_one_shot_actual_accept_literal=True,complete_feedback_correction_tuple_literal=True,
        geometry_unchanged=True,latency_delta=0,protected_checks_retained=True,
        native_qualified=False,clock_or_area_gain_claim=False)
    return out


def prepare(n=256, fixed_schedule=0):
    return bind(capture(n),fixed_schedule)
