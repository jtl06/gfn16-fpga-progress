"""Read-only R85 diagnosis of captured timing7 CRT/carry mapping.

Parses existing Quartus reports and exact captured RTL. No RTL generation,
vendor/native execution, numerical full-N work, or adoption is performed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
DOSSIER=ROOT/'queue/standing-fit-state/terminal/s4-p16-timing-whole-9000-high-effort-v1/evidence/project'
BUNDLE=ROOT/'results/throughput-20260929/trackS-p16-timing-v1/bundles-v1/whole-standalone-aw16.json'
ROOT_PIN='0011468ec67d7ca7ebb86fac88103fd19ea0207dc75685289da64d508228ea28'
BASE='engine|recurrence|arithmetic|'
LEAF_NAMES=('genefer_crt3_27_mont_pipe.sv','genefer_div_recip_precision.sv',
    'genefer_montgomery_mul27_sparse_pipe.sv','genefer_stream27_blockcarry_lane_localbase_v1.sv',
    'genefer_stream27_blockcarry_small_cell_localbase_v1.sv','genefer_track_a4_setup_v1.sv')

def need(ok,why):
    if not ok:raise ValueError('CRT_CARRY_MAPPING_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def table(raw,first_column,required_columns=()):
    lines=raw.decode().splitlines();header=None;rows=[];seen=False
    for lineno,line in enumerate(lines,1):
        if not line.startswith(';'):
            if seen:break
            continue
        cells=[x.strip() for x in line.split(';')[1:-1]]
        if header is None:
            if cells and cells[0]==first_column and all(k in cells for k in required_columns):header=cells
            continue
        if len(cells)==len(header):
            rows.append(dict(zip(header,cells),_line=lineno));seen=True
    need(header is not None and rows,'REPORT_TABLE:'+first_column)
    return rows
def metric(row,name,own=False):
    text=row[name];match=re.fullmatch(r'([\d.]+)(?: \(([\d.]+)\))?',text)
    need(match is not None,'TYPED_HIERARCHY_METRIC:'+name)
    return float(match.group(2 if own else 1) or match.group(1))
def aggregate(rows):
    names=dict(needed_ALM='ALMs needed [=A-B+C]',placed_ALM='[A] ALMs used in final placement',
        registers='Dedicated Logic Registers',DSP_needed='DSP Blocks needed [=A-B]',
        DSP_physical='[A] DSP Blocks used in final placement',M20K='M20Ks')
    return {key:round(sum(metric(r,name) for r in rows),1) for key,name in names.items()}

def analyse():
    bundle_raw=BUNDLE.read_bytes();bundle=json.loads(bundle_raw)
    need(len(bundle['rtl_sources'])==64 and sha(bundle['files'][bundle['top']+'.sv'].encode())==ROOT_PIN,'EXACT_TIMING7_ROOT64')
    for name,text in bundle['files'].items():need((DOSSIER/'rtl'/name).read_bytes()==text.encode(),'CAPTURED_RTL:'+name)
    fit_raw=(DOSSIER/'output_files/probe.fit.rpt').read_bytes()
    syn_raw=(DOSSIER/'output_files/probe.syn.rpt').read_bytes()
    hierarchy=table(fit_raw,'Compilation Hierarchy Node')
    by_name={r['Full Hierarchy Name']:r for r in hierarchy}
    need(len(by_name)==len(hierarchy),'UNIQUE_HIERARCHY')
    carry=[by_name[BASE+f'arithmetic[{i}].carry'] for i in range(16)]
    crt=[by_name[BASE+f'arithmetic[{i}].crt'] for i in range(16)]
    div77=[by_name[BASE+f'arithmetic[{i}].carry|split_first'] for i in range(16)]
    div47=[by_name[BASE+f'arithmetic[{i}].carry|split_second'] for i in range(16)]
    mont=[by_name[BASE+f'arithmetic[{i}].crt|{name}'] for i in range(16) for name in ('mont_a3','mont_b3','mont_t2')]
    p3_mont=[r for r in mont if r['Full Hierarchy Name'].endswith(('mont_a3','mont_b3'))]
    fields=[by_name[BASE+f'field{i}'] for i in range(3)]
    setup=by_name[BASE+'shared_setup'];whole=by_name['|']
    # Carry/CRT/fields/setup are disjoint sibling attribution. Divider and Mont
    # detail overlaps their parents and is never added a second time.
    groups={name:aggregate(rows) for name,rows in
        (('carry16',carry),('crt16',crt),('div77_16_overlap',div77),('div47_16_overlap',div47),
         ('crt_mont48_overlap',mont),('crt_P3_mont32_overlap',p3_mont),
         ('fields3',fields),('shared_setup',[setup]),('whole',[whole]))}
    for key in ('DSP_needed','DSP_physical'):
        need(sum(groups[n][key] for n in ('carry16','crt16','fields3','shared_setup'))==groups['whole'][key],
            'DISJOINT_DSP_CLOSURE:'+key)
    multipliers=table(syn_raw,'Multiplier Name')
    selected=[r for r in multipliers if r['Multiplier Name'].startswith(BASE) and
        any(tag in r['Multiplier Name'] for tag in ('.carry|','.crt|','|shared_setup|'))]
    need(selected,'ALL_SHARED_MULTIPLIERS_PRESENT')
    targets=dict(Counter(r['Target'] for r in selected))
    need(set(targets)<= {'dsp','decomposed into smaller multipliers'},'UNEXPECTED_MULTIPLIER_TARGET:'+str(targets))
    packing=table(fit_raw,'Name',('AX/CoefSelA','Output Register','Mode'))
    packing_selected=[r for r in packing if r['Name'].startswith(BASE) and
        any(tag in r['Name'] for tag in ('.carry|','.crt|','|shared_setup|'))]
    need(len(packing_selected)==groups['carry16']['DSP_physical']+groups['crt16']['DSP_physical']+
         groups['shared_setup']['DSP_physical'],'FINAL_PACKING_SHARED_COUNT')
    lane0_mult=[{key:r[key] for key in ('Multiplier Name','Input A Width','Input B Width','Output O Width','Target','Reason','_line')}
        for r in selected if 'arithmetic[0].' in r['Multiplier Name'] or '|shared_setup|' in r['Multiplier Name']]
    lane0_packing=[dict(name=r['Name'],mode=r['Mode'],output_register=r['Output Register'],line=r['_line'])
        for r in packing_selected if 'arithmetic[0].' in r['Name'] or '|shared_setup|' in r['Name']]
    N,P,b=65536,16,1000000000
    K=2*N+24*P
    A=2*((N+3*P)*(b-1)**2+4*P*(b-1)*K+P*K*K)
    modulus=104857601*69206017*67239937
    need(A<2**77 and modulus//2<2**78,'SCALAR_COEFFICIENT_BOUNDS')
    m_max=2**32-1
    bounds={str(prime):dict(product_max=m_max*prime,bits=(m_max*prime).bit_length(),
        sparse_terms=[0,26,21 if prime==69206017 else 17]) for prime in (69206017,67239937)}
    need(all(v['bits']<=59 for v in bounds.values()),'EXACT_REDC_PRODUCT59')
    return dict(status='DIAGNOSED_existing_reports_no_RTL_or_fit',candidate_root_sha256=ROOT_PIN,
        source=dict(bundle=str(BUNDLE.relative_to(ROOT)),bundle_sha256=sha(bundle_raw),
            fit=str((DOSSIER/'output_files/probe.fit.rpt').relative_to(ROOT)),fit_sha256=sha(fit_raw),
            syn=str((DOSSIER/'output_files/probe.syn.rpt').relative_to(ROOT)),syn_sha256=sha(syn_raw),
            leaves={n:sha((DOSSIER/'rtl'/n).read_bytes()) for n in LEAF_NAMES}),
        hierarchy=groups,shared_plus_CRT_needed_ALM=round(groups['carry16']['needed_ALM']+groups['crt16']['needed_ALM'],1),
        inferred_multiplication_targets=targets,explicit_logic_targeted_multipliers=[],
        multiplier_report_scope='Logical synthesis operators, including decomposed children; NOT a physical-DSP count. Final packing/resources close separately.',
        shared_physical_DSP_packing_rows=len(packing_selected),lane0_and_setup_multiplier_rows=lane0_mult,
        lane0_and_setup_final_DSP_rows=lane0_packing,
        precision=dict(max_legal_coefficient_magnitude=A,magnitude_bits=A.bit_length(),
            canonical_CRT_magnitude_max=modulus//2,canonical_CRT_signed_bits=79,
            note='78 signed bits suffice for admitted A;79 preserve all canonical CRT centered values. Narrowing fault-observable raw inputs must retain range guards. Width work belongs to merged.'),
        fabric_reduction=dict(leaf='genefer_montgomery_mul27_sparse_pipe.sv',
            operations='m_s2=lo-(lo<<26)-(lo<<S) mod2^32;mp_s3=m+(m<<26)+(m<<S), used high[58:32]',
            rationale='Explicit exact sparse constant products use fabric shifts/adders; they are not missing reciprocal-product DSP mappings.',
            P2_P3_product_bounds=bounds,CRT_Mont_cells=48,
            total_CRT_Mont_needed_ALM_upper_bound_for_any_saving=groups['crt_mont48_overlap']['needed_ALM']),
        private_hypothesis=dict(name='CRT-P3-only DSP mapping of sparse m*P high-product',
            scope='Private leaf bound only to32 CRT P3 mont_a3/mont_b3 consumers. P2mont_t2 and all original field/general Mont remain unchanged.',
            proposed_exact_expression='mp_s3 <= 59\'(m_s2)*59\'(P); preserve same E3/II1, validity/reset/CE/output holds.',
            precision='m unsigned32;P unsigned27;full59 exact then high27. No quotient/base truncation, new reciprocal precision or arithmetic profile.',
            conservative_extra_DSP=64,projected_physical_DSP_if_all_added=1382,projected_needed_DSP_if_all_added=1364,
            actual_device_DSP_capacity=1518,planning_DSP_target=1400,
            targeted_Mont32_needed_ALM_upper_bound=groups['crt_P3_mont32_overlap']['needed_ALM'],
            rejected_wider_hypothesis='All48CRT cells would add96physicalDSP:1414 exceeds conservative1400planning by14. Initial unpublished analysis retained separately; no source/fit experiment ran.',
            savings='UNKNOWN: sparse fabric adders are already cheap; total32-cell ALM attribution is an upper bound, not a forecast. No newRTL/fit until core seam and range rationale accepted.',
            risks='Constant auto-folding may retain fabric; DSP decomposition/reconstruction/reset controls can worsen LAB/timing. Preserve same-edge owner/range faults and publication.'),
        no_native_or_vendor_execution=True,no_full_N_numeric_computation=True,promotion_allowed=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_OUTPUT')
    result=analyse();out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({key:result[key] for key in ('status','hierarchy','inferred_multiplication_targets','shared_physical_DSP_packing_rows')},indent=2))
