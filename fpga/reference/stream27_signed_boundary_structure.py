"""Exact source-only contract for S3 signed c0/c1 reduction; no HDL run."""
import hashlib
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
RTL='rtl/kernel/genefer_stream27_signed_boundary_reduce27_pipe.sv'
PINS={
    RTL:'140fcad078bd089456712e27eed9c1f78f340298f72a7d6860d5bed70bbb9f2d',
    'rtl/kernel/genefer_digit_reduce27_pipe.sv':'61e14bb13c2dbcc13b5030756578a0d0358269beb24fb207a5641b98795883e8',
    'reference/stream27_signed_boundary_oracle.py':'55df355cd27cf92ce9c090eeb46d6788ba7e3cbeabab5ca6f47f9c5593d6dd6f',
}


def validate(root=ROOT):
    root=Path(root)
    for name,pin in PINS.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=pin:
            raise ValueError('S3 signed-boundary source identity: '+name)
    text=(root/RTL).read_text()
    section=text[text.index('always_ff'):text.index('// synthesis translate_off')]
    registers=set(re.findall(r'\b(\w+)\s*<=',section))
    if text.count('always_ff')!=1 or registers!={'out_valid','out_error','residue','payload_out'}:
        raise ValueError('extra sign-output pipeline/state')
    return dict(status='source_only_not_native_or_physical_qualified',source_sha256=PINS,
        input_width=32,widened_signed_magnitude_width=33,acceptance_output_edge_offset=4,
        magnitude_child_edge_offset=3,extra_sign_output_edges=1,initiation_interval=1,
        payload_sign_packing='{correction[31],payload_in}',
        invalid_poison='0x80000000 (child error; not legal0xffffffff signed-1 special case)',
        output_domain='ordinary canonical0<=residue<P',
        bounds='c0:abs<=base-1; c1:abs<=2N+24BLOCKS; full base gate enforced',
        controller_owns=['base/profile/generation coherence','quarantine and reload','whole CRT coefficient/width eligibility'])
