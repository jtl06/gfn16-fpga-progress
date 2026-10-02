"""Pinned, isolated format2/input-fusion delta. No HDL execution or file writes."""
import hashlib
from pathlib import Path

ANCESTORS = {
    'genefer_square_core27_stream_prefetch': '9824a29d3b5e12f29f6e1793d84dde554d91037c0c054f070ba6fbc8cbaed540',
    'genefer_root_profile27_rom': '072487e042b3fc70bcda656ef80cfe0965b350f01fa605baa695c4df5af1c754',
    'genefer_ntt_banked27_prefetch_engine': '9381ff17205c65f5b34ba355b845e15fa25cc7ce1370f81160c147aea51c4a9c',
    'genefer_ntt_banked27_prefetch_host_engine': 'b9248c7201d64b6f1e5ef63d5f9c44edd7711df092cef055450ada3554a0a605',
}
NAMES = {
    'genefer_square_core27_stream_prefetch': 'genefer_square_core27_stream_prefetch_r2',
    'genefer_root_profile27_rom': 'genefer_root_profile27_r2_rom',
    'genefer_ntt_banked27_prefetch_engine': 'genefer_ntt_banked27_prefetch_r2_engine',
    'genefer_ntt_banked27_prefetch_host_engine': 'genefer_ntt_banked27_prefetch_r2_host_engine',
}
OLD_CONVERTER = '''            genefer_montgomery_mul27_sparse_pipe #(.P(P[f]),.Q(Q[f])) convert (
                .clk,.rst_n,.in_valid(state==CONVERT && reduce_valid_words[f][h] && !reduce_error_words[f][h]),
                .lhs(canonical_digit),.rhs(R2[f]),
                .out_valid(convert_valid_words[f][h]),.result(convert_words[f][h*32+:32])
            );'''
NEW_CONVERTER = '''            // Format2 twist consumes ordinary canonical d, not d*R.
            // Preserve the reducer and a registered boundary before NTT RAM.
            // Payload holds on bubbles/reset; reset clears eligibility only.
            always_ff @(posedge clk or negedge rst_n) begin
                if(!rst_n) convert_valid_words[f][h]<=0;
                else convert_valid_words[f][h]<=state==CONVERT &&
                    reduce_valid_words[f][h] && !reduce_error_words[f][h];
            end
            always_ff @(posedge clk) begin
                if(rst_n && state==CONVERT && reduce_valid_words[f][h] && !reduce_error_words[f][h])
                    convert_words[f][h*32+:32]<=canonical_digit;
            end'''


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('ambiguous source anchor: '+old)
    return text.replace(old, new)


