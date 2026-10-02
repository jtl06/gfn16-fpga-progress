"""Read-only R89 whole-placement hierarchy partition; no field extrapolation.

Quartus reports outside parentheses inclusive, inside parentheses exclusive.
Placed ALM/FF attribution is approximately/exactly additive respectively;
needed ALM estimates are not fully additive because dense packing is estimated
again at hierarchy boundaries. Keep that measured reconciliation residual.
Scalar memory/DSP columns are inclusive and are differenced along the exact
reported hierarchy before aggregation, never summed across ancestor/child rows.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
DOSSIER='queue/standing-fit-state/terminal/s4-p16-c2-tagcompact-place-only-v1'
REPORT=DOSSIER+'/evidence/project/output_files/probe.fit.place.rpt'
REPORT_PIN='741abf430831a9df115d552bddf8c0e6583af791679ae426ae61d0168f04fde6'
METRICS={'needed_alms':1,'placed_alms':2,'recoverable_alms':3,'unavailable_alms':4,
         'memory_alms':5,'aluts':6,'registers':7,'block_bits':9,'m20k':10,'needed_dsp':11,'physical_dsp':12}
PATTERN=re.compile(r'([0-9.,]+)\s+\(([0-9.,]+)\)\Z')


def need(ok,why):
    if not ok:raise ValueError('C2_PLACE_'+why)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def number(text):return Decimal(text.replace(',',''))


def parse(text):
    nodes={};active=False
    for line_number,line in enumerate(text.splitlines(),1):
        cells=[x.strip() for x in line.split(';')][1:-1]
        if cells and cells[0]=='Compilation Hierarchy Node':active=True;continue
        if not active or len(cells)!=20 or not PATTERN.fullmatch(cells[1]):continue
        path=cells[17];need(path not in nodes,'UNIQUE_NODE '+path)
        inc={};exc={}
        for name,index in METRICS.items():
            match=PATTERN.fullmatch(cells[index])
            if match:inc[name],exc[name]=map(number,match.groups())
            else:inc[name]=number(cells[index])
        nodes[path]=dict(path=path,entity=cells[18],line=line_number,inclusive=inc,exclusive=exc,children=[])
    need('|' in nodes and len(nodes)>1,'WHOLE_ROOT_AND_CHILDREN')
    for path,node in nodes.items():
        if path=='|':continue
        parent=path.rsplit('|',1)[0] if '|' in path else '|'
        need(parent in nodes,'EXACT_PARENT '+path)
        node['parent']=parent;nodes[parent]['children'].append(path)
    for path,node in nodes.items():
        node['boundary_residual']={}
        for name,value in node['inclusive'].items():
            local=value-sum((nodes[p]['inclusive'][name] for p in node['children']),Decimal(0))
            if name not in node['exclusive']:
                # Needed DSP counts, like needed ALMs, include a merging
                # estimate. A parent's credit may exceed its child credits;
                # a negative attributed estimate is NOT a physical negativeDSP.
                need(local>=0 or name=='needed_dsp','NONNEGATIVE_MEMORY_DSP_EXCLUSIVE '+path+' '+name)
                node['exclusive'][name]=local
            else:node['boundary_residual'][name]=local-node['exclusive'][name]
    return nodes


def descendants(path,ancestor):return path==ancestor or path.startswith(ancestor+'|')


def category(node,nodes):
    path,entity=node['path'],node['entity']
    if path=='|':return 'host_publication_descriptor_control'
    if path.startswith('scratch'):return 'canonical_scratch_math_and_image'
    if path.startswith('shadows'):return 'two_context_shadow_images_and_ports'
    if path.startswith('final_c'):return 'final_correction_snapshot_memory'
    if path.startswith('descriptors'):return 'two_descriptor_FIFOs'
    if re.search(r'engine\|arithmetic\|arithmetic\[\d+\]\.carry(?:\||$)',path):return 'shared_16_carry_lanes_including_dividers'
    if re.search(r'engine\|arithmetic\|arithmetic\[\d+\]\.crt(?:\||$)',path):return 'shared_16_CRT_lanes'
    if entity=='genefer_stream27_montgomery_factored_core_v1':return 'field_factored_Montgomery_core'
    # Every vendor descendant follows its closest architectural subtree;
    # numeric Montgomery leaves are partitioned first, not counted twice.
    parents=[];current=node
    while current['path']!='|':
        parents.append(current)
        current=nodes[current['parent']]
    entities={row['entity'] for row in parents}
    if 'genefer_stream27_mdc_fifo_sync' in entities or 'genefer_stream27_delay_mlab_v1' in entities:
        return 'field_commutator_data_storage'
    if (re.search(r'\|stage\d+\.roots(?:\||$)',path) or '|term_roots' in path or
            'genefer_stream27_root_rom_prefetch' in entities or
            any('root_library' in row['entity'] for row in parents)):
        return 'field_root_ROM_and_prefetch'
    if 'genefer_ntt_lazy28_butterfly_v1' in entities:return 'field_lazy_butterfly_shell_payload_and_tags'
    if 'genefer_stream27_merged_final_gs_pair_v1' in entities:return 'field_final_GS_shell_and_normalization_alignment'
    # A boundary contains its own magnitude digit reducer. Allocate that
    # complete subtree here, not as a second independent outer digit lane.
    if 'genefer_stream27_signed_boundary_reduce27_pipe' in entities:return 'field_boundary_reducers_including_magnitude_path'
    if 'genefer_digit_reduce27_pipe' in entities:return 'field_outer_digit_reducers'
    if '|term_producer' in path:return 'field_term_context_state_selection_and_nonMont_control'
    if '|correction_transform' in path:return 'field_correction_transform_shared_nonMont'
    if '|epoch_protocol' in path:return 'field_context_epoch_protocol'
    if 'genefer_stream27_mdc_commutator_tagcompact_v1' in entities:return 'field_compact_commutator_control_dictionary'
    if re.fullmatch(r'engine\|arithmetic\|field[012]',path):return 'field_wrapper_tables_admission_join_state'
    if re.search(r'engine\|arithmetic\|field[012](?:\||$)',path):return 'field_other_add_square_term_ROM_transport'
    return 'shared_setup_profiles_recurrence_and_transport'


def add(total,values):
    for key,value in values.items():total[key]+=value


def grouped(nodes,classifier):
    result=defaultdict(lambda:dict(metrics=defaultdict(Decimal),reported_nodes=0))
    for node in nodes.values():
        row=result[classifier(node,nodes)];add(row['metrics'],node['exclusive']);row['reported_nodes']+=1
    return sorted([dict(category=name,**value) for name,value in result.items()],
                  key=lambda x:-x['metrics']['placed_alms'])


def subtree(nodes,path):
    node=nodes[path]
    return dict(path=path,entity=node['entity'],line=node['line'],inclusive=node['inclusive'],exclusive=node['exclusive'])


def source_settings(dossier):
    project=ROOT/dossier/'evidence/project'
    m=json.loads((project/'manifest.json').read_text())
    return dict(manifest=str((project/'manifest.json').relative_to(ROOT)),manifest_sha256=sha((project/'manifest.json').read_bytes()),
        top=m['top'],part=m['device'],seed=m['seed'],period_ns=m['clock_period_ns'],workers=m['compile_processors'],
        parameters=m['core_parameters'],allowed_stages=m['allowed_stages'],source_files=len(m['source_sha256']))


def front_evidence(nodes):
    outer=[n for p,n in nodes.items() if re.search(r'\|reducers\[\d+\]\.digits$',p)]
    boundary=[n for p,n in nodes.items() if re.search(r'\|reducers\[\d+\]\.boundary$',p)]
    magnitude=[n for n in nodes.values() if n['entity']=='genefer_digit_reduce27_pipe' and n not in outer]
    need(len(outer)==48 and len(boundary)==48 and len(magnitude)==48,'FRONT_POPULATION')
    def total(rows):
        result=defaultdict(Decimal)
        for n in rows:add(result,n['inclusive'])
        return dict(result)
    return dict(actual_outer_lanes=48,actual_boundary_lanes=48,embedded_magnitude_lanes=48,
        outer_inclusive=total(outer),boundary_inclusive=total(boundary),
        embedded_magnitude_inclusive_not_additive_to_boundary=total(magnitude),
        source_semantics='Outer tag1/tag2/tag3/payload_out carry common row/frame owner; good/bad are lane-specific numeric admission. Boundary magnitude payload appends independent correction sign and adds a fifth output edge. Share only proven common owner/row bits; retain independent sign, sentinel interpretation, valid/error/range, reset, occupied-token and held-output contracts.',
        source_dependencies=[dict(path=REPORT.rsplit('/output_files/',1)[0]+'/rtl/'+name,
            sha256=sha((ROOT/REPORT.rsplit('/output_files/',1)[0]/'rtl'/name).read_bytes()))
            for name in ('genefer_digit_reduce27_pipe.sv','genefer_stream27_signed_boundary_reduce27_pipe.sv')])


def analyze():
    raw=(ROOT/REPORT).read_bytes();need(sha(raw)==REPORT_PIN,'ACTUAL_REPORT_SOURCE')
    nodes=parse(raw.decode());root=nodes['|']
    sums=defaultdict(Decimal)
    for node in nodes.values():add(sums,node['exclusive'])
    residual={name:value-sums[name] for name,value in root['inclusive'].items()}
    need(residual['registers']==0 and residual['m20k']==0 and residual['block_bits']==0 and
         residual['physical_dsp']==0,'FF_MEMORY_DSP_EXACT_RECONCILIATION')
    categories=grouped(nodes,category)
    selected=[subtree(nodes,p) for p in ('|','engine','engine|arithmetic','scratch','shadows')]
    selected += [subtree(nodes,'engine|arithmetic|field'+str(f)) for f in range(3)]
    selected += [subtree(nodes,'engine|arithmetic|field'+str(f)+'|'+child)
                 for f in range(3) for child in ('term_producer','epoch_protocol','correction_transform')]
    field_total=defaultdict(Decimal)
    for f in range(3):add(field_total,nodes['engine|arithmetic|field'+str(f)]['inclusive'])
    hierarchy=dict(root=root['inclusive'],all_exclusive_sum=dict(sums),root_minus_exclusive_sum=residual,
        explanation='ALMs needed have nonadditive dense-packing attribution at hierarchy boundaries; do not relabel residual as hidden logic or fabricate exact exclusives. Derived needed-DSP boundary credits may be negative and are NOT physical counts. FFs/physical DSPs/M20K/bits close exactly; displayed placed ALM fractional attribution has small rounding residual.',
        actual_three_field_inclusive_total=dict(field_total),selected_subtrees=selected,
        disjoint_categories=categories,
        front_reducer_evidence=front_evidence(nodes),
        largest_direct_exclusive_nodes=[subtree(nodes,n['path']) for n in sorted(nodes.values(),key=lambda x:-x['exclusive']['placed_alms'])[:20]],
        largest_entity_exclusive_groups=grouped(nodes,lambda n,unused:n['entity'])[:25],
        largest_needed_attribution_boundaries=[dict(path=n['path'],line=n['line'],residual=n['boundary_residual'])
             for n in sorted(nodes.values(),key=lambda x:-abs(x['boundary_residual']['needed_alms']))[:20]])
    summary=dict(needed_alms=323047,placed_alms=389158,labs=42204,total_labs=42720,
        logic_labs=41388,memory_labs=816,lab_percent=100*42204/42720,registers=613726,m20k=2066,
        needed_dsp=1300,physical_dsp=1318,unavailable_lab_input_alms=4691,
        unavailable_lab_signal_conflict_alms=189,virtual_io_unavailable_alms=1523,
        scope='actual whole plan/place only; no routed timing or whole clock')
    comparator_path='results/throughput-20260929/trackS-p16-area-timing-whole-v1/place-result.json'
    comparator_raw=(ROOT/comparator_path).read_bytes();comparator=json.loads(comparator_raw)
    comparison=dict(path=comparator_path,sha256=sha(comparator_raw),same_report_stage='plan/place',
        source='different composed C1 source, not a clean uncompressed C2 parent',
        c1_measurements={k:comparator[k] for k in ('needed_ALM','placed_ALM','LAB','registers','M20K','MLAB','DSP_needed','DSP_placed')},
        contextual_C2_minus_C1=dict(needed_alms=323047-comparator['needed_ALM'],placed_alms=389158-comparator['placed_ALM'],
            labs=42204-comparator['LAB'],registers=613726-comparator['registers'],m20k=2066-comparator['M20K']),
        causal_delta_allowed=False)
    return dict(status='DIAGNOSED_READ_ONLY_ACTUAL_PLACEMENT',report=REPORT,report_sha256=REPORT_PIN,
        source_settings=source_settings(DOSSIER),summary=summary,hierarchy=hierarchy,
        contextual_same_stage_comparison=comparison,
        matched_parent='No clean uncompressed C2 plan/place report was collected; no isolated compact-tag whole-placement delta exists.',
        duplicated_state_not_removed_by_arithmetic_count='The actual design already shares16CRT/carry lanes, one setup, one scratch canonicalizer, three correction transforms (one perfield, not percontext). Two image banks/descriptor queues are necessary independent context storage, not duplicate arithmetic.',
        owned_work_not_new_recommendations=['GEN6/7 and compact CT/GS tags: existing authors; do not duplicate.',
            'A/B context storage4-to2 and term-context-data MLAB: stream_core/private storage authors; do not duplicate.',
            'Explicit MLAB/depth storage: existing author; do not duplicate.'],
        unowned_recommendations=[dict(name='front reducer shared owner/row transport',scope='model-first only; no RTL authorization in this diagnosis',
            evidence='48 outer digit and48 signed-boundary lanes have repeated PAYLOAD transport. Their measured inclusive totals include numeric logic and per-lane checks, NOT a removable FF or ALM estimate.',
            required_proof='Demonstrate common payload at every accepted token, occupied+origin propagation through valid and rejected paths, reset/quarantine/held-output preservation and deliberate shared-tag corruption detection. Retain every per-lane sign/sentinel/range/valid/error; normal then separate faults and matched field LAB before any whole estimate.',
            limitation='Only one credible unowned seam identified; do not invent a second or claim savings from declared payload bits.')],
        no_field_times_three_extrapolation=True,no_register_bits_area_extrapolation=True,
        no_RTL_or_native_or_fit_action=True)


def serial(value):
    if isinstance(value,Decimal):return int(value) if value==value.to_integral_value() else float(value)
    raise TypeError(type(value).__name__)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();need(not args.output.exists(),'FRESH_DIAGNOSIS')
    with args.output.open('x') as stream:json.dump(analyze(),stream,indent=2,default=serial);stream.write('\n')
