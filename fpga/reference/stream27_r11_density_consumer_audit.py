"""Consumer-live correction to R11 declared-only metadata FF accounting.

This source proof does not assert actual synthesis pruning or a LAB delta.
The paired native deliberately checks the whole W-bit transport nevertheless.
"""
import json
from fpga.reference.stream27_r11_density_audit import CAPTURE
from fpga.reference.stream27_crt_tag_delay_bind import DECL, SHIFT


def audit():
    bundle=json.loads(CAPTURE.read_bytes())
    text=next(t for t in bundle['files'].values() if DECL in t)
    # Only these three tail references exist, not an owner slice, wide read,
    # hierarchy output or alias which would make all25 owner bits live here.
    assert text.count('crt_tag[15]')==3
    assert text.count('crt_tag[15][ROW_W-1:0]')==2
    assert text.count('crt_tag[15][TAG_W-1]')==1
    assert text.count('crt_double[15]')==1
    remaining=text.replace(DECL,'').replace(SHIFT,'')
    for token in ('crt_tag[15][ROW_W-1:0]','crt_tag[15][TAG_W-1]','crt_double[15]'):
        remaining=remaining.replace(token,'')
    assert 'crt_tag' not in remaining and 'crt_double' not in remaining
    # Full ownership is validated at joined origin, and carry authority is
    # captured independently. Neither may be removed by this density seam.
    for protected in ('bank_epoch[bank]!=field_epoch[0]',
                      'bank_generation[bank]!=field_generation[0]',
                      'carry_epoch<=field_epoch[0];carry_generation<=field_generation[0];carry_context<=field_context[0];'):
        assert protected in text
    row_w=bundle['parameters']['AW']-4
    live=row_w+2
    return dict(scope='Exact captured R10 lean arithmetic consumer proof, not measured represented FF/LAB',
        declared_full_width=25+row_w+1, source_consumer_live_width=live,
        unused_at_tail_owner_bits=24,
        original_consumer_live_nominal_ff=16*live,
        candidate_consumer_live_nominal_ff=2*live+9,
        consumer_live_ff_reduction_upper_bound=14*live-9,
        whole_lab_saving=None,
        full_owner_origin_and_carry_authority_retained=True,
        native_checks_full_word=True,
        physical_measurement_required=True)


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
