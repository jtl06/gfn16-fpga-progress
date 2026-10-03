"""Default-OFF R93 lean experiment on captured original C2 storage2.

One build switch; the protected default is a literal deep copy. Numeric RTL,
four logical leases, two physical context banks, E4 bypass, row/frame cadence,
descriptor occupancy and host publication framing remain. The lean branch
normalizes functional keys to context+epoch mod4 (+lease bank for term keys),
removes aggregate fault authority and retains a host timeout watchdog.

This first seam does not remove every leaf numerical guard or observer. It is
not fault-equivalent, native-qualified, a physical saving, or a deployment GL
implementation. Any record must say 'lean build; host GL assumed'.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

from . import stream27_context_storage_combo_bind as capture

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_lean_production.py'
MODEL = 'reference/stream27_lean_functional_key_model.py'
MODEL_PIN = '2645a24d8649f1c30a487a29c92041b1b9bf23cd708084b89e71124fefae53dd'


def need(ok, label):
    if not ok:
        raise ValueError('LEAN_PRODUCTION_' + label)


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


class Changes:
    """Exact transform/reverse log; no pattern authorizes an unbounded cut."""
    def __init__(self, text):
        self.original, self.text, self.ops = text, text, []

    def replace(self, old, new):
        need(self.text.count(old) == 1, 'EXACT_ANCHOR:' + old[:70])
        self.text = self.text.replace(old, new, 1)
        self.ops.append((old, new))

    def section(self, first, last, replacement):
        need(self.text.count(first) == self.text.count(last) == 1, 'SECTION_BOUNDARIES')
        start, end = self.text.index(first), self.text.index(last)
        need(start < end, 'SECTION_ORDER')
        self.replace(self.text[start:end], replacement)

    def assignment(self, name, new):
        matches = list(re.finditer(r'\bassign ' + re.escape(name) + r'=[\s\S]*?;', self.text))
        need(len(matches) == 1, 'ASSIGNMENT:' + name)
        self.replace(matches[0][0], 'assign ' + name + '=' + new + ';')

    def done(self):
        inverse = self.text
        for old, new in reversed(self.ops):
            need(inverse.count(new) == 1, 'REVERSE_ANCHOR')
            inverse = inverse.replace(new, old, 1)
        need(inverse == self.original, 'LITERAL_REVERSE')
        return self.text


def field_source(text):
    x = Changes(text)
    # Preserve public ports. Only values in the body are normalized; named
    # connection labels stay unchanged, and all shorthand uses are explicit.
    header, body = x.text.split(');\n', 1)
    values = {'epoch_in': "{14'd0,epoch_in[1:0]}",
              'correction_epoch': "{14'd0,correction_epoch[1:0]}",
              'generation_in': "8'd0", 'correction_generation': "8'd0"}
    alias_body = body
    for name in values:
        alias_body = re.sub(r'\.' + name + r'(?=\s*[,\)])', '.' + name + '(' + name + ')', alias_body)
        alias_body = re.sub(r'(?<![.\w])' + name + r'\b', 'lean_' + name, alias_body)
    declarations = ''.join(' wire [' + ('15:0' if 'epoch' in name else '7:0') + '] lean_' + name + '=' + expr + ';\n'
                           for name, expr in values.items())
    x.replace(body, declarations + alias_body)
    x.section(' always_comb begin\n  admission_bad=',
              ' logic [LANES-1:0] digit_valid,', ' assign admission_bad=1\'b0;\n')
    x.section(' always_comb begin\n  child_pending[0]=',
              ' for(genvar lane=0;lane<LANES;lane=lane+1)begin: reducers',
              " assign child_pending[0]=1'b0;assign child_pending[1]=1'b0;\n")
    x.section(' always_comb begin\n  join_bad=',
              ' genefer_stream27_epoch_protocol_contexts_v1 #(', " assign join_bad=1'b0;\n")
    x.assignment('fault_pending', "1'b0")
    x.replace('   if(!stop && (admission_bad || join_bad || (|child_pending) || (|child_error) || inverse_pending || inverse_error || protocol_pending || protocol_error))\n    controller_error<=1;',
              "   controller_error<=1'b0; // lean aggregate authority removed\n")
    return x.done()


def protocol_source(text):
    x = Changes(text)
    x.assignment('fault_pending', "1'b0")
    x.replace('   if(!stop && (bad || external_fault_pending))out_error<=1;',
              "   out_error<=1'b0; // lean; watchdog is at the host framing boundary")
    x.replace(' assign frame_accept=rst_n && frame_begin && frame_context_valid && free_found && !frame_owner_exists && !stop &&\n  (!sequence_initialized[frame_ci] || frame_epoch==next_epoch[frame_ci]);',
              ' assign frame_accept=rst_n && frame_begin && frame_context_valid && free_found && !frame_owner_exists && !stop;')
    x.replace('  sink_tuple_ok && sink_order_ok && sink_generation==sink_live_generation && sink_frame_start==(sink_age[sink_index]==0);',
              '  sink_tuple_ok && sink_frame_start==(sink_age[sink_index]==0);')
    x.replace('    if(sink_slot && sink_found && !sink_multiple && sink_tuple_ok && sink_order_ok &&\n',
              '    if(sink_slot && sink_found && !sink_multiple && sink_tuple_ok &&\n')
    x.replace("     next_epoch[frame_ci]<=frame_epoch+EPOCH_W'(1);",
              "     next_epoch[frame_ci]<=(frame_epoch+EPOCH_W'(1)) & EPOCH_W'(3);")
    x.replace("     next_completed[sink_ci]<=sink_epoch+EPOCH_W'(1);",
              "     next_completed[sink_ci]<=(sink_epoch+EPOCH_W'(1)) & EPOCH_W'(3);")
    return x.done()


def threefield_source(text):
    x = Changes(text)
    x.replace(' assign frame_profile_ok=config_valid[context_in] && base_in==profile_base[context_in] &&\n  generation_in==profile_generation[context_in] && metadata_free_found;',
              ' assign frame_profile_ok=config_valid[context_in] && metadata_free_found;')
    x.section(' always_comb begin\n  join_bad=', ' for(genvar b=0;b<P;b=b+1)begin: arithmetic',
              " assign join_bad=1'b0;assign carry_bad=1'b0;assign admission_bad=1'b0;\n")
    x.assignment('fault_pending', "1'b0")
    x.assignment('digit_eligible', 'digit_valid && context_enabled[carry_context]')
    x.assignment('boundary_eligible', 'boundary_valid && context_enabled[carry_context]')
    x.assignment('next_epoch', "{14'd0,(carry_epoch[1:0]+2'd1)}")
    x.replace('   if(fault_pending)out_error<=1;', "   out_error<=1'b0;")
    x.replace('bank_epoch[metadata_free]<=epoch_in;', "bank_epoch[metadata_free]<={14'd0,epoch_in[1:0]};")
    return x.done()


def warm_source(text):
    x = Changes(text)
    # AW8's FIFO write and AW16's direct assignment contain the same owner
    # expression. Only metadata bits change, never the real18-edge FIFO.
    x.replace('{digit_context,digit_epoch+16\'d1,digit_generation}',
              "{digit_context,14'd0,(digit_epoch[1:0]+2'd1),8'd0}")
    x.replace(' wire command_bad=command_needed && (!command_valid[feedback_context] ||\n  command_index[feedback_context*32+:32]!=launched[feedback_context] ||\n  command_generation[feedback_context*8+:8]!=chain_generation[feedback_context]);',
              ' wire command_bad=command_needed && !command_valid[feedback_context]; // retain descriptor availability')
    x.assignment('out_error', "1'b0")
    x.assignment('fault_pending', "1'b0")
    x.replace('   if(child_error || collision || count_bad || command_bad || cold_request_bad)local_error<=1;',
              "   local_error<=1'b0;")
    x.replace("   if(local_error || child_error)begin active<=0;warm_done<=0;warm_cancelled<=2'b11;end",
              '   // lean: job-count/descriptor flow remains; no child fault quarantine')
    return x.done()


def host_source(text, geometry):
    x = Changes(text)
    interval, carry = geometry['warm_interval'], geometry['carry_done']
    n, rows = geometry['n'], geometry['rows']
    overhead = geometry['warm_interval']//2 + carry + 1 + 2*(rows + 10*n + 6) + n + 1024
    anchor = ' wire canon_busy,canon_done,canon_error,canon_image_valid,canon_read_valid;\n'
    watchdog = f''' // Lean GL/rollback is host-assumed, not implemented here.
 logic watchdog_error;logic [63:0] watchdog_limit;
 wire [63:0] requested_count0=start_contexts[0] ? (batch_mode[0] ? {{32'd0,warm_count[0+:32]}} : 64'd1) : 64'd0;
 wire [63:0] requested_count1=start_contexts[1] ? (batch_mode[1] ? {{32'd0,warm_count[32+:32]}} : 64'd1) : 64'd0;
 wire [63:0] requested_max_count=requested_count0>requested_count1 ? requested_count0 : requested_count1;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin watchdog_error<=0;watchdog_limit<=0;end
  else begin
   if((|start_contexts) && !(|busy) && !canonical_owned && !error)
    watchdog_limit<=requested_max_count*64'd{interval}+64'd{overhead};
   if((|busy) && cycles>watchdog_limit)watchdog_error<=1;
  end
 end
 // synthesis translate_off
 initial if(LEAN_PRODUCTION!=1)$fatal(1,"LEAN_SWITCH_REQUIRES_PROTECTED_DEFAULT_SOURCE");
 // synthesis translate_on
'''
    x.replace(anchor, anchor + watchdog)
    x.replace('EXPLICIT_NET_DECLARATIONS=1,COLD_LAUNCH_FENCE=1,',
              'LEAN_PRODUCTION=1,EXPLICIT_NET_DECLARATIONS=1,COLD_LAUNCH_FENCE=1,')
    x.replace('  final_owner!=live_owner[final_context*56+:56] || raw_rows[final_context]>=(ROW_W+1)\'(ROWS) ||',
              '  raw_rows[final_context]>=(ROW_W+1)\'(ROWS) ||')
    x.replace('.row_write_data(digit_data),.row_write_owner(final_owner),',
              '.row_write_data(digit_data),.row_write_owner(live_owner[final_context*56+:56]),')
    x.assignment('error', 'watchdog_error')
    x.assignment('canonical_cycles', "128'd0")
    x.assignment('image_copy_cycles', "128'd0")
    x.assignment('final_image_rows', "64'd0")
    # Typed setters vanish; phase/count/order/ack control is otherwise literal.
    setters = list(re.finditer(r'local_error<=1;', x.text))
    need(len(setters) == 6, 'KNOWN_HOST_TYPED_SETTER_COUNT')
    for match in reversed(setters):
        # Disambiguate each whole line for a literal reversal even when many
        # statements end with the same old setter.
        start = x.text.rfind('\n', 0, match.start()) + 1
        end = x.text.find('\n', match.end())
        old = x.text[start:end]
        x.replace(old, old.replace('local_error<=1;', "local_error<=1'b0; // lean typed setter removed"))
    return x.done(), overhead


def bind(bundle, *, LEAN_PRODUCTION=0):
    need(type(LEAN_PRODUCTION) is int and LEAN_PRODUCTION in (0, 1), 'ONE_BOOLEAN_SWITCH')
    out = copy.deepcopy(bundle)
    if not LEAN_PRODUCTION:
        return out
    n = out['geometry']['n']
    need(n in capture.CAPTURES, 'AW8_FULL_ONLY')
    protected = capture.prepare(n, enabled=0)
    need(out == protected, 'EXACT_ORIGINAL_STORAGE2_PARENT_ONLY')
    need(sha((ROOT/MODEL).read_bytes()) == MODEL_PIN, 'FROZEN_FUNCTIONAL_KEY_MODEL')
    before = copy.deepcopy(out)
    files = out['files']
    renames, transformed = {}, []
    for name, body in list(files.items()):
        if name.startswith('genefer_stream27_shared_warm_'):
            newbody = field_source(body)
        elif name == 'genefer_stream27_epoch_protocol_contexts_v1.sv':
            newbody = protocol_source(body)
        elif 'threefield_carry_aw' in name:
            newbody = threefield_source(body)
        elif 'warm_contexts_aw' in name:
            newbody = warm_source(body)
        elif name == before['top'] + '.sv':
            newbody, overhead = host_source(body, out['geometry'])
        else:
            continue
        old = name[:-3]
        if name.startswith('genefer_stream27_shared_warm_'):
            field = re.search(r'_f([012])_', old)[1]
            new = f'genefer_stream27_lean_aw{out["geometry"]["aw"]}_p16_f{field}_v1'
        elif name == before['top'] + '.sv':
            new = f'genefer_stream27_lean_host_aw{out["geometry"]["aw"]}_p16_v1'
        else:
            new = old + '_lean_v1'
        need(newbody.count('module ' + old + ' #') == 1, 'MODULE_DECLARATION')
        newbody = newbody.replace('module ' + old + ' #', 'module ' + new + ' #', 1)
        files.pop(name)
        files[new + '.sv'] = newbody
        renames[old] = new
        transformed.append(name)
    need(len(transformed) == 7, 'THREE_FIELDS_PROTOCOL_THREEFIELD_WARM_HOST')
    for name, body in list(files.items()):
        for old, new in renames.items():
            body = re.sub(r'\b' + re.escape(old) + r'\b', new, body)
        files[name] = body
    out['top'] = renames[before['top']]
    out['parameters']['LEAN_PRODUCTION'] = 1
    out['rtl_sources'] = list(files)
    out['generated_sha256'] = {name: sha(body) for name, body in files.items()}
    deps = [SELF, MODEL] + [str((capture.BASE/stage/'production-bundle.json').relative_to(ROOT))
                            for stage, _ in capture.CAPTURES.values()]
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies'] + deps))
    out['source_sha256'] = {path: sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['lean_production'] = dict(label='lean build; host GL assumed', host_GL_rollback_implemented=False,
        source_parent=before['top'], source_parent_generated_sha256=before['generated_sha256'],
        main_functional_key_mask='0x01000300', term_functional_key_mask='0x07000300',
        logical_leases=4, physical_payload_banks=2, kept=['context', 'lease bank', 'epoch modulo4',
            'E4 bypass/row/cache availability', 'full32 counts/ordinal', 'descriptor occupancy/availability',
            'shadow/canonical context arbitration', 'N commit acknowledgments', 'host timeout watchdog'],
        removed=['high epoch/generation transport', 'field/protocol/top aggregate fault authority',
            'field and cross-field malformed/identity guard aggregates', 'host typed setters'],
        retained_leaf_numerical_guards=True,
        trimmed_observers=['canonical_cycles', 'image_copy_cycles', 'final_image_rows'],
        retained_functional_observers=['cycles for watchdog', 'full32 completed/started counts',
            'FIFO occupancy', 'accepted generation/read_owner for unchanged host ABI'],
        watchdog_overhead_edges=overhead, zero_public_edge_intent=True,
        native_qualified=False, fault_equivalent=False, hardware_GL_implemented=False,
        physical_area_claim=False, clock_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, p=16, contexts=2, LEAN_PRODUCTION=0):
    return bind(capture.prepare(n, p=p, contexts=contexts, enabled=0), LEAN_PRODUCTION=LEAN_PRODUCTION)
