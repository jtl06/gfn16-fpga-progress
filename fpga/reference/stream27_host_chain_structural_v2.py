"""Additive explicit producer/consumer endpoints for the exact whole P8 core.

The v1 inventory remains frozen. This successor splits every field-to-CRT
transfer into its upper/lower parallel branches and names the actual source
output flop before the CRT input flop. Companion anchors bind shared metadata
and branch connections, not an inferred netlist/timing completeness claim.
"""
import copy
import hashlib
import json
from pathlib import Path
from . import stream27_host_chain_structural_v1 as parent
from fpga.tools.prefit_structural_guard_v1 import source_inventory, identities

ROOT = parent.ROOT
BASE = ROOT / 'results/throughput-20260929/s4-p8-whole-host-structural-source-v1/inventory.json'
BASE_PIN = 'c55ab4ae7a222d1568a8726d53bbfbb0a7ede632576b32c16b66a3835e640e9d'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory():
    project = ROOT / parent.PROJECT
    if sha(BASE) != BASE_PIN or sha(project / 'manifest.json') != parent.PROJECT_PIN:
        raise ValueError('S4_STRUCTURE_V2_PARENT_DRIFT')
    if sha(ROOT / 'tools/prefit_structural_guard_v1.py') != parent.CHECKER_PIN:
        raise ValueError('S4_STRUCTURE_V2_CHECKER_DRIFT')
    spec = json.loads(BASE.read_text())
    source_inventory(project, spec)
    updated = []
    for transfer in spec['transfers']:
        if transfer['id'] not in [f'field{f}_to_CRT' for f in range(3)]:
            updated.append(transfer)
            continue
        f = int(transfer['producer'][-1])
        gs = f'genefer_stream28_merged_gs_aw16_p8_f{f}_v1.sv'
        for branch in ('upper', 'lower'):
            value = copy.deepcopy(transfer)
            value['id'] = f'field{f}_{branch}_to_CRT'
            value['signals'] = [f'r{f+1} {branch} lanes', 'joined', 'epoch/generation/row']
            if branch == 'upper':
                producer = parent.stage(f'field{f}_GS_upper_output', f'field{f}', 0,
                    'genefer_stream27_merged_final_gs_pair_v1.sv', ['upper_delay[1] / y0'],
                    'lower_valid && upper_valid_delay[1] && !out_error',
                    ['final GS slot_pipe[5]/start_pipe[5]/generation_pipe[5]'],
                    ['if(upper_valid_delay[0])upper_delay[1]<=upper_delay[0];',
                     'upper_valid_delay<={upper_valid_delay[0],upper_valid};'],
                    note='Parallel normalized upper output register at accepted k+5. Metadata is the same-edge final GS six-stage pipe, checked by companion anchors and existing native row/tag comparisons.')
            else:
                producer = parent.stage(f'field{f}_GS_lower_output', f'field{f}', 0,
                    'genefer_ntt_banked27_engine.sv', ['genefer_ntt_difdit_butterfly27.y1 / lower'],
                    'out_valid / product_valid; qualified by final_pair out_valid',
                    ['final GS slot_pipe[5]/start_pipe[5]/generation_pipe[5]'],
                    ['out_valid<=product_valid;', 'y1<=dif_pipe[4] ? product :'],
                    note='Registered normalized lower output of final_pair.lower_pipeline, parallel to upper_delay[1] at accepted k+5. Companion anchors bind the instantiated leaf and parent metadata.')
            crt_input = copy.deepcopy(transfer['registered_stages'][0])
            crt_input['edge'] = 1
            # Both parallel producer leaves transfer into the same CRT input
            # edge; the old downstream centered stage is not used as a
            # substitute for the source endpoint.
            value['registered_stages'] = [producer, crt_input]
            value['companion_source_anchors'] = [
                {'source': 'rtl/genefer_stream27_merged_final_gs_pair_v1.sv',
                 'text': '.out_valid(lower_valid),.y0(unused_upper),.y1(lower));'},
                {'source': 'rtl/genefer_stream27_merged_final_gs_pair_v1.sv',
                 'text': 'assign y0=upper_delay[1];assign y1=lower;'},
                {'source': 'rtl/' + gs,
                 'text': 'assign slot[16]=slot_pipe[5] && (&bf_valid) && !stop;'},
                {'source': 'rtl/' + gs,
                 'text': 'assign start[16]=start_pipe[5];assign generation[16]=generation_pipe[5];'},
                {'source': 'rtl/' + gs,
                 'scope_marker': 'if(1)begin: stage15',
                 'text': 'for(int k=1;k<6;k=k+1)generation_pipe[k]<=generation_pipe[k-1];'}]
            updated.append(value)
    spec['transfers'] = updated
    companion_checks = []
    for transfer in updated:
        for anchor in transfer.get('companion_source_anchors', []):
            if anchor['source'] not in spec['sources']:
                raise ValueError('S4_STRUCTURE_V2_COMPANION_CLOSURE')
            text = (project / anchor['source']).read_text()
            if 'scope_marker' in anchor:
                if text.count(anchor['scope_marker']) != 1:
                    raise ValueError('S4_STRUCTURE_V2_COMPANION_SCOPE')
                text = text.split(anchor['scope_marker'], 1)[1]
            if text.count(anchor['text']) != 1:
                raise ValueError('S4_STRUCTURE_V2_COMPANION_ANCHOR:' + anchor['text'])
            companion_checks.append({'transfer': transfer['id'], **anchor})
    result = source_inventory(project, spec)
    if result['findings']:
        raise ValueError('S4_STRUCTURE_V2_FINDINGS:' + repr(result['findings']))
    return spec, result, companion_checks


def prepare(destination):
    destination = Path(destination).resolve()
    if destination.exists() or (ROOT / 'docs/briefs/PAUSE').exists():
        raise ValueError('S4_STRUCTURE_V2_FRESH_PAUSE')
    spec, result, companions = inventory()
    destination.mkdir()
    (destination / 'inventory.json').write_text(json.dumps(spec, indent=2) + '\n')
    receipt = dict(status='PASS_declared_whole_source_inventory_only', **identities(spec),
        project_manifest_sha256=parent.PROJECT_PIN, inventory_sha256=sha(destination / 'inventory.json'),
        parent_inventory_sha256=BASE_PIN, preparer_sha256=sha(__file__), checker_sha256=parent.CHECKER_PIN,
        compiled_sv=49, transfers=len(spec['transfers']), source_inventory=result,
        companion_source_checks=companions, fit_allowed=False, promotion_allowed=False,
        limitations=['No netlist crossing completeness or physical timing claim',
                    'Ordinary fit-owner source, budget, resources and whole21780s horizon admission remain required',
                    'No field exemption, fieldclock or threefield-area inheritance'])
    (destination / 'source-preparation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    import sys
    print(json.dumps(prepare(sys.argv[1]), indent=2))
