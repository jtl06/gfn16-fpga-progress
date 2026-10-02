"""Explicit declaration successor for Quartus's forward implicit-net seam.

Native SV admitted these forward wire initializers. Quartus 26.1 dropped
their drivers and pruned the actual arithmetic core. This copied-source
successor changes declaration order/continuous-assignment spelling only.
"""
from copy import deepcopy
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_contexts_explicit_nets.py'


def need(ok, label):
    if not ok:
        raise ValueError('S4_CTX_EXPLICIT_NETS_' + label)


def early(text, declaration):
    need(text.count(declaration) == 1, 'UNIQUE_DECLARATION:' + declaration.strip())
    header = text.index(');\n') + 3
    need(text.index(declaration) > header, 'DECLARATION_AFTER_HEADER')
    return text[:header] + declaration + text[header:].replace(declaration, '', 1)


def threefield(text):
    declarations = ' wire frame_profile_ok,field_input_valid;\n'
    match = re.search(r' wire frame_profile_ok=([^;]+);\n wire field_input_valid=([^;]+);\n', text)
    need(match is not None, 'PROFILE_DRIVER_ANCHOR')
    old = match[0]
    new = ' assign frame_profile_ok=' + match[1] + ';\n assign field_input_valid=' + match[2] + ';\n'
    changed = text.replace(old, new, 1)
    header = changed.index(');\n') + 3
    changed = changed[:header] + declarations + changed[header:]
    need(changed.replace(declarations, '', 1).replace(new, old, 1) == text,
         'PROFILE_DECLARATION_ASSIGN_EXACT_REVERSE')
    need(changed.index(declarations) < changed.index('.in_slot_valid(field_input_valid)'),
         'PROFILE_DECLARE_BEFORE_INSTANCE')
    return changed


def bind(bundle, enabled=1):
    need(type(enabled) is int and enabled in (0, 1), 'LITERAL_FLAG')
    result = deepcopy(bundle)
    if not enabled:
        return result
    need(bundle['parameters']['CONTEXTS'] == 2 and
         'explicit_net_declarations' not in bundle, 'TWO_CONTEXT_SUCCESSOR')
    changes = {}
    fields = carries = hosts = 0
    for name, text in list(result['files'].items()):
        changed = text
        if name.startswith('genefer_stream27_threefield_carry_'):
            changed = threefield(text)
            carries += 1
        elif name.startswith('genefer_stream27_shared_warm_'):
            declaration = ' wire [31:0] protocol_correction_base;\n'
            changed = early(text, declaration)
            # Exact relocation: remove the early copy and restore its old
            # position after the boundary/seed declarations.
            original_at = text.index(declaration)
            reverted = changed.replace(declaration, '', 1)
            need(reverted[:original_at] + declaration + reverted[original_at:] == text,
                 'FIELD_DECLARATION_EXACT_REVERSE')
            need(changed.index(declaration) < changed.index('protocol_correction_base', changed.index(declaration) + len(declaration)),
                 'FIELD_DECLARE_BEFORE_USE')
            fields += 1
        elif name == bundle['top'] + '.sv':
            declaration = ' wire canon_busy,canon_done,canon_error,canon_image_valid,canon_read_valid;\n'
            changed = early(text, declaration)
            original_at = text.index(declaration)
            reverted = changed.replace(declaration, '', 1)
            need(reverted[:original_at] + declaration + reverted[original_at:] == text,
                 'HOST_DECLARATION_EXACT_REVERSE')
            hosts += 1
        if changed != text:
            result['files'][name] = changed
            changes[name] = dict(parent_sha256=hashlib.sha256(text.encode()).hexdigest(),
                                 successor_sha256=hashlib.sha256(changed.encode()).hexdigest())
    need((fields, carries, hosts) == (3, 1, 1), 'EXACT_FIVE_SOURCE_RELOCATIONS')
    old = result['top']
    top = old + '_explicitnets_v1'
    text = result['files'].pop(old + '.sv')
    text = text.replace('module ' + old + ' #', 'module ' + top + ' #', 1)
    need(text.count('CONTEXTS=2') == 1 and text.count('CONTEXTS!=2') == 1, 'HOST_FLAG_ANCHOR')
    text = text.replace('CONTEXTS=2', 'CONTEXTS=2,EXPLICIT_NET_DECLARATIONS=1', 1)
    text = text.replace('CONTEXTS!=2', 'CONTEXTS!=2 || EXPLICIT_NET_DECLARATIONS!=1', 1)
    result['files'][top + '.sv'] = text
    result['top'] = top
    result['parameters'] = dict(result['parameters'], EXPLICIT_NET_DECLARATIONS=1)
    result['source_dependencies'] = list(dict.fromkeys(result['source_dependencies'] + [SELF]))
    result['source_sha256'] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in result['source_dependencies']}
    result['rtl_sources'] = [name for name in result['files'] if name.endswith('.sv')]
    result['generated_sha256'] = {
        name: hashlib.sha256(text.encode()).hexdigest()
        for name, text in result['files'].items()}
    need(result['geometry'] == bundle['geometry'], 'ZERO_CALENDAR_DELTA')
    result['explicit_net_declarations'] = dict(parent_top=old, changes=changes,
        declaration_only=True, public_edges_unchanged=True, native_pass_inherited=False,
        physical_memory_claim=False,
        cause='Quartus26.1 forward implicit wires dropped frame_profile_ok/field_input_valid initializers; old tiny SYN screen is invalid arithmetic scope.')
    return result
