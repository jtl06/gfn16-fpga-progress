"""Real two-context three-prime/CRT/shared-carry assembly.

Four frame metadata banks follow the lease allocator's lowest-prefree policy.
Each context retains an exact base/reciprocal/A/generation profile. The setup
unit and P carry lanes are shared; overlapping carry blocks are rejected.
This is arithmetic integration, not a recurrence or host publication promise.
"""
import hashlib
from pathlib import Path
from . import stream27_threefield_carry_param_v1 as parent
from . import stream27_shared_field_contexts as fields

ROOT = parent.ROOT
SELF = 'reference/stream27_threefield_contexts.py'


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('S4_CTX_CARRY_SOURCE_ANCHOR:' + before[:90])
    return text.replace(before, after, 1)


def source(n, p, bundles, mode):
    oldtop, s = parent.source(n, p, bundles, mode)
    top = oldtop + '_contexts2_v1'
    s = once(s, 'module ' + oldtop + ' #', 'module ' + top + ' #')
    s = once(s, 'CONTEXTS=1', 'CONTEXTS=2')
    s = once(s, 'CONTEXTS!=1', 'CONTEXTS!=2')
    s = once(s, 'input logic clk,rst_n,begin_setup,in_slot_valid,frame_start,context_enabled,double_in,',
             'input logic clk,rst_n,begin_setup,setup_context,in_slot_valid,frame_start,context_in,correction_context,double_in,\n input logic [1:0] context_enabled,')
    s = once(s, 'input logic [7:0] generation_in,live_generation,',
             'input logic [7:0] generation_in,input logic [15:0] live_generation,')
    s = once(s, 'output logic config_valid,setup_done,out_error,fault_pending,frame_accept,correction_accept,',
             'output logic [1:0] config_valid,output logic setup_done,setup_done_context,out_error,fault_pending,frame_accept,correction_accept,')
    s = once(s, 'output logic coefficient_valid,coefficient_start,',
             'output logic coefficient_valid,coefficient_start,coefficient_context,')
    s = once(s, 'output logic digit_valid,digit_start,digit_eligible,',
             'output logic digit_valid,digit_start,digit_eligible,digit_context,')
    s = once(s, 'output logic boundary_valid,boundary_eligible,',
             'output logic boundary_valid,boundary_eligible,boundary_context,')
    s = once(s, 'output logic frame_done,output logic [15:0] done_epoch);',
             'output logic frame_done,done_context,output logic [15:0] done_epoch);')
    s = once(s, 'TAG_W=24+ROW_W;', 'TAG_W=25+ROW_W;')
    s = once(s, 'wire [15:0] field_epoch[0:2];wire [7:0] field_generation[0:2];wire [1:0] field_owners[0:2];',
             'wire [15:0] field_epoch[0:2];wire [7:0] field_generation[0:2];wire [2:0] field_owners[0:2];\n wire [2:0] field_context;wire [1:0] field_correction_bank[0:2],field_pointwise_bank[0:2],field_sink_bank[0:2];')
    s = once(s, 'logic [15:0] bank_epoch[0:1];logic [7:0] bank_generation[0:1];logic bank_double[0:1];\n logic [31:0] bank_base[0:1];',
             '''logic [15:0] bank_epoch[0:3];logic [7:0] bank_generation[0:3];logic bank_double[0:3],bank_context[0:3];
 logic [31:0] bank_base[0:3];logic [3:0] bank_live;
 logic [1:0] metadata_free;logic metadata_free_found,setup_owner_busy;
 always_comb begin
  metadata_free='0;metadata_free_found=0;setup_owner_busy=0;
  for(int i=0;i<4;i=i+1)begin
   if(!bank_live[i] && !metadata_free_found)begin metadata_free=2'(i);metadata_free_found=1;end
   if(bank_live[i] && bank_context[i]==setup_context)setup_owner_busy=1;
  end
 end
 logic setup_context_q;
 logic [31:0] profile_base[0:1];logic [95:0] profile_reciprocal[0:1];
 logic [76:0] profile_limit[0:1];logic [7:0] profile_generation[0:1];
 wire unit_config_valid,unit_setup_done;''')
    s = once(s, '.busy(setup_busy),.done(setup_done),.error(setup_error),.config_valid,',
             '.busy(setup_busy),.done(unit_setup_done),.error(setup_error),.config_valid(unit_config_valid),')
    for f in range(3):
        start = s.index(' field' + str(f) + ' (')
        end = s.index(');', start)
        part = s[start:end]
        part = once(part, '.context_enabled(context_enabled && !out_error),',
                    '.context_enabled(context_enabled & {2{!out_error}}),.context_in,.correction_context,')
        part = once(part, f'.generation_out(field_generation[{f}]),',
                    f'.generation_out(field_generation[{f}]),.out_context(field_context[{f}]),.commit_context(),')
        part = once(part, f'.owner_count(field_owners[{f}]),',
                    f'.owner_count(field_owners[{f}]),.correction_bank(field_correction_bank[{f}]),\n  .pointwise_bank(field_pointwise_bank[{f}]),.sink_bank(field_sink_bank[{f}]),')
        s = s[:start] + part + s[end:]
    s = once(s, 'wire bank=field_epoch[0][0];', 'wire [1:0] bank=field_sink_bank[0];')
    s = once(s, 'logic [15:0] carry_epoch;logic [7:0] carry_generation;',
             'logic [15:0] carry_epoch;logic [7:0] carry_generation;logic carry_context;\n logic doubled_context;')
    s = once(s, 'assign coefficient_data=$signed(doubled_data);assign coefficient_row=doubled_row;',
             'assign coefficient_data=$signed(doubled_data);assign coefficient_row=doubled_row;assign coefficient_context=doubled_context;')
    s = once(s, 'assign digit_epoch=carry_epoch;assign digit_generation=carry_generation;',
             'assign digit_epoch=carry_epoch;assign digit_generation=carry_generation;assign digit_context=carry_context;')
    s = once(s, 'assign digit_eligible=digit_valid && context_enabled && carry_generation==live_generation;',
             "assign digit_eligible=digit_valid && context_enabled[carry_context] && carry_generation==8'(live_generation>>(carry_context*8));")
    s = once(s, 'assign boundary_eligible=boundary_valid && context_enabled && carry_generation==live_generation;',
             "assign boundary_context=carry_context;\n assign boundary_eligible=boundary_valid && context_enabled[carry_context] && carry_generation==8'(live_generation>>(carry_context*8));")
    s = once(s, 'assign frame_done=(&lane_done) && !out_error;assign done_epoch=carry_epoch;',
             'assign frame_done=(&lane_done) && !out_error;assign done_epoch=carry_epoch;assign done_context=carry_context;')
    s = once(s, 'field_eligible[f]!=field_eligible[0])join_bad=1;',
             'field_eligible[f]!=field_eligible[0] || field_context[f]!=field_context[0] ||\n    field_sink_bank[f]!=field_sink_bank[0])join_bad=1;')
    s = once(s, 'if(!config_valid || bank_base[bank]!=qualified_base || bank_epoch[bank]!=field_epoch[0] ||\n    bank_generation[bank]!=field_generation[0])join_bad=1;',
             'if(!config_valid[field_context[0]] || !bank_live[bank] ||\n    bank_base[bank]!=profile_base[field_context[0]] || bank_context[bank]!=field_context[0] ||\n    bank_epoch[bank]!=field_epoch[0] || bank_generation[bank]!=field_generation[0])join_bad=1;')
    s = once(s, 'admission_bad=(in_slot_valid && frame_start && (!config_valid || base_in!=qualified_base)) ||\n   (begin_setup && (in_slot_valid || correction_valid || (|lane_busy) || (|field_owners[0])));',
             '''admission_bad=(in_slot_valid && frame_start && (!config_valid[context_in] ||
    base_in!=profile_base[context_in] || generation_in!=profile_generation[context_in] || !metadata_free_found)) ||
   (begin_setup && (in_slot_valid || correction_valid || setup_busy || setup_owner_busy ||
    ((|lane_busy) && carry_context==setup_context)));
  if((|field_frame_accept) && !(&field_frame_accept))admission_bad=1;
  if((|field_correction_accept) && !(&field_correction_accept))admission_bad=1;''')
    s = once(s, '.base(qualified_base),.reciprocal,.coefficient_limit,',
             '.base(profile_base[field_context[0]]),.reciprocal(profile_reciprocal[field_context[0]]),.coefficient_limit(profile_limit[field_context[0]]),')
    s = once(s, 'crt_tag[0]<={field_epoch[0],field_generation[0],field_row[0]};',
             'crt_tag[0]<={field_context[0],field_epoch[0],field_generation[0],field_row[0]};')
    s = once(s, "doubled_row<=crt_tag[15][ROW_W-1:0];doubled_start<=crt_tag[15][ROW_W-1:0]==0;",
             'doubled_row<=crt_tag[15][ROW_W-1:0];doubled_start<=crt_tag[15][ROW_W-1:0]==0;doubled_context<=crt_tag[15][TAG_W-1];')
    s = once(s, 'if(!rst_n)begin out_error<=0;doubled_valid<=0;carry_epoch<=0;carry_generation<=0;end',
             'if(!rst_n)begin out_error<=0;doubled_valid<=0;carry_epoch<=0;carry_generation<=0;carry_context<=0;\n   bank_live<=0;config_valid<=0;setup_done<=0;setup_done_context<=0;setup_context_q<=0;end')
    s = once(s, 'if(fault_pending)out_error<=1;',
             '''setup_done<=0;
   if(begin_setup && !setup_busy && !admission_bad && !out_error)begin
    setup_context_q<=setup_context;config_valid[setup_context]<=0;
   end
   if(unit_setup_done && unit_config_valid && !out_error)begin
    profile_base[setup_context_q]<=qualified_base;profile_reciprocal[setup_context_q]<=reciprocal;
    profile_limit[setup_context_q]<=coefficient_limit;profile_generation[setup_context_q]<=qualified_generation[7:0];
    config_valid[setup_context_q]<=1;setup_done<=1;setup_done_context<=setup_context_q;
   end
   if(fault_pending)out_error<=1;''')
    s = once(s, 'bank_epoch[epoch_in[0]]<=epoch_in;bank_generation[epoch_in[0]]<=generation_in;\n    bank_base[epoch_in[0]]<=base_in;bank_double[epoch_in[0]]<=double_in;',
             'bank_live[metadata_free]<=1;bank_epoch[metadata_free]<=epoch_in;bank_generation[metadata_free]<=generation_in;\n    bank_base[metadata_free]<=base_in;bank_double[metadata_free]<=double_in;bank_context[metadata_free]<=context_in;')
    s = once(s, 'if(begin_carry)begin carry_epoch<=field_epoch[0];carry_generation<=field_generation[0];end',
             "if(joined && field_row[0]==ROW_W'(ROWS-1) && !join_bad && !out_error)bank_live[bank]<=0;\n   if(begin_carry)begin carry_epoch<=field_epoch[0];carry_generation<=field_generation[0];carry_context<=field_context[0];end")
    return top, s


