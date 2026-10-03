"""Co-retime a trusted transform-ROM weight into its output register.

This is not blanket RAM output-register ON. Root service +1 and removal of
the lazy BF pre_w register are inseparable; total BF/field latency is exact.
Term and canonical final-GS pair services are excluded. Physical absorption
and LAB savings remain unmeasured until the source-matched probe.
"""
from copy import deepcopy
import hashlib
import re
from pathlib import Path
from .stream27_root_outputreg_contract import fields_with_weight_register

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_root_outputreg_bind.py'
CONTRACT = 'reference/stream27_root_outputreg_contract.py'
OLD_BF = 'genefer_ntt_lazy28_butterfly_v1'
NEW_BF = 'genefer_stream27_lazy28_rootregistered_butterfly_v1'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError(why)


def once(text, old, new):
    need(text.count(old) == 1, 'S4_ROOT_OUTREG_ANCHOR:' + old[:70])
    return text.replace(old, new, 1)


ROOT_EDITS = (
    ('logic [WIDTH-1:0] prefetched;', 'logic [WIDTH-1:0] prefetched,rom_output;\n        logic first_q;'),
    ('assign root=frame_start ? FIRST_ROOT : prefetched;', 'assign root=first_q ? FIRST_ROOT : rom_output;'),
    ('if(rst_n && in_slot_valid)prefetched<=roots[following_address];',
     'if(rst_n && in_slot_valid)begin\n                prefetched<=roots[following_address];\n                rom_output<=prefetched;\n            end'),
    ("if(!rst_n)current_row<='0;", "if(!rst_n)begin current_row<='0;first_q<=0;end"),
    ('else if(in_slot_valid)current_row<=following_row;',
     'else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end'),
)


def root_source(text, name):
    new = name + '_bf_outreg_v1'
    bound = once(text, 'module ' + name + ' #(', 'module ' + new + ' #(')
    for before, after in ROOT_EDITS:
        bound = once(bound, before, after)
    reverse = bound
    for before, after in reversed(ROOT_EDITS):
        reverse = once(reverse, after, before)
    reverse = once(reverse, 'module ' + new + ' #(', 'module ' + name + ' #(')
    need(reverse == text, 'S4_ROOT_OUTREG_LITERAL_INVERSE')
    return new, bound


def butterfly_source(text):
    edits = [
        ('module ' + OLD_BF + ' #(', 'module ' + NEW_BF + ' #('),
        ('input logic [26:0] w,', 'input logic [26:0] root_delayed,'),
        ('    logic [26:0] pre_w;\n', ''),
        ('.rhs(pre_w)', '.rhs(root_delayed)'),
        ('pre_valid<=0;pre_v<=0;pre_w<=0;gs_pipe<=0;', 'pre_valid<=0;pre_v<=0;gs_pipe<=0;'),
        ("if(in_valid && ({1'b0,u}>=TWO_P || {1'b0,v}>=TWO_P || {5'b0,w}>=P))",
         "if(in_valid && ({1'b0,u}>=TWO_P || {1'b0,v}>=TWO_P))"),
        ('if(product_valid && product>=P)',
         "if(pre_valid && {5'b0,root_delayed}>=P)\n                $fatal(1,\"Delayed trusted root range violation\");\n            if(product_valid && product>=P)"),
        ('if(in_valid)begin pre_v<=gs ? gs_diff_fold : v;pre_w<=w;end',
         'if(in_valid)begin pre_v<=gs ? gs_diff_fold : v;end'),
    ]
    bound = text
    for before, after in edits:
        bound = once(bound, before, after)
    # Removing a declaration is recovered at its exact original adjacency.
    reverse = bound
    for before, after in reversed(edits):
        if after:
            reverse = once(reverse, after, before)
        else:
            reverse = once(reverse, '    logic [27:0] pre_v;\n',
                           '    logic [27:0] pre_v;\n' + before)
    need(reverse == text, 'S4_ROOT_OUTREG_BF_LITERAL_INVERSE')
    need('pre_w' not in bound, 'S4_ROOT_OUTREG_NO_DUPLICATE_WEIGHT_REGISTER')
    return bound


