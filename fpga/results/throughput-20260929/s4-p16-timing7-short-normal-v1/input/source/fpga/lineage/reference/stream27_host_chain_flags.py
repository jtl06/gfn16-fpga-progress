"""Copied whole-host timing flags; frozen zero-flag bundle is unchanged.

BOUNDARY_INPUTREG registers the selected field boundary payload in all three
fields. It does not move correction admission, FIFO pop, main NTT/carry edges,
warm recurrence or finalization. Only generous-margin calendars are admitted.
"""
import copy
import hashlib
from . import stream27_host_chain_param_v3 as parent
from . import stream27_shared_field_flags as fields

ROOT = parent.ROOT
SELF = 'reference/stream27_host_chain_flags.py'
DESCRIPTOR = 'rtl/kernel/genefer_stream27_descriptor_fifo_ff_v1.sv'


def prepare(n=65536, p=8, *, paired=False, contexts=1,
            allow_full_constants=False, canonical_pipe_stages=0, boundary_inputreg=0,
            descriptor_fifo_ff=0):
    b = parent.prepare(n, p, paired=paired, contexts=contexts,
                       allow_full_constants=allow_full_constants,
                       canonical_pipe_stages=canonical_pipe_stages)
    return bind(b, boundary_inputreg=boundary_inputreg, descriptor_fifo_ff=descriptor_fifo_ff)


def bind_boundary_host(bundle, *, boundary_inputreg=0):
    fields.need(type(boundary_inputreg) is int and boundary_inputreg in (0, 1),
                'S4_BOUNDARY_HOST_FLAG')
    if boundary_inputreg == 0:
        return bundle
    b = copy.deepcopy(bundle)
    fields.need(b['parameters']['CONTEXTS'] == 1, 'S4_BOUNDARY_HOST_CONTEXTS1')
    fields.need('BOUNDARY_INPUTREG' not in b['parameters'], 'S4_BOUNDARY_HOST_ALREADY_BOUND')
    g = fields.boundary_geometry(b['geometry'])
    roots = [name for name in b['files']
             if name.startswith('genefer_stream27_shared_warm_') and name.endswith('.sv')]
    fields.need(len(roots) == 3, 'S4_BOUNDARY_HOST_THREE_FIELDS')
    renames = {}
    for name in roots:
        old = name[:-3]
        new, text = fields.boundary_root(b['files'].pop(name), old)
        renames[old] = new
        b['files'][new + '.sv'] = text
    for name, text in list(b['files'].items()):
        for old, new in renames.items():
            # Newly renamed declarations already contain the old prefix.
            text = text.replace(old + ' #', new + ' #')
        b['files'][name] = text
    # Rename both the ordinary host and the paired public top, not arithmetic.
    host_names = [name[:-3] for name in b['files']
                  if name.startswith('genefer_stream27_host_chain_') and name.endswith('.sv')]
    fields.need(host_names, 'S4_BOUNDARY_HOST_ROOT')
    host_renames = {name: name + '_boundary_inputreg_v1' for name in host_names}
    def rename(text):
        for old, new in host_renames.items():
            text = text.replace(old, new)
        return text
    b['files'] = {rename(name): rename(text) for name, text in b['files'].items()}
    b['top'] = rename(b['top'])
    for name in host_renames.values():
        text = b['files'][name + '.sv']
        anchor = '#(parameter '
        fields.need(text.count(anchor) == 1, 'S4_BOUNDARY_HOST_PARAMETER')
        text = text.replace(anchor, '#(parameter int BOUNDARY_INPUTREG=1,parameter ', 1)
        text = text.replace('endmodule', ' // synthesis translate_off\n initial if(BOUNDARY_INPUTREG!=1)$fatal(1,"S4_BOUNDARY_INPUTREG_BUILD_FLAG");\n // synthesis translate_on\nendmodule')
        b['files'][name + '.sv'] = text
    b['files'][fields.BOUNDARY.rsplit('/', 1)[1]] = (ROOT / fields.BOUNDARY).read_text()
    b['parameters'] = dict(b['parameters'], BOUNDARY_INPUTREG=1)
    b['geometry'] = g
    b['source_dependencies'] = list(dict.fromkeys(b['source_dependencies'] + [SELF, fields.SELF, fields.BOUNDARY]))
    b['source_sha256'] = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                          for path in b['source_dependencies']}
    b['rtl_sources'] = [name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256'] = {name: hashlib.sha256(text.encode()).hexdigest()
                             for name, text in b['files'].items()}
    b['boundary_inputreg_contract'] = 'All three coherent selected correction ingress registers; cache/seed +1 only. FIFO acceptance, main transform/carry/warm interval and canonical/copy costs unchanged.'
    b['scope'] = 'Whole BOUNDARY_INPUTREG timing candidate; no inherited whole native/clock/promotion qualification.'
    return b


