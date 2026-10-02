"""R91 STEP0: disjoint actual hierarchy attribution, not removable-overhead credit.

Only named metadata, descriptor and final/setup/image subtrees are isolated.
Checks/dictionaries/flow embedded in arithmetic/controller entities remain
explicitly mixed or unassigned. C1 final FIT and C2 PLACE are different stages,
sources and settings: their individual shares are NOT an isolated delta.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
from fpga.reference.stream27_c2_place_resource_diagnosis import parse,serial

PREFIX='queue/standing-fit-state/terminal/'
COHORTS={
 'C1_timing7':dict(project=PREFIX+'s4-p16-timing-whole-9000-high-effort-v1/evidence/project',
    report='probe.fit.rpt',pin='edcd542437154678630783c3f6aa28115795fffe603c213f785b2f1d19976499',stage='final FIT',
    settings='9ns/HighPerformanceEffort/seed1/Azure4; adopted source64',expected_register_residual=2),
 'C2_compact':dict(project=PREFIX+'s4-p16-c2-tagcompact-place-only-v1/evidence/project',
    report='probe.fit.place.rpt',pin='741abf430831a9df115d552bddf8c0e6583af791679ae426ae61d0168f04fde6',stage='PLACE only',
    settings='10ns/Balanced/seed1/Azure4; compact corrected C2 source53',expected_register_residual=0)}
FIELDS=('needed_alms','placed_alms','registers','block_bits','m20k','physical_dsp')
NAMES={
 'metadata_named':'Named metadata/fault transport only (includes required occupied authority)',
 'once_named':'Isolated canonical/image/setup subtrees (still required by current contract)',
 'dynamic_named':'Isolated descriptor FIFO flow',
 'mixed_shells':'Identifiable mixed checks/dictionaries/flow/numeric state',
 'other_datapath':'Remaining datapath/storage with embedded unsplit guards/control'}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def ancestors(node,nodes):
    result=[node]
    while result[-1]['path']!='|':result.append(nodes[result[-1]['parent']])
    return result


def classify(node,nodes):
    path=node['path'];a=ancestors(node,nodes);entities={n['entity'] for n in a}
    if any(re.search(r'\|(?:upper_tags|lower_tags|crt_tag_rtl_0|table_epoch_rtl_rtl_0|table_generation_rtl_0|bank_owner_rtl_0)(?:\||$)',n['path'])
           for n in a) or 'genefer_stream27_quarantine_replicas_v1' in entities:
        return 'metadata_named'
    if 'genefer_stream27_descriptor_fifo_ff_v1' in entities:return 'dynamic_named'
    if (path.startswith('scratch') or path.startswith('shadows') or path.startswith('host_image') or
        path.startswith('engine|final_image') or path.startswith('final_c0') or path.startswith('final_c1') or
        'genefer_stream27_blockcarry_setup_param_v1' in entities or 'genefer_track_a4_setup_v1' in entities):
        return 'once_named'
    # ONLY direct exclusives of these mixed parents are allocated here;
    # their numeric children are NOT swept into an overhead estimate.
    entity=node['entity']
    if ('epoch_protocol' in entity or 'mdc_commutator_shared_mlab' in entity or
        'mdc_commutator_tagcompact' in entity or entity.startswith('genefer_stream27_term_context_param') or
        entity.startswith('genefer_stream27_correction_serial') or
        entity.startswith('genefer_stream27_shared_warm_') or
        entity.startswith('genefer_stream27_threefield_carry_') or
        entity.startswith('genefer_stream27_host_') or
        entity.startswith('genefer_stream27_warm_') or
        entity.startswith('genefer_stream27_chain_canonical_') or
        'digit_reduce27_pipe' in entity or 'signed_boundary_' in entity or
        re.search(r'\|profile_(?:base|limit|reciprocal)_rtl_0(?:\||$)',path)):
        return 'mixed_shells'
    return 'other_datapath'


def report(cohort):
    project=ROOT/cohort['project'];path=project/'output_files'/cohort['report'];raw=path.read_bytes()
    if sha(raw)!=cohort['pin']:raise ValueError('R91_ACTUAL_REPORT')
    nodes=parse(raw.decode());whole=nodes['|']['inclusive'];groups={}
    for name in NAMES:groups[name]=dict(label=NAMES[name],metrics=defaultdict(Decimal),reported_rows=[])
    for node in nodes.values():
        name=classify(node,nodes);g=groups[name]
        for metric in FIELDS:g['metrics'][metric]+=node['exclusive'][metric]
        if name!='other_datapath' and any(node['exclusive'][m] for m in FIELDS):
            g['reported_rows'].append(dict(path=node['path'],entity=node['entity'],line=node['line'],
                exclusive={k:node['exclusive'][k] for k in FIELDS}))
    residual={k:whole[k]-sum(g['metrics'][k] for g in groups.values()) for k in FIELDS}
    if (residual['registers']!=cohort['expected_register_residual'] or
            any(residual[k] for k in ('block_bits','m20k','physical_dsp'))):
        raise ValueError('R91_DISJOINT_EXACT_CLOSURE')
    for name,g in groups.items():g['percent_of_whole']={k:(100*g['metrics'][k]/whole[k] if whole[k] else 0) for k in FIELDS}
    tags=[n for p,n in nodes.items() if p.endswith('|upper_tags') or p.endswith('|lower_tags')]
    dictionary_parents=[n for n in nodes.values() if n['entity']=='genefer_stream27_mdc_commutator_tagcompact_v1']
    mraw=(project/'manifest.json').read_bytes();manifest=json.loads(mraw)
    observer=[name for name in manifest['source_sha256'] if 'observer' in name.lower()]
    if observer:raise ValueError('R91_UNEXPECTED_PRODUCTION_OBSERVER')
    special=dict(actual_tag_delay_instances=len(tags),tag_delay_instances_with_M20K=sum(n['inclusive']['m20k']>0 for n in tags),
        total_tag_delay_M20K=sum(n['inclusive']['m20k'] for n in tags),
        actual_compact_dictionary_parent_instances=len(dictionary_parents),
        dictionary_ALM_FF_separately_resolved=False,
        explanation='Full compact owner dictionaries and flow counters share their parent with numeric output FFs. Do not count the complete parent as dictionary/check logic. Quoted120 tag memories is not the measured current count;144 upper/lower delay instances contain72 M20Ks in each report, with additional small authority RAM elsewhere.',
        synthesized_observer_modules=0,embedded_metric_port_increment_unknown=True,
        translate_off_assertions='Excluded from synthesized production source by translate_off; no fabricated checker ALM cost.')
    return dict(report=str(path.relative_to(ROOT)),sha256=cohort['pin'],stage=cohort['stage'],settings=cohort['settings'],
        manifest_sha256=sha(mraw),top=manifest['top'],whole={k:whole[k] for k in FIELDS},
        buckets=groups,attribution_residual=residual,special_evidence=special,
        register_attribution_boundaries=[dict(path=n['path'],line=n['line'],unattributed_registers=n['boundary_residual']['registers'])
            for n in nodes.values() if n['boundary_residual']['registers']])


def analyze():
    return dict(status='READ_ONLY_STEP0_ATTRIBUTION_NOT_REMOVABILITY',cohorts={name:report(c) for name,c in COHORTS.items()},
        method='Each exact hierarchy row is assigned once using its exclusive ALM/FF values; inclusive RAM/DSP counts are differenced across exact children. Never sum ancestor and child metrics. Needed ALM packing estimates and placed fractional rounding retain residuals.',
        caveats=[
            'Named metadata is only an isolated measured subset, NOT the total cost of tags/checks. Mixed shells and arithmetic contain owner/validation/fault/calendar terms that these reports cannot separate.',
            'Once category covers final canonicalizer, images/snapshots and setup. Cold digit reducers also run on warm feedback; they are mixed, not once-only. Profile storage is consumed repeatedly by carry and is mixed. Copy/publication/host arbitration share controllers with ongoing commands.',
            'The dynamic-only descriptor FIFO is an isolated subset. Commute enable/phase/counters, skid/feedback validity and fault-stop flow are embedded in mixed or datapath entities. Fixed calendars do not authorize removing halt/quarantine or occupied authority.',
            'C1 final FIT and C2 PLACE differ in report stage, source, context count and effort/period; individual shares are valid, no causal timing-versus-control area delta is claimed.',
            'No duty-cycle or0.4ms host-offload claim is derived from resource rows. Required memory/control remains under current record/fault/host contracts.',
            'Front common tag sharing is not a fault-equivalent drop-in: modeled single shared-tag corruption escapes the existing lane equality check. Prior counterexample remains binding.'
        ],policy=dict(A_lean_production='HOLD_PENDING_DIRECT_HUMAN_APPROVAL',B_host_offload='HOLD_PENDING_DIRECT_HUMAN_APPROVAL',
            C_D='model suggestions only after existing cohorts; no extra jobs from this deliverable',
            RTL_fault_rules_record_boundary_hosts_unchanged=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with args.output.open('x') as stream:json.dump(analyze(),stream,indent=2,default=serial);stream.write('\n')
