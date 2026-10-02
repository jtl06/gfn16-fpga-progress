"""User-selected C2 storage2 + packed delay + root retiming + term lookahead.

The donor is the immutable original storage2 capture, not timing58. No GEN,
compact-tag, seven-timing-flag or explicit-MLAB addition is made. The full27
lookahead is payload only: all live owner/cadence/accept/fault authority remains
literal parent logic. Default disabled is exact; public edge calendars stay put.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
from . import stream27_comm_packed_bind as packed
from . import stream27_root_outputreg_bind as roots

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_storage_combo_bind.py'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage2-native-v1'
CAPTURES = {
    256: ('aw8-normal', 'b46fa68fbdb4b7d7bee8c799919490a3329285538e95e087e4ea4a322a1137c9'),
    65536: ('full-normal', '7592c3d12f6ecf0ef3e5aa9e9c80a4b4cb0f5c7796e94c179b4f0f9488a77837')}
TERM = 'genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1'
PROTOCOL = 'genefer_stream27_epoch_protocol_contexts_v1'
NEW_PROTOCOL = PROTOCOL + '_payload_lookahead_v1'
NEW_TERM = TERM + '_payload_lookahead_v1'


def need(ok, label):
    if not ok:
        raise ValueError('C2_STORAGE_COMBO_' + label)


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def once(text, before, after):
    need(text.count(before) == 1, 'ANCHOR:' + before[:90])
    return text.replace(before, after, 1)


def edits(text, changes):
    original = text
    for before, after in changes:
        text = once(text, before, after)
    inverse = text
    for before, after in reversed(changes):
        inverse = once(inverse, after, before)
    need(inverse == original, 'LITERAL_REVERSE')
    return text


def root_retime(files, aw):
    """Apply trusted port-cycle transforms to all actual C2 BF/root cohorts."""
    original = dict(files)
    bf = roots.butterfly_source(files[roots.OLD_BF + '.sv'])
    names, count = set(), 0
    for name, text in list(files.items()):
        if not re.match(r'genefer_stream28_merged_(ct|gs)_.*\.sv$', name):
            continue
        if roots.OLD_BF + ' #(' not in text:
            continue
        cohort = re.findall(re.escape(roots.OLD_BF) + r' #\([\s\S]*?\);', text)
        need(cohort and all('.in_valid(accept)' in call for call in cohort) and
             '.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots)' in text,
             'C2_ROOT_BF_SAME_ACCEPT')
        updated = text.replace(roots.OLD_BF + ' #(', roots.NEW_BF + ' #(')
        updated, changed = re.subn(r'\.w\((packed_roots\[[^\n]+?)\),', r'.root_delayed(\1),', updated)
        need(changed == len(cohort), 'ALL_BF_WEIGHT_PORTS')
        for module in re.findall(r'\b(merged_stream27_root_(?:ct|gs)_\w+) roots \(', text):
            stage = int(re.search(r'_s(\d+)_v1$', module)[1])
            if '_gs_' in module and stage == aw-1:
                continue
            names.add(module)
            updated = once(updated, module + ' roots (', module + '_bf_outreg_v1 roots (')
        files[name] = updated
        count += len(cohort)
    need(count == 3 * (2*aw-1) * 8, 'ALL_THREE_C2_BF_COHORTS')
    emitted = set()
    for name, text in list(files.items()):
        if not name.startswith('merged_stream27_root_library_'):
            continue
        updated = text
        for match in re.finditer(r'module (merged_stream27_root_\w+) #\([\s\S]*?endmodule', text):
            module = match[1]
            if module in names:
                new, body = roots.root_source(match[0], module)
                updated = once(updated, match[0], body)
                emitted.add(module)
        files[name] = updated
    need(emitted == names and len(names) == 3*(2*aw-1), 'ALL_ROOT_MODULES')
    files[roots.NEW_BF + '.sv'] = bf
    if not any(roots.OLD_BF + ' #(' in text for name, text in files.items() if name != roots.OLD_BF + '.sv'):
        del files[roots.OLD_BF + '.sv']
    return dict(lazy_instances=count, root_modules=len(names),
        contract=roots.fields_with_weight_register(), original_generated={n: sha(t) for n,t in original.items()},
        new_generated={n: sha(t) for n,t in files.items()}, public_edges_added=0)


def protocol_source(text):
    lookup = ''' // Data-only next-edge lookup; not used by accept/pending/commit logic.
 logic [31:0] payload_age_next[0:BANKS-1];
 always_comb begin
  pointwise_payload_owner_next='0;pointwise_payload_row_next='0;
  for(int i=0;i<BANKS;i=i+1)begin
   payload_age_next[i]=(cycle_count+32'd1)-pw_first[i];
   if(valid[i] && payload_age_next[i]<32'(ROWS))begin
    pointwise_payload_owner_next={2'(i),owner[i],epoch[i],generation[i]};
    pointwise_payload_row_next=ROW_W'(payload_age_next[i]);
   end
  end
 end
 // synthesis translate_off
 initial if(EPOCH_W!=16 || POINTWISE_FIRST<=1 || SINK_FIRST<POINTWISE_FIRST+ROWS)
  $fatal(1,"C2_LOOKAHEAD_NONOVERLAP_GEOMETRY");
 // synthesis translate_on
'''
    return edits(text, [
        ('module '+PROTOCOL+' #(', 'module '+NEW_PROTOCOL+' #('),
        (' output logic out_error,fault_pending\n',
         ' output logic out_error,fault_pending,\n output logic [26:0] pointwise_payload_owner_next,\n output logic [$clog2(ROWS)-1:0] pointwise_payload_row_next\n'),
        (' // Pure lookup: no accept/fault signal', lookup+' // Pure lookup: no accept/fault signal')])


def term_source(text):
    return edits(text, [
        ('module '+TERM+' #(', 'module '+NEW_TERM+' #('),
        ('    input logic [LANES*27-1:0] next_coeff,next_seed_R_roots,',
         '    input logic [LANES*27-1:0] next_coeff,next_seed_R_roots,\n    input logic [26:0] payload_owner,\n    input logic [AW-$clog2(LANES)-1:0] payload_row,'),
        ('    wire reseed=next_row[ROW_W-1-:LANE_W]!=pointwise_row[ROW_W-1-:LANE_W];',
         '    wire [ROW_W-1:0] payload_target=payload_row+ROW_W\'(4);\n    wire reseed=payload_target[ROW_W-1-:LANE_W]!=payload_row[ROW_W-1-:LANE_W];'),
        ('    wire bypass=product_slot && product_owner==pointwise_owner && product_row==pointwise_row;\n',
         '    wire bypass=product_slot && product_owner==pointwise_owner && product_row==pointwise_row;\n    wire bypass_payload=product_slot && product_owner==payload_owner && product_row==payload_row;\n'),
        ('current_term=context_data[pw_bank][pw_context];', 'current_term=context_data[payload_owner[24]][payload_row[1:0]];'),
        ("        if(bypass)begin current_term=product_data;consumer_missing=1'b0;end",
         "        if(bypass_payload)current_term=product_data;\n        if(bypass)consumer_missing=1'b0;")])


def field_source(name, text, aw, field):
    new = f'genefer_stream27_shared_warm_aw{aw}_p16_f{field}_storage_combo_v1'
    coefficient = re.findall(r'  assign term_next_coeff\[(\d+)\+:27\]=B_table\[fwd_generation\[24\]\]\[([^;]+)\];', text)
    need(len(coefficient) == 16 and len({index for _,index in coefficient}) == 1, 'SAME_COHORT_B_COEFFICIENT')
    current_index = coefficient[0][1]
    next_index = current_index.replace('term_target', 'term_payload_target_next')
    declarations = ''' wire [26:0] protocol_payload_owner_next;
 wire [ROW_W-1:0] protocol_payload_row_next;
 logic [26:0] term_payload_owner;logic [ROW_W-1:0] term_payload_row;
 logic [26:0] term_payload_coeff;
 wire [ROW_W-1:0] term_payload_target_next=protocol_payload_row_next+ROW_W'(4);
'''
    registers = f''' // Predict payload only; every authoritative owner/calendar check stays live.
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin term_payload_owner<=0;term_payload_row<=0;end
  else begin term_payload_owner<=protocol_payload_owner_next;term_payload_row<=protocol_payload_row_next;end
 end
 always_ff @(posedge clk)if(rst_n)begin
  term_payload_coeff<=B_table[protocol_payload_owner_next[24]][{next_index}];
  if(!stop && small_slot && small_capture && small_owner[24]==protocol_payload_owner_next[24])
   term_payload_coeff<=small_data[27*int'(term_payload_target_next[ROW_W-1-:4])+:27];
 end
 // synthesis translate_off
 always @(negedge clk)if(rst_n && fwd_slot && !stop && protocol_pw_accept)begin
  if(term_payload_owner!={{pointwise_bank,fwd_generation}} || term_payload_row!=pw_row)
   $fatal(1,"C2_LOOKAHEAD_CURRENT_OWNER_ROW");
  if(term_payload_coeff!=B_table[fwd_generation[24]][{current_index}])
   $fatal(1,"C2_LOOKAHEAD_CURRENT_B_COEFFICIENT");
 end
 // synthesis translate_on
'''
    changes = [
        ('module '+name+' #', 'module '+new+' #'),
        (PROTOCOL+' #(', NEW_PROTOCOL+' #('), (TERM+' #(', NEW_TERM+' #('),
        ('.pointwise_epoch(protocol_pw_epoch),.sink_epoch(protocol_sink_epoch),',
         '.pointwise_epoch(protocol_pw_epoch),.sink_epoch(protocol_sink_epoch),\n  .pointwise_payload_owner_next(protocol_payload_owner_next),.pointwise_payload_row_next(protocol_payload_row_next),'),
        (' wire [ROW_W-1:0] pw_row=protocol_pw_row;', declarations+' wire [ROW_W-1:0] pw_row=protocol_pw_row;'),
        ('.pw_slot(fwd_slot),.pw_start(fwd_start),.pw_row,', '.pw_slot(fwd_slot),.pw_start(fwd_start),.pw_row(term_payload_row),'),
        ('.pointwise_row(pw_row),.next_coeff(term_next_coeff),', '.pointwise_row(pw_row),.payload_owner(term_payload_owner),.payload_row(term_payload_row),.next_coeff(term_next_coeff),'),
        (' always_ff @(posedge clk or negedge rst_n)begin\n  if(!rst_n)begin\n   input_remaining',
         registers+' always_ff @(posedge clk or negedge rst_n)begin\n  if(!rst_n)begin\n   input_remaining')]
    changes += [(f'  assign term_next_coeff[{offset}+:27]=B_table[fwd_generation[24]][{current_index}];',
                 f'  assign term_next_coeff[{offset}+:27]=term_payload_coeff;') for offset,_ in coefficient]
    return new, edits(text, changes)


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_FLAG')
    out = copy.deepcopy(bundle)
    if not enabled:
        return out
    n = out['geometry']['n']; aw = out['geometry']['aw']
    need(n in CAPTURES and len(out['files']) == 53 and out['parameters']['CONTEXTS'] == 2 and
         out.get('storage_contract', {}).get('clean_parent') is True, 'ORIGINAL_STORAGE53')
    need(out['parameters']['P'] == 16 and out['parameters']['CORR_SERIAL_BFS'] == 2 and
         out['parameters']['MONT_FACTORED'] == 1 and out['geometry']['rows'] >= 16, 'AW8_FULL_ONLY')
    need(not any(k in out for k in ('context_timing', 'context_stage_pipe', 'context_tagcompact', 'context_storage_combo')),
         'NO_OTHER_FLAGS')
    original = copy.deepcopy(out)
    out = packed.bind(out)
    retiming = root_retime(out['files'], aw)
    files = out['files']
    files[NEW_PROTOCOL+'.sv'] = protocol_source(files.pop(PROTOCOL+'.sv'))
    files[NEW_TERM+'.sv'] = term_source(files.pop(TERM+'.sv'))
    names = [name for name in files if name.startswith('genefer_stream27_shared_warm_')]
    need(len(names) == 3, 'THREE_ACTUAL_FIELDS')
    renames = {}
    for name in names:
        field = int(re.search(r'_f([012])_',name)[1])
        new, text = field_source(name[:-3], files.pop(name), aw, field)
        files[new+'.sv'] = text
        renames[name[:-3]] = new
    for name, text in list(files.items()):
        for old, new in renames.items():
            text = re.sub(r'\b'+re.escape(old)+r'\b',new,text)
        files[name] = text
    oldtop = out['top']; top = f'genefer_stream27_host_contexts_aw{aw}_p16_storage_combo_v1'
    files[top+'.sv'] = once(files.pop(oldtop+'.sv'), 'module '+oldtop+' #', 'module '+top+' #')
    need(out['geometry'] == original['geometry'] and out['parameters'] == original['parameters'], 'ZERO_PUBLIC_EDGES')
    out.update(top=top, rtl_sources=list(files), generated_sha256={name:sha(text) for name,text in files.items()})
    dependencies = [SELF, roots.SELF, roots.CONTRACT]
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies'] + dependencies))
    out['source_sha256'] = {path:sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['context_storage_combo'] = dict(parent_top=original['top'], parent_generated_sha256=original['generated_sha256'],
        parent_capture_sha256=CAPTURES[n][1], roster=['storage2','packed_delays','root_weight_retime','term_payload_lookahead'],
        full_ingress_owner_bits=25, full_term_owner_bits=27, logical_leases=4, physical_payload_banks=2,
        product_capture_edges=4, recurrence_distance=4, II=1, zero_public_edges=True,
        qualified_product_slot_bypass_cache_state_unchanged=True,
        no_seven_timing_GEN_compact_MLAB_flags=True, root_retime=retiming,
        native_qualified=False, physical_area_claim=False, clock_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, enabled=0):
    need(n in CAPTURES, 'AW5_UNSUPPORTED_ROW_W_LT4')
    stage, pin = CAPTURES[n]
    raw = (BASE/stage/'production-bundle.json').read_bytes()
    need(sha(raw) == pin, 'IMMUTABLE_CAPTURE')
    return bind(json.loads(raw), enabled=enabled)