def bind_descriptor(bundle, *, descriptor_fifo_ff=0):
    fields.need(type(descriptor_fifo_ff) is int and descriptor_fifo_ff in (0, 1),
                'S4_DESCRIPTOR_FIFO_FF_FLAG')
    if descriptor_fifo_ff == 0:
        return bundle
    b = copy.deepcopy(bundle)
    fields.need('DESCRIPTOR_FIFO_FF' not in b['parameters'], 'S4_DESCRIPTOR_FIFO_FF_ALREADY_BOUND')
    host_names = [name for name in b['files'] if name.startswith('genefer_stream27_host_chain_') and name.endswith('.sv')]
    real = [name for name in host_names if 'logic [31:0] feed_index[0:3],next_write_index;' in b['files'][name]]
    fields.need(len(real) == 1, 'S4_DESCRIPTOR_FIFO_FF_REAL_HOST')
    name = real[0]; text = b['files'][name]
    def change(before, after):
        nonlocal text
        fields.need(text.count(before) == 1, 'S4_DESCRIPTOR_FIFO_FF_ANCHOR:' + before[:70])
        text = text.replace(before, after, 1)
    change('logic [1:0] feed_read,feed_write;logic [2:0] feed_count;',
           'wire [2:0] feed_count;')
    change('logic [31:0] feed_index[0:3],next_write_index;',
           'logic [31:0] next_write_index;wire [31:0] feed_head_index;')
    change('logic [7:0] feed_generation[0:3];logic feed_double[0:3];',
           'wire [7:0] feed_head_generation;wire feed_head_double;')
    change('.command_double(feed_double[feed_read])', '.command_double(feed_head_double)')
    change('.command_index(feed_index[feed_read]),.command_generation(feed_generation[feed_read])',
           '.command_index(feed_head_index),.command_generation(feed_head_generation)')
    change('feed_index[feed_write]<=command_index;feed_generation[feed_write]<=command_generation;feed_double[feed_write]<=command_double;\n    feed_write<=feed_write+2\'d1;', '')
    change("if(feed_pop)begin feed_read<=feed_read+2'd1;commands_consumed<=commands_consumed+32'd1;end",
           "if(feed_pop)begin commands_consumed<=commands_consumed+32'd1;end")
    change("   case({feed_push,feed_pop})\n    2'b10:feed_count<=feed_count+3'd1;\n    2'b01:feed_count<=feed_count-3'd1;\n    default:begin end\n   endcase\n", '')
    before = 'feed_read<=0;feed_write<=0;feed_count<=0;'
    fields.need(text.count(before) == 2, 'S4_DESCRIPTOR_FIFO_FF_RESET_CLEAR')
    text = text.replace(before, '')
    anchor = ' assign operations_started=first_operation_seen ? child_started : 32\'d0;'
    fields.need(text.count(anchor) == 1, 'S4_DESCRIPTOR_FIFO_FF_INSTANCE')
    text = text.replace(anchor, anchor + '''
 genefer_stream27_descriptor_fifo_ff_v1 descriptor_fifo (
  .clk,.rst_n,.clear(state==IDLE && start),.push(feed_push),.pop(feed_pop),
  .push_index(command_index),.push_generation(command_generation),.push_double(command_double),
  .head_index(feed_head_index),.head_generation(feed_head_generation),.head_double(feed_head_double),.level(feed_count));''', 1)
    fields.need('feed_read' not in text and 'feed_write' not in text and 'feed_count<=' not in text,
                'S4_DESCRIPTOR_FIFO_FF_OLD_STORAGE_REMOVED')
    b['files'][name] = text
    renames = {name[:-3]: name[:-3] + '_descriptor_ff_v1' for name in host_names}
    def rename(text):
        for old, new in renames.items():
            text = text.replace(old, new)
        return text
    b['files'] = {rename(name): rename(text) for name, text in b['files'].items()}
    b['top'] = rename(b['top'])
    for module in renames.values():
        text = b['files'][module + '.sv']
        anchor = '#(parameter '
        fields.need(text.count(anchor) == 1, 'S4_DESCRIPTOR_FIFO_FF_BUILD_PARAM')
        text = text.replace(anchor, '#(parameter int DESCRIPTOR_FIFO_FF=1,parameter ', 1)
        text = text.replace('endmodule', ' // synthesis translate_off\n initial if(DESCRIPTOR_FIFO_FF!=1)$fatal(1,"S4_DESCRIPTOR_FIFO_FF_BUILD_FLAG");\n // synthesis translate_on\nendmodule')
        b['files'][module + '.sv'] = text
    b['files'][DESCRIPTOR.rsplit('/', 1)[1]] = (ROOT / DESCRIPTOR).read_text()
    b['parameters'] = dict(b['parameters'], DESCRIPTOR_FIFO_FF=1)
    b['source_dependencies'] = list(dict.fromkeys(b['source_dependencies'] + [SELF, DESCRIPTOR]))
    b['source_sha256'] = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in b['source_dependencies']}
    b['rtl_sources'] = [name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256'] = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in b['files'].items()}
    b['descriptor_fifo_contract'] = 'Exact4x41 ring in explicit FFs, no pipeline/empty bypass; pre-edge head/full pop+push/clear semantics preserved. Ingress and consumer fulltuple fault checks unchanged.'
    b['scope'] = 'Source-bound descriptor-FF timing candidate; no arithmetic/calendar change and no native/physical clock inheritance.'
    return b


def bind(bundle, *, boundary_inputreg=0, descriptor_fifo_ff=0):
    return bind_descriptor(bind_boundary_host(bundle, boundary_inputreg=boundary_inputreg),
                           descriptor_fifo_ff=descriptor_fifo_ff)
