"""Private R88 C2 arithmetic storage seam; disabled is byte-identical.

Four logical leases and all full owners remain. Only the A/B coefficient and
four-row term payload stores become two physical banks keyed by context.
This is a SOURCE candidate, not native qualified or an area-saving claim.
Closed fullN host I8459/cold fence only; never silently apply to raw field ABI.
"""
import copy
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_storage_banks_bind.py'
TERM = 'genefer_stream27_term_context_param_v1_contexts_v1'
TERM_PIN = 'd80b52222fca64f7753e592931d5d81d6c3652d6284d337fc3416d65a0660014'
HOST_PIN = 'cb734faeef4ebe4e95d8a6924e8467253d66e686a0aaa5ec13b2c2cca8bd9e3b'
FIELD_PINS = ('dd27a59831f41ba5cf0fd7a4228e8c0b4ced3645827dd2e75ac18e1c02824ba3',
              '4d761cb13245041d7d341d7473f16d3c67b7620306cceff98bf14eea414d5f15',
              'e0a46bb75586c576a0fa2c8cf153fce78f8e8daf105157657e4721a942faf6ed')


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('C2_STORAGE_ANCHOR:' + before[:70])
    return text.replace(before, after, 1)


def leaf(text):
    if hashlib.sha256(text.encode()).hexdigest() != TERM_PIN:
        raise ValueError('C2_STORAGE_TERM_PARENT')
    new = TERM + '_storage2_v1'
    text = once(text, 'module ' + TERM + ' #', 'module ' + new + ' #')
    for before, after in (
        ('context_data[0:3][0:3]', 'context_data[0:1][0:3]'),
        ('context_row[0:3][0:3]', 'context_row[0:1][0:3]'),
        ('context_valid[0:3]', 'context_valid[0:1]'),
        ('bank_owner[0:3]', 'bank_owner[0:1]'),
        ('wire [1:0] pw_bank=pointwise_owner[26:25],prod_bank=product_owner[26:25],seed_bank=seed_owner[26:25];',
         'wire pw_bank=pointwise_owner[24],prod_bank=product_owner[24],seed_bank=seed_owner[24];'),
        ('for(int bank=0;bank<4;bank=bank+1)context_valid[bank]',
         'for(int bank=0;bank<2;bank=bank+1)context_valid[bank]')):
        text = once(text, before, after)
    # Full27-bit bank_owner comparisons, E4 bypass, validity and arithmetic
    # remain literal parent statements, including product owner mismatch.
    return new, text


def field(name, text):
    new = name + '_storage2_v1'
    text = once(text, 'module ' + name + ' #', 'module ' + new + ' #')
    text = once(text, 'A_table[0:3][0:LANES-1],B_table[0:3][0:LANES-1]',
                'A_table[0:1][0:LANES-1],B_table[0:1][0:LANES-1]')
    text = once(text, 'logic [3:0] tables_ready;', '''logic [3:0] tables_ready;
 logic [1:0] payload_reserved,payload_ready;
 logic [26:0] payload_owner[0:1];''')
    # Only payload addresses change; table epoch/generation/ready authority
    # stays indexed by logical bank and is joined with the new full key.
    for array, old, new_index, count in (
        ('A_table', 'pointwise_bank', 'fwd_generation[24]', 16),
        ('B_table', 'pointwise_bank', 'fwd_generation[24]', 16),
        ('B_table', 'seed_owner[26:25]', 'seed_owner[24]', 16),
        ('A_table', 'small_owner[26:25]', 'small_owner[24]', 16),
        ('B_table', 'small_owner[26:25]', 'small_owner[24]', 16)):
        anchor = array + '[' + old + ']'
        if text.count(anchor) != count:
            raise ValueError('C2_STORAGE_PAYLOAD_INDEX:' + anchor)
        text = text.replace(anchor, array + '[' + new_index + ']')
    text = once(text, 'if(c1_pending || seed_running)admission_bad=1;',
                'if(c1_pending || seed_running || payload_reserved[correction_context])admission_bad=1;')
    text = once(text, 'table_context[pointwise_bank]!=fwd_generation[24])) ||',
                '''table_context[pointwise_bank]!=fwd_generation[24] ||
   !payload_ready[fwd_generation[24]] ||
   payload_owner[fwd_generation[24]]!={pointwise_bank,fwd_generation})) ||''')
    text = once(text, 'tables_ready<=0;controller_error<=0;',
                'tables_ready<=0;payload_reserved<=0;payload_ready<=0;controller_error<=0;')
    text = once(text, 'if(accepted_correction)begin high_correction<=c1_in;',
                '''if(accepted_correction)begin
     payload_reserved[correction_context]<=1;payload_ready[correction_context]<=0;
     high_correction<=c1_in;''')
    text = once(text, 'if(small_slot)begin', '''if(small_slot)begin
     if(!small_capture)payload_owner[small_owner[24]]<=small_owner;''')
    text = once(text, 'if(fwd_slot)begin addA_row<=pw_row;addA_bank<=pointwise_bank;end',
                '''if(fwd_slot)begin addA_row<=pw_row;addA_bank<=pointwise_bank;
     if(pw_row==ROW_W'(ROWS-1) && payload_owner[fwd_generation[24]]=={pointwise_bank,fwd_generation})begin
      payload_reserved[fwd_generation[24]]<=0;payload_ready[fwd_generation[24]]<=0;
     end
    end
    if(term_cache_ready && payload_reserved[term_cache_owner[24]] &&
       payload_owner[term_cache_owner[24]]==term_cache_owner)payload_ready[term_cache_owner[24]]<=1;''')
    text = once(text, TERM + ' #', TERM + '_storage2_v1 #')
    return new, text


