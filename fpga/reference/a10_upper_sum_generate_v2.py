"""Measured pairing→sum→DSP cut, latency-neutral canonical A10 successor.

The upper Montgomery input register replaces ONE of TWO existing output
alignment registers. Shared lower BF, k+5/II1 and engine counters stay unchanged.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = 'rtl/kernel/genefer_a10_canonical_butterfly_v1.sv'
PARENT_SHA = 'c05f64749b333bbdedee8e470fb9f468f6123cd7d2f0f3b0c725cbfc41c120fc'
TARGET = 'rtl/kernel/genefer_a10_canonical_butterfly_sumlaunch_v2.sv'
POINT = 'rtl/kernel/genefer_a10_banked27_engine_pointlaunch_v3.sv'
POINT_SHA = '087bb158c0f493e22ed8e49372e233928979ed2161eff11f21f4510d2888c646'
ENGINE = 'rtl/kernel/genefer_a10_banked27_engine_sumlaunch_v4.sv'
PATH_LEDGER = 'results/throughput-20260929/a10-point-field-fit-consumption-v3/path-ledger-v2.json'
PATH_LEDGER_SHA = 'a0efaab04421b8d20fafa2fa52588ba0c69b3bca3c6c32ab63498bc50e8875dd'
DOSSIER = 'queue/fit-r54-controller-v5/terminal/a10-point-sizing'
RECEIPT_SHA = '7b46383863e86716939f260ff3fed7c4d79189b0724f8cbebeb62a65a679e45d'
STA_SHA = '488aa43602a54dc2615efc0c1d1d9b4af9f1a8577cfaa52ae79db7d419b35e18'


def need(ok, tag):
    if not ok:
        raise ValueError(tag)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def measured_guard():
    dossier = ROOT/DOSSIER
    need(sha((dossier/'receipt.json').read_bytes()) == RECEIPT_SHA and
         sha((dossier/'evidence/project/output_files/probe.sta.rpt').read_bytes()) == STA_SHA and
         sha((ROOT/PATH_LEDGER).read_bytes()) == PATH_LEDGER_SHA,
         'A10_UPPER_MEASURED_EVIDENCE_PIN')
    ledger = json.loads((ROOT/PATH_LEDGER).read_text())
    need(ledger['source_manifest_sha256'] == '99816830cde736bbade38a841fc962dcb735e81af7e84f846f1bf8349a862ec0' and
         ledger['setup']['native_sample_count'] == 10 and
         all('pairing_d[' in path['source'] and 'upper_normalizer|' in path['destination'] and
             any('reduced_sum' in node['element'] for node in path['observed_data_cone'])
             for path in ledger['setup']['paths']), 'A10_UPPER_ACTUAL_CONTROL_SUM_DSP_CONE')
    need(sha((dossier/'evidence/project/rtl'/Path(PARENT).name).read_bytes()) == PARENT_SHA and
         sha((dossier/'evidence/project/rtl'/Path(POINT).name).read_bytes()) == POINT_SHA,
         'A10_UPPER_EXACT_FITTED_SOURCES')
    return ledger


def changes():
    return (
        ('// Accepted edge k -> k+5, II1, including parallel upper normalization.',
         '// Accepted edge k -> k+5, II1. Upper sum/rhs launch replaces one output alignment stage.'),
        ('module genefer_a10_canonical_butterfly_v1 #(',
         'module genefer_a10_canonical_butterfly_sumlaunch_v2 #('),
        ('    logic [1:0] upper_valid_delay;\n    logic [31:0] upper_delay[0:1];',
         '    logic upper_launch_valid,upper_valid_delay;\n    (* preserve,dont_merge *) logic [31:0] upper_sum_launch,upper_norm_launch;\n    logic [31:0] upper_delay;'),
        ('.in_valid(in_valid && normalize_upper),\n        .lhs(reduced_sum),.rhs(normalization)',
         '.in_valid(upper_launch_valid),\n        .lhs(upper_sum_launch),.rhs(upper_norm_launch)'),
        ('if(!rst_n)begin norm_pipe<=0;upper_valid_delay<=0;out_error<=0;end',
         'if(!rst_n)begin norm_pipe<=0;upper_launch_valid<=0;upper_valid_delay<=0;out_error<=0;end'),
        ('            upper_valid_delay<={upper_valid_delay[0],upper_valid};',
         '            upper_launch_valid<=in_valid && normalize_upper;\n            upper_valid_delay<=upper_valid;'),
        ('(norm_pipe[5] && (lower_valid!=upper_valid_delay[1]))',
         '(norm_pipe[5] && (lower_valid!=upper_valid_delay))'),
        ('        if(rst_n && upper_valid)upper_delay[0]<=upper_product;\n        if(rst_n && upper_valid_delay[0])upper_delay[1]<=upper_delay[0];',
         '        if(rst_n && in_valid && normalize_upper)begin\n            upper_sum_launch<=reduced_sum;upper_norm_launch<=normalization;\n        end\n        if(rst_n && upper_valid)upper_delay<=upper_product;'),
        ('assign out_valid=lower_valid && (!norm_pipe[5] || upper_valid_delay[1]);',
         'assign out_valid=lower_valid && (!norm_pipe[5] || upper_valid_delay);'),
        ('assign y0=norm_pipe[5] ? upper_delay[1] : lower0;',
         'assign y0=norm_pipe[5] ? upper_delay : lower0;'))


def cell_source():
    measured_guard()
    raw = (ROOT/PARENT).read_bytes(); need(sha(raw) == PARENT_SHA, 'A10_UPPER_PARENT_CELL_PIN')
    source = raw.decode(); result = source
    for old, new in changes():
        need(result.count(old) == 1, 'A10_UPPER_EXACT_SITE '+old)
        result = result.replace(old, new)
    restored = result
    for old, new in reversed(changes()):
        need(restored.count(new) == 1, 'A10_UPPER_RESTORE_SITE')
        restored = restored.replace(new, old)
    need(restored == source, 'A10_UPPER_ONLY_LAUNCH_ALIGNMENT_CHANGE')
    return result


def engine_source():
    raw = (ROOT/POINT).read_bytes(); need(sha(raw) == POINT_SHA, 'A10_UPPER_POINT_PARENT_PIN')
    source = raw.decode(); old = 'genefer_a10_canonical_butterfly_v1 #'; new = 'genefer_a10_canonical_butterfly_sumlaunch_v2 #'
    need(source.count(old) == 1, 'A10_UPPER_ENGINE_SINGLE_CELL_BINDING')
    result = source.replace(old, new)
    need(result.replace(new, old) == source, 'A10_UPPER_ENGINE_NO_CYCLE_OR_CONTROL_CHANGE')
    return result


def ledger():
    return dict(accepted_to_output_edges=5, II=1,
        old_upper=dict(Mont_accept=0, Mont_result=3, alignment_capture=[4,5]),
        new_upper=dict(sum_rhs_capture=0, Mont_accept=1, Mont_result=4, alignment_capture=[5]),
        shared_lower=dict(prefix_diff_capture=0, Mont_accept=1, Mont_result=4, output_capture=5),
        eligibility='upper_launch_valid+Montvalid+onealignmentvalid match norm_pipe[5]; reset clears eligibility, payload retained.',
        normalization_capture='Both canonical reduced_sum and per-request normalization captured at acceptededge, no assumedconstant rhs.',
        arithmetic_domain='u,v,w<P; normalization<P when used;33bit sum<2P canonical fold;32bit Mont input remains canonical.',
        net_extra_payload_bits_per_lane=32, net_extra_payload_bits_per_field=2048,
        valid_register_count_delta=0, DSP_source_delta=0, ROM_source_delta=0,
        engine_cycle_delta=0, external_host_block_ABI_delta=0,
        point_cycle_prediction=1032, transform_cycle_prediction=8336,
        whole_controller_NTT_prediction=17710,
        native_verified=False, physical_verified=False, promotion_allowed=False)
