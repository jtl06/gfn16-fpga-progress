"""Source-only T5 closure and passive-carry delta checks. No native execution."""
import hashlib
import re
from pathlib import Path
from . import core27_prefetch_r2_rootfused_crtmont_structure as parent

CORE = parent.CANDIDATE + '_prefill'
CARRY = 'genefer_carry_prefix_stream_precision_emit'
PINS = {
    'rtl/kernel/'+CORE+'.sv': 'fc8f381d0db17d3c1bff9ee4b89a99878102099b2c6a404d60157ce2c6b5d6af',
    'rtl/kernel/'+CARRY+'.sv': 'ac01093c075b8bb0f7c5493b18623209164e42659a92a0310893aee086619c3a',
    'rtl/tb/core27_prefill_probe.sv': '565c119d543ea49cef03a9288230430ed53577effbd45d0d737ea34272d6180d',
    'rtl/tb/core27_prefill_normal.cpp': '6b1ad965fdd56e89817aab364b68a8560898ef79eeaa33ee42b5026bff815104',
    'rtl/tb/core27_prefill_normal_threaded.cpp': '8d09296e3c0f799631866042303c2d3d07386322fbdcbca152b9b7baf000ecd2',
}
PARENT_REVIEWS = {
    'results/throughput-20260929/core27-prefetch-r2-rootfused-crtmont-aw5-v1/independent-review-v1.json':
        'e65ca96a9b16faa34ae2a8ab1a745f85ed8339cab5c4ee4efd7571cc2c6555a9',
    'results/throughput-20260929/core27-prefetch-r2-rootfused-crtmont-aw16-v1/independent-review-v1.json':
        'ec5e1adad36eb815b2525b30f810a1decf760a5ad1d4ec1e43502a7537ea2b0a',
}


def require(ok, message):
    if not ok: raise ValueError(message)


def remove_passive_extension(text):
    text = text.replace('module '+CARRY+' #', 'module genefer_carry_prefix_stream_precision #', 1)
    text, count = re.subn(r'    output logic \[6:0\] passes,\n    // Passive descriptor.*?emit_commit_data\n',
                         '    output logic [6:0] passes\n', text, count=1, flags=re.S)
    require(count == 1, 'carry port extension missing')
    text, count = re.subn(r'    // No new state or backpressure:.*?    // synthesis translate_off',
                         '    // synthesis translate_off', text, count=1, flags=re.S)
    require(count == 1, 'carry descriptor extension missing')
    text, count = re.subn(r'    always @\(posedge clk\)if\(emit_commit_valid\)begin.*?    // synthesis translate_on',
                         '    // synthesis translate_on', text, count=1, flags=re.S)
    require(count == 1, 'carry assertions missing')
    return text


def validate_files(root):
    root = Path(root)
    parent.validate_files(root)
    for name, expected in {**PINS, **PARENT_REVIEWS}.items():
        require(hashlib.sha256((root/name).read_bytes()).hexdigest() == expected, 'T5 pin changed: '+name)
    carry = (root/'rtl/kernel'/ (CARRY+'.sv')).read_text()
    frozen = (root/'rtl/kernel/genefer_carry_prefix_stream_precision.sv').read_text()
    require(remove_passive_extension(carry) == frozen, 'T5 changed existing carry behavior')
    core = (root/'rtl/kernel'/(CORE+'.sv')).read_text()
    old = (root/'rtl/kernel'/(parent.CANDIDATE+'.sv')).read_text()
    header = lambda s: s[s.index(' #(\n'):s.index('\n);')]
    require(header(core) == header(old), 'T5 external core contract changed')
    for token in ['genefer_digit_reduce27_pipe', 'genefer_crt3_27_mont_pipe crt',
                  'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_engine']:
        require(core.count(token) == old.count(token), 'T5 arithmetic ancestry changed')
    require('public_flat' not in core, 'T5 blanket exposure forbidden')
    replacements = {parent.CANDIDATE+'.sv': CORE+'.sv',
                    'genefer_carry_prefix_stream_precision.sv': CARRY+'.sv'}
    compiled = ['rtl/kernel/'+replacements.get(name, name) for name in parent.KERNEL_PINS]
    compiled.append('rtl/tb/core27_prefill_probe.sv')
    require(len(compiled) == len(set(compiled)) == 17, 'T5 exact 16 kernels plus observer')
    return {'compiled': compiled, 'pins': PINS, 'parent_reviews': PARENT_REVIEWS,
            'status': 'source_only_not_native_qualified'}