def bind(bundle, *, enabled=0):
    if type(enabled) is not int or enabled not in (0, 1):
        raise ValueError('C2_STORAGE_BOOL_FLAG')
    result = copy.deepcopy(bundle)
    if not enabled:
        return result
    g = result['geometry']
    if any(g.get(k) != v for k, v in {'n': 65536, 'p': 16, 'contexts': 2,
        'warm_interval': 8459, 'lease_banks': 4, 'corr_serial_bfs': 2}.items()):
        raise ValueError('C2_STORAGE_CLOSED_HOST_GEOMETRY')
    files = result['files']
    host = files[result['top'] + '.sv']
    if hashlib.sha256(host.encode()).hexdigest() != HOST_PIN or \
       'CONTEXT_OFFSET=4229,SECOND_CORRECTION=8233;' not in host or 'COLD_LAUNCH_FENCE=1' not in host:
        raise ValueError('C2_STORAGE_COLD_FENCE')
    renames = {}
    name, text = leaf(files.pop(TERM + '.sv'))
    files[name + '.sv'] = text
    for f, pin in enumerate(FIELD_PINS):
        matches = [key for key in files if key.startswith('genefer_stream27_shared_warm_aw16_p16_f' + str(f)) and key.endswith('_contexts2_v1.sv')]
        if len(matches) != 1 or hashlib.sha256(files[matches[0]].encode()).hexdigest() != pin:
            raise ValueError('C2_STORAGE_FIELD_PARENT:' + str(f))
        old = matches[0][:-3]
        name, text = field(old, files.pop(old + '.sv'))
        files[name + '.sv'] = text
        renames[old] = name
    # Identifier-only caller wiring; original setup/CRT/general Montgomery
    # leaves and all tag/lease transport remain untouched.
    for filename, text in list(files.items()):
        for old, new in renames.items():
            text = re_identifier(text, old, new)
        files[filename] = text
    oldtop = result['top']
    newtop = oldtop + '_storage2_v1'
    files[newtop + '.sv'] = once(files.pop(oldtop + '.sv'), 'module ' + oldtop + ' #', 'module ' + newtop + ' #')
    result['top'] = newtop
    result['rtl_sources'] = [key for key in files if key.endswith('.sv')]
    result['generated_sha256'] = {key: hashlib.sha256(text.encode()).hexdigest() for key, text in files.items()}
    result['source_dependencies'] = list(dict.fromkeys(result.get('source_dependencies', []) + [SELF]))
    result['source_sha256'] = dict(result.get('source_sha256', {}), **{
        SELF: hashlib.sha256((ROOT / SELF).read_bytes()).hexdigest()})
    result['storage_contract'] = dict(physical_banks=2, logical_leases=4, enabled=1,
        closed_host_only=True, full_owner_bits=27, default_adopted=False,
        scope='SOURCE candidate; needs own numerical/fault/native/matched-resource evidence; no saving credit')
    return result


def re_identifier(text, old, new):
    import re
    return re.sub(r'(?<![A-Za-z0-9_$])' + re.escape(old) + r'(?![A-Za-z0-9_$])', new, text)