def profile_source(top, text):
    """Intrinsic setup-profile admission, not diagnostic-pending gating.

    The legacy arithmetic root exposes raw field acceptance even for a
    profile-mismatched origin token. This named successor denies that token
    before lease allocation, while retaining the same registered fault edge.
    Disabled/live-stale contexts remain raw-drain eligible, publication off.
    """
    new = top + '_profile_qualified_v2'
    text = once(text, 'module ' + top + ' #', 'module ' + new + ' #')
    anchor = ' assign frame_accept=&field_frame_accept;assign correction_accept=&field_correction_accept;'
    extra = ''' wire frame_profile_ok=config_valid[context_in] && base_in==profile_base[context_in] &&
  generation_in==profile_generation[context_in] && metadata_free_found;
 wire field_input_valid=in_slot_valid && !out_error && (!frame_start || frame_profile_ok);
'''
    text = once(text, anchor, extra + anchor)
    before = '.in_slot_valid(in_slot_valid && !out_error),.frame_start,'
    if text.count(before) != 3:
        raise ValueError('S4_CTX_PROFILE_THREE_INPUTS')
    text = text.replace(before, '.in_slot_valid(field_input_valid),.frame_start(frame_start && frame_profile_ok),')
    before = '.correction_valid(correction_valid && !out_error)'
    if text.count(before) != 3:
        raise ValueError('S4_CTX_PROFILE_THREE_CORRECTIONS')
    text = text.replace(before, '.correction_valid(correction_valid && !out_error && (!frame_start || frame_profile_ok))')
    return new, text


