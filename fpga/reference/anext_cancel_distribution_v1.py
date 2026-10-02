"""Isolated upper-A-next host payload intent / same-edge image kill cut.

No reset distribution or arithmetic change. Old shell equivalence requires the
actual backend contract: its compute enables are already child_cancel-gated.
Raw proposals at cancel are tested separately against an early-gated old image.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENTS = {
    'rtl/kernel/genefer_track_a4_host_word_v1.sv': '255c65ed340a391e9dd43c09fbc2d6299c5fb67e9b76360e9364a8af175e62cf',
    'rtl/kernel/genefer_track_a4_host_shell_v2.sv': 'f62dab985ebb34f760e9d568b835ce17bc52fd37fdd3b71c0f0a99ae182058da',
    'rtl/kernel/genefer_track_a4_digit_image_v1.sv': '606e807d3a845697038deec169ef5b8aea572c85e4d2bf622444cd03700372f6',
    'rtl/kernel/genefer_anext_upper_ntt_sequencer_v1.sv': '6da1f271db2a6cd820d48e9a68fb12b2401dfe4384d91c17f9964fede8b7b295',
    'rtl/kernel/genefer_anext_upper_square_backend_v1.sv': 'e31528f0ccdc61abe74d19193dd49936ec7e3fbc0415bc0aca8fe769ca3124d5',
    'rtl/kernel/genefer_anext_upper_core_v1.sv': '47a84a9f20490709756af28623b3a7233832a2080a435f2fe71b2487b0dbe8bc',
}
MEASURED = 'queue/fit-r54-controller-field2h-v12/terminal/anext-upper-9668'
RECEIPT_SHA = '57a36c8c228a9491727bcf0bde9ac8b6717bd974aab0647361dfe82de5bad0db'
STA_SHA = '7f34953f6e29b9d94d0f113404f4d2ab6dd664932216a7d8603454160f4bb7fa'
TARGETS = {
    'word': 'rtl/kernel/genefer_anext_cancel_host_word_v1.sv',
    'image': 'rtl/kernel/genefer_anext_cancel_digit_image_v1.sv',
    'shell': 'rtl/kernel/genefer_anext_cancel_host_shell_v1.sv',
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def guard():
    for name, pin in PARENTS.items():
        need(sha((ROOT/name).read_bytes()) == pin, 'ANEXT_CANCEL_FROZEN_PARENT '+name)
    need(sha((ROOT/MEASURED/'receipt.json').read_bytes()) == RECEIPT_SHA and
         sha((ROOT/MEASURED/'evidence/project/output_files/probe.sta.rpt').read_bytes()) == STA_SHA,
         'ANEXT_CANCEL_ACTUAL_WHOLE_MEASUREMENT')
    backend = (ROOT/'rtl/kernel/genefer_anext_upper_square_backend_v1.sv').read_text()
    need('wire child_cancel=cancel || state==FAILED;' in backend and
         'compute_write_en=image_write_valid[1] && !fault && !child_cancel;' in backend and
         'compute_boundary_commit=image_boundary_valid[1] && !fault && !child_cancel;' in backend,
         'ANEXT_CANCEL_ACTUAL_CALLER_KILL_CONTRACT')


def transform(text, changes):
    result = text
    for old, new in changes:
        need(result.count(old) == 1, 'ANEXT_CANCEL_SINGLE_SITE '+old[:80])
        result = result.replace(old, new)
    restored = result
    for old, new in reversed(changes):
        need(restored.count(new) == 1, 'ANEXT_CANCEL_SINGLE_REVERSE_SITE')
        restored = restored.replace(new, old)
    need(restored == text, 'ANEXT_CANCEL_ONLY_DECLARED_DELTA')
    return result


def changes(kind):
    if kind == 'word':
        return (
            ('module genefer_track_a4_host_word_v1', 'module genefer_anext_cancel_host_word_v1'),
            ('output logic mem_read_en,mem_write_en,', 'output logic mem_read_en,mem_write_en,mem_write_select,'),
            ('    assign mem_write_en=state==ACCESS && write_reg && !mem_error && !cancel;',
             '    // Payload owner is independent of cancel; the original eligible enable stays immediate.\n'
             '    assign mem_write_select=state==ACCESS && write_reg && !mem_error;\n'
             '    assign mem_write_en=mem_write_select && !cancel;'))
    if kind == 'image':
        return (
            ('module genefer_track_a4_digit_image_v1', 'module genefer_anext_cancel_digit_image_v1'),
            ('input logic clk,rst_n,configure,clear_image,', 'input logic clk,rst_n,cancel,configure,clear_image,'),
            ('    wire accept=rst_n && request && !fault;',
             '    // Late same-edge kill freezes all image mutations, not a delayed/reset cancel.\n'
             '    wire accept=rst_n && request && !fault && !cancel;'),
            ('            error<=request && fault;error_code<=request && fault ? fault_code : 4\'d0;',
             '            error<=request && fault && !cancel;error_code<=request && fault && !cancel ? fault_code : 4\'d0;'),
            ('            if(request && fault)error_generation<=generation;',
             '            if(request && fault && !cancel)error_generation<=generation;'))
    if kind == 'shell':
        return (
            ('module genefer_track_a4_host_shell_v2', 'module genefer_anext_cancel_host_shell_v1'),
            ('    logic hr_en,hw_en;', '    logic hr_en,hw_en,hw_select;'),
            ('    genefer_track_a4_host_word_v1 #(.AW(AW)) host_word (',
             '    genefer_anext_cancel_host_word_v1 #(.AW(AW)) host_word ('),
            ('.mem_read_en(hr_en),.mem_write_en(hw_en),.mem_offset',
             '.mem_read_en(hr_en),.mem_write_en(hw_en),.mem_write_select(hw_select),.mem_offset'),
            ('wire multiple_writes=((|cw_mask) && hw_en) || ((|cw_mask) && compute_write_en) || (hw_en && compute_write_en);',
             'wire multiple_writes=((|cw_mask) && hw_select) || ((|cw_mask) && compute_write_en) || (hw_select && compute_write_en);'),
            ('else arbitration_error<=arbitration_fault;', 'else arbitration_error<=arbitration_fault && !bus.cancel;'),
            ('wire write_enable=((|cw_mask) || hw_en || compute_write_en) && !arbitration_fault;',
             'wire write_enable=((|cw_mask) || hw_select || compute_write_en) && !arbitration_fault;'),
            ('wire [AW-1:0] write_offset=(|cw_mask) ? cw_offset : hw_en ? h_offset : compute_write_offset;',
             'wire [AW-1:0] write_offset=(|cw_mask) ? cw_offset : hw_select ? h_offset : compute_write_offset;'),
            ('wire [15:0] write_mask=(|cw_mask) ? cw_mask : hw_en ? h_mask : compute_write_mask;',
             'wire [15:0] write_mask=(|cw_mask) ? cw_mask : hw_select ? h_mask : compute_write_mask;'),
            ('wire [511:0] write_words=(|cw_mask) ? cw_words : hw_en ? h_words : compute_write_words;',
             'wire [511:0] write_words=(|cw_mask) ? cw_words : hw_select ? h_words : compute_write_words;'),
            ('wire [1:0] write_kind=(|cw_mask) ? 2\'d1 : hw_en ? 2\'d2 : 2\'d0;',
             'wire [1:0] write_kind=(|cw_mask) ? 2\'d1 : hw_select ? 2\'d2 : 2\'d0;'),
            ('genefer_track_a4_digit_image_v1 #(.AW(AW)) image (',
             'genefer_anext_cancel_digit_image_v1 #(.AW(AW)) image ('),
            ('.clk,.rst_n,.configure,.clear_image,.base(config_base)',
             '.clk,.rst_n,.cancel(bus.cancel),.configure,.clear_image,.base(config_base)'))
    raise ValueError('ANEXT_CANCEL_KIND')


def source(kind):
    guard()
    parent = {'word':'host_word_v1', 'image':'digit_image_v1', 'shell':'host_shell_v2'}[kind]
    return transform((ROOT/('rtl/kernel/genefer_track_a4_'+parent+'.sv')).read_text(), changes(kind))


def write_sources():
    outputs = {name: source(kind) for kind,name in TARGETS.items()}
    for name in outputs:
        need(not (ROOT/name).exists(), 'ANEXT_CANCEL_FRESH_TARGET '+name)
    for name,text in outputs.items():
        with (ROOT/name).open('x') as stream:
            stream.write(text)
    return {name:sha(text.encode()) for name,text in outputs.items()}


def select_host(access, write, memory_error, cancel):
    """Frozen service state only; intent versus eligibility for the current edge."""
    proposal = bool(access and write and not memory_error)
    return proposal, proposal and not cancel


def image_accept(request, fault, cancel, reset_released=True):
    accepted = bool(reset_released and request and not fault and not cancel)
    published_error = bool(reset_released and request and fault and not cancel)
    return accepted, published_error


def ledger():
    return dict(schema='anext-cancel-distribution-v1', parent_receipt_sha256=RECEIPT_SHA,
        raw_STA_sha256=STA_SHA, scope='host_payload_intent_and_image_acceptance_only',
        source_pins=PARENTS, cycle_delta=0, image_read_RAM_E0_consumer_E1_unchanged=True,
        immediate_cancel='Physical RAM write/read, configure, correction/shadow/boundary metadata acceptance and error/read publication killed on the same edge; no cancel reset of payload/state.',
        eligibility='Payload/tag retained but ineligible; outer control quarantines and owns complete reload/generation. Held host response is unchanged.',
        caller='Old/new whole-shell comparison requires backend compute enable qualification by child_cancel. Raw canceled proposals tested by old early-gated versus new late-killed leaf pair.',
        preserved_recovery_failure=True, sequencer_reset_changed=False,
        preserved_recovery='Raw cancel remains on children_rst_n; the measured -0.267ns recovery path is NOT repaired or waived.',
        timing_claim=False, native_pass=False, promotion_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    print(json.dumps(write_sources() if args.write else ledger(), indent=2))
