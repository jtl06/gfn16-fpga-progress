"""Additive AW8/full closed-host storage2 binding; clean C2 parent only.

Imports the frozen v1 text transform, never current shared generators. All
four logical leases/full27 owners remain; each geometry has its own whitelist.
"""
import copy
import hashlib
from pathlib import Path
import re

from . import stream27_context_storage_banks_bind as parent

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_storage_banks_bind_v2.py'
PARENT_PIN = '0410e782a72be901e523d3ab989c89bafc14ba52d0f5802c0103f197fe7101be'
SMALL_HOST = 'adfec31890377979f0e066790608633273d88aef193f471aa4e34945058ed496'
SMALL_FIELDS = ('e08f26cead784a6890c50dfdbbd9d48f8144bb64f3c30d2ed73c3151710b5fcc',
    '4fd2d63c6e45a4f4f35a1a625e31a2deb19b3942392c1834cdda812806108537',
    '50b34010a547f4e1bd0eb2c961dd2ce3ea809af0a5742303b839122059eb2837')


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def bind(bundle, *, enabled=0):
    if type(enabled) is not int or enabled not in (0, 1):
        raise ValueError('C2_STORAGE2_BOOL_FLAG')
    result = copy.deepcopy(bundle)
    if not enabled:
        return result
    if hashlib.sha256((ROOT / parent.SELF).read_bytes()).hexdigest() != PARENT_PIN:
        raise ValueError('C2_STORAGE2_FROZEN_TRANSFORM')
    g = result['geometry']
    if g.get('p') != 16 or g.get('contexts') != 2 or g.get('lease_banks') != 4 or g.get('corr_serial_bfs') != 2:
        raise ValueError('C2_STORAGE2_CLOSED_HOST')
    n = g.get('n')
    if n not in (256, 65536):
        raise ValueError('C2_STORAGE2_SUPPORTED_GEOMETRY')
    aw = 8 if n == 256 else 16
    expected = dict(warm_interval=212, pointwise_accept=78, rows=16,
                    next_correction_accept=212, last_sink=166) if aw == 8 else dict(
                        warm_interval=8459, pointwise_accept=4207, rows=4096,
                        next_correction_accept=12557, last_sink=12511)
    if any(g.get(k) != value for k, value in expected.items()):
        raise ValueError('C2_STORAGE2_EXACT_READ_WRITE_CALENDAR')
    files = result['files']
    top = result['top']
    host_pin = SMALL_HOST if aw == 8 else parent.HOST_PIN
    if sha(files[top + '.sv']) != host_pin:
        raise ValueError('C2_STORAGE2_CAPTURED_HOST')
    if 'genefer_stream27_mdc_commutator_shared_mlab_v1.sv' not in files or any('tagcompact' in key for key in files):
        raise ValueError('C2_STORAGE2_CLEAN_PARENT_NOT_COMPOSITE')
    original = dict(files)
    field_pins = SMALL_FIELDS if aw == 8 else parent.FIELD_PINS
    name, text = parent.leaf(files.pop(parent.TERM + '.sv'))
    files[name + '.sv'] = text
    renames = {}
    for f, pin in enumerate(field_pins):
        matches = [key for key in files if key.startswith(f'genefer_stream27_shared_warm_aw{aw}_p16_f{f}') and key.endswith('_contexts2_v1.sv')]
        if len(matches) != 1 or sha(files[matches[0]]) != pin:
            raise ValueError('C2_STORAGE2_EXACT_FIELD:' + str(f))
        old = matches[0][:-3]
        name, text = parent.field(old, files.pop(old + '.sv'))
        files[name + '.sv'] = text
        renames[old] = name
    for filename, text in list(files.items()):
        for old, new in renames.items():
            text = parent.re_identifier(text, old, new)
        files[filename] = text
    newtop = top + '_storage2_v1'
    files[newtop + '.sv'] = parent.once(files.pop(top + '.sv'), 'module ' + top + ' #', 'module ' + newtop + ' #')
    result['top'] = newtop
    result['rtl_sources'] = [key for key in files if key.endswith('.sv')]
    result['generated_sha256'] = {key: sha(text) for key, text in files.items()}
    result['source_dependencies'] = list(dict.fromkeys(result.get('source_dependencies', []) + [parent.SELF, SELF]))
    result['source_sha256'] = dict(result.get('source_sha256', {}), **{
        key: hashlib.sha256((ROOT / key).read_bytes()).hexdigest() for key in (parent.SELF, SELF)})
    delta = []
    for old, text in original.items():
        new = old if old in files else old[:-3] + '_storage2_v1.sv'
        if files[new] != text:
            delta.append(dict(parent=old, candidate=new, parent_sha256=sha(text), candidate_sha256=sha(files[new])))
    if len(delta) != 6 or len(files) != 53:
        raise ValueError('C2_STORAGE2_SIX_NAMESPACE_DELTA')
    result['storage_contract'] = dict(physical_banks=2, logical_leases=4, full_owner_bits=27,
        clean_parent=True, closed_host_only=True, changed=delta, unchanged=47,
        geometry=expected, native_qualified=False, measured_area_saving=None,
        scope='Private actual source candidate; default0 exact; own normals/fault/resource evidence required')
    return result