def diet_source(top,text,corr_serial_bfs,mont_factored):
    """Explicit frozen recipe flags, with zero-flag RTL byte-identical."""
    values=(corr_serial_bfs,mont_factored)
    if values==(0,0):return top,text
    if values!=(2,1):raise ValueError('S4_CONTEXT_DIET_EXACT_C2_M1')
    new=top+'_diet_c2_m1_v1'
    text=once(text,'module '+top+' #','module '+new+' #')
    text=once(text,'CONTEXTS=2','CONTEXTS=2,CORR_SERIAL_BFS=2,MONT_FACTORED=1,COMM_STAGE_SHARED_MLAB=1')
    text=once(text,'CONTEXTS!=2','CONTEXTS!=2 || CORR_SERIAL_BFS!=2 || MONT_FACTORED!=1 || COMM_STAGE_SHARED_MLAB!=1')
    return new,text


def prepare(n=32, p=8, *, contexts=2, mode='warm_signed', allow_full_constants=False,
            profile_admission=1,corr_serial_bfs=0,mont_factored=0):
    if (ROOT / 'docs/briefs/PAUSE').exists():
        raise ValueError('brief PAUSE')
    if contexts != 2 or p not in (8, 16) or mode not in ('warm', 'warm_signed'):
        raise ValueError('S4_CTX_CARRY_EXPLICIT_CONTEXTS2_P8_P16')
    if type(profile_admission) is not int or profile_admission not in (0, 1):
        raise ValueError('S4_CTX_PROFILE_ADMISSION_FLAG')
    if any(type(value) is not int for value in (corr_serial_bfs,mont_factored)) or \
       (corr_serial_bfs,mont_factored) not in ((0,0),(2,1)) or ((corr_serial_bfs or mont_factored) and p!=16):
        raise ValueError('S4_CONTEXT_DIET_EXACT_P16_C2_M1')
    bundles = [fields.prepare(n, p, f, mode=mode, contexts=2,
                              allow_full_constants=allow_full_constants,
                              corr_serial_bfs=corr_serial_bfs,mont_factored=mont_factored) for f in range(3)]
    files = {}; deps = []
    for bundle in bundles:
        for name, text in bundle['files'].items():
            if name in files and files[name] != text:
                raise ValueError('S4_CTX_CARRY_SHARED_COLLISION:' + name)
            files[name] = text
        deps += bundle['source_dependencies']
    for path in parent.COMPONENTS:
        files[Path(path).name] = (ROOT / path).read_text()
    top, text = source(n, p, bundles, mode)
    if profile_admission:
        top, text = profile_source(top, text)
    top,text=diet_source(top,text,corr_serial_bfs,mont_factored)
    files[top + '.sv'] = text
    deps = list(dict.fromkeys(deps + parent.COMPONENTS + [SELF, parent.__name__.replace('.', '/') + '.py']))
    # Module import prefix is not part of the FPGA source-relative closure.
    deps = [path.removeprefix('fpga/') for path in deps]
    g = dict(bundles[0]['geometry'])
    result=dict(top=top, files=files, rtl_sources=[name for name in files if name.endswith('.sv')],
                source_dependencies=deps,
                source_sha256={path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in deps},
                generated_sha256={name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()},
                geometry=g, parameters=dict(AW=n.bit_length()-1, P=p, CONTEXTS=2), mode=mode,
                profile_admission=bool(profile_admission),
                setup_latency=98, setup_contract='Shared setup E97 output captured into the addressed context profile at E98; first frame follows profile publication.',
                resource_contract='Two 213-bit profile snapshots (base32/reciprocal96/A77/generation8), four full-owner frame metadata banks; shared setup/CRT/P carry lanes.',
                scope='Real two-context three-field/CRT/shared-carry source candidate; no recurrence/host publication or native/physical qualification inherited.')
    if corr_serial_bfs:
        result['parameters'].update(CORR_SERIAL_BFS=2,MONT_FACTORED=1,COMM_STAGE_SHARED_MLAB=1)
    return result