def expected(name, text):
    if name not in ANCESTORS or hashlib.sha256(text.encode()).hexdigest() != ANCESTORS[name]:
        raise ValueError('frozen ancestor identity mismatch')
    text = once(text, 'module '+name+' #(', 'module '+NAMES[name]+' #(')
    if name == 'genefer_square_core27_stream_prefetch':
        text = once(text, OLD_CONVERTER, NEW_CONVERTER)
        for old in ('genefer_root_profile27_rom', 'genefer_ntt_banked27_prefetch_host_engine'):
            text = once(text, old+' #(', NAMES[old]+' #(')
        text = once(text, '.profile_format(8\'d1)', '.profile_format(8\'d2)')
        text = once(text, '// Isolated prefetch-format1 autonomous profile integration from frozen core75eb.\n'
                    '// Precision streaming carry, original61-stage CRT and input conversion unchanged.\n'
                    '// No pair CRT, R2-input fusion, tiled routing, or arithmetic substitutions.',
                    '// LOCAL UNVALIDATED RTL: format2 R2-twist/input-fusion clone of prefetch9824.\n'
                    '// All digit reducers/guards retained; standalone conversion multipliers removed.\n'
                    '// Precision streaming carry, original61-stage CRT and prefetch schedule unchanged.')
        text = once(text, '// Atomic27/R=2^32, format1 generated roots,64 arithmetic lanes/16 host lanes.',
                    '// Atomic27/R=2^32, format2 R2-twist roots,64 arithmetic lanes/16 host lanes.')
    elif name == 'genefer_root_profile27_rom':
        text = once(text, '// Fixed-size compact profile producer for generated-root format1.\n'
                    '// Separate integration candidate. No engine/core selects it yet.',
                    '// LOCAL UNVALIDATED RTL: fixed-size format2 profile for ordinary input residues.\n'
                    '// Only twist seeds use R2; recurrence steps remain R-scaled, post ordinary.')
        text = once(text, "    localparam logic [31:0] R=32'(64'h100000000%64'(P));",
                    "    localparam logic [31:0] R=32'(64'h100000000%64'(P));\n"
                    "    localparam logic [31:0] R2=32'((64'(R)*64'(R))%64'(P));")
        text = once(text, 'factor=key==0 ? R : IN;', 'factor=key==0 ? R2 : IN;')
    elif name == 'genefer_ntt_banked27_prefetch_host_engine':
        old = 'genefer_ntt_banked27_prefetch_engine'
        text = once(text, old+' #(', NAMES[old]+' #(')
    else:
        text = once(text, "profile_format!=8'd1", "profile_format!=8'd2")
    return ('// Isolated format2 experiment; source/model checks are not RTL validation.\n'+text)


def validate_files(root):
    kernel = Path(root)/'rtl/kernel'
    result = {}
    for name, new in NAMES.items():
        original = (kernel/(name+'.sv')).read_text()
        candidate = (kernel/(new+'.sv')).read_text()
        if candidate != expected(name, original):
            raise ValueError('unreviewed candidate delta: '+new)
        result[new] = hashlib.sha256(candidate.encode()).hexdigest()
    return result


FIELDS = ((104857601,4190109697,3,45971250),
          (69206017,4225761281,5,50081300),
          (67239937,4227727361,10,63576045))
RADIX = 1 << 32


def mont(x, y, p):
    """Ordinary integer oracle, independent of sparse RTL reduction."""
    if not 0 <= x < p or not 0 <= y < p:
        raise ValueError('noncanonical operand')
    return x*y*pow(RADIX, -1, p) % p


def profile_word(p, generator, aw, lanes, address, fused=True):
    """Elaboration-formula model; not execution/equivalence proof of the RTL ROM."""
    n = 1 << aw
    seed_words = 4*lanes+1
    if aw not in range(1,17) or lanes not in (16,64) or not 0 <= address < (2*aw+2)*seed_words:
        raise ValueError('invalid profile geometry/address')
    r = RADIX % p
    psi = pow(generator, (p-1)//(2*n), p)
    omega = psi*psi % p
    key, offset = divmod(address, seed_words)
    context, lane = divmod(offset, lanes)
    if key in (0, 2*aw+1):
        alpha = psi if key == 0 else pow(psi,-1,p)
        factor = (r*r % p if fused else r) if key == 0 else pow(n,-1,p)
        if offset == 4*lanes:
            return pow(alpha,4*lanes,p)*r % p
        return pow(alpha,context*lanes+lane,p)*factor % p
    stage = key-1-(aw if key>aw else 0)
    alpha = pow(omega,-1,p) if key>aw else omega
    k = (2*lanes).bit_length()-1
    h = aw-1-stage
    period = 1 if stage<k else 1 << (stage-k+1)
    if offset == 4*lanes:
        return r if period<=4 else pow(alpha,1 << (k+h+1),p)*r % p
    if lane >= min(1<<stage,lanes):
        return 0
    group = context % period
    coordinate = stage % k
    base = 0 if stage<k else ((group&1)<<coordinate)+((group>>1)%(1<<(stage-k)))*(1<<k)
    variable = lane if stage<k else (lane&((1<<coordinate)-1))|((lane>>coordinate)<<(coordinate+1))
    return pow(alpha,(base+variable)<<h,p)*r % p