def bind(bundle, *, enabled=1):
    need(type(enabled) is int and enabled in (0, 1), 'S4_ROOT_OUTREG_LITERAL_FLAG')
    out = deepcopy(bundle)
    if not enabled:
        return out
    need('root_weight_outputreg' not in out, 'S4_ROOT_OUTREG_NOT_ALREADY_BOUND')
    params = out['parameters']
    need(params['P'] == 16 and params['CONTEXTS'] == 1 and
         params.get('CORR_SERIAL_BFS') == 2 and params.get('COMM_STAGE_SHARED_MLAB') == 1 and
         params.get('MONT_FACTORED') == 1 and out['mode'] in ('warm', 'warm_signed'),
         'S4_ROOT_OUTREG_EXACT_P16_COMPOSED_FIELD_DONOR')
    files = out['files']
    bf_file = OLD_BF + '.sv'
    need(bf_file in files, 'S4_ROOT_OUTREG_BF_PARENT')
    new_bf = butterfly_source(files[bf_file])
    changes = {}
    root_names = set()
    bf_count = 0
    for name, source in list(files.items()):
        if not re.match(r'genefer_stream28_merged_(ct|gs)_.*\.sv$', name):
            continue
        if OLD_BF + ' #(' not in source:
            continue
        # The same accept is explicitly wired to root and its BF cohort.
        need('.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots)' in source,
             'S4_ROOT_OUTREG_ROOT_ACCEPT')
        count = source.count(OLD_BF + ' #(')
        cohorts = re.findall(re.escape(OLD_BF) + r' #\([\s\S]*?\);', source)
        need(len(cohorts) == count and all('.in_valid(accept)' in text for text in cohorts),
             'S4_ROOT_OUTREG_BF_ACCEPT')
        changed = source.replace(OLD_BF + ' #(', NEW_BF + ' #(')
        pattern = r'\.w\((packed_roots\[[^\n]+?)\),'
        changed, replaced = re.subn(pattern, r'.root_delayed(\1),', changed)
        need(replaced == count, 'S4_ROOT_OUTREG_EVERY_WEIGHT_PORT')
        roots = re.findall(r'\b(merged_stream27_root_(?:ct|gs)_\w+) roots \(', source)
        # Final GS is a canonical pair, not a lazy BF. Exclude its last root.
        for root in roots:
            stage = int(re.search(r'_s(\d+)_v1$', root).group(1))
            if '_gs_' in root and stage == params['AW'] - 1:
                continue
            root_names.add(root)
            changed = once(changed, root + ' roots (', root + '_bf_outreg_v1 roots (')
        files[name] = changed
        changes[name] = dict(parent_sha256=sha(source), bound_sha256=sha(changed))
        bf_count += count
    need(bf_count == (2 * params['AW'] - 1) * 8, 'S4_ROOT_OUTREG_BF_COHORT_COUNT')
    emitted = set()
    for name, source in list(files.items()):
        if not name.startswith('merged_stream27_root_library_') or not name.endswith('.sv'):
            continue
        changed = source
        for match in list(re.finditer(r'module (merged_stream27_root_\w+) #\([\s\S]*?endmodule', source)):
            module = match.group(1)
            if module not in root_names:
                continue
            new, text = root_source(match.group(0), module)
            need(changed.count(match.group(0)) == 1, 'S4_ROOT_OUTREG_MODULE_UNIQUE')
            changed = changed.replace(match.group(0), text, 1)
            emitted.add(module)
        files[name] = changed
        changes[name] = dict(parent_sha256=sha(source), bound_sha256=sha(changed))
    need(emitted == root_names, 'S4_ROOT_OUTREG_ALL_ROOT_CLOSURE')
    files[NEW_BF + '.sv'] = new_bf
    # Keep other sparse/general arithmetic and the final canonical pair exact.
    if not any(OLD_BF + ' #(' in raw for name, raw in files.items() if name != bf_file):
        del files[bf_file]
    out['rtl_sources'] = [name for name in files if name.endswith('.sv')]
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies'] + [SELF, CONTRACT]))
    out['source_sha256'] = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in out['source_dependencies']}
    out['generated_sha256'] = {name: sha(text) for name, text in files.items()}
    out['root_weight_outputreg'] = dict(enabled=1, changes=changes, root_modules=len(root_names),
        lazy_butterfly_instances=bf_count, contract=fields_with_weight_register(),
        mapped_output_registers_measured=False, LAB_savings_measured=False, whole_GO=False)
    return out
