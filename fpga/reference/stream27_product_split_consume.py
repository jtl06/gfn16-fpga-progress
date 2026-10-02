"""Compact owner interpretation of the collected scalar packing probe."""
import argparse
import json
from pathlib import Path
import re

CELLS=('split_canonical','parent_canonical','split_lazy','parent_lazy')

def table(text,title,header):
    anchor='; '+title
    if text.count(anchor)!=1:raise ValueError('one native panel: '+title)
    lines=text.split(anchor,1)[1].splitlines();names=None;rows=[]
    for line in lines:
        if not line.startswith(';'):continue
        parts=[s.strip() for s in line.strip(';').split(';')]
        if parts[0]==header:names=parts;continue
        if names is not None and len(parts)==len(names):rows.append(dict(zip(names,parts)))
        elif names is not None and rows:break
    if not rows:raise ValueError('missing native rows: '+title)
    return rows

def number(value):return float(value.split()[0].replace(',',''))

def output_bits(value):
    if value=='unregistered':return 0
    ranges=re.findall(r'\[(\d+)\.\.(\d+)\]',value)
    if not ranges:raise ValueError('explicit native DSP output range: '+value)
    return sum(abs(int(b)-int(a))+1 for a,b in ranges)

def extract(text):
    entities=table(text,'Fitter Resource Utilization by Entity','Compilation Hierarchy Node')
    packing=table(text,'Fixed Point DSP Register Packing Details','Name')
    result={}
    for cell in CELLS:
        rows=[r for r in entities if r['Full Hierarchy Name']==cell+'|core']
        dsp=[r for r in packing if r['Name'].startswith(cell+'|core|')]
        if len(rows)!=1 or len(dsp)!=1:raise ValueError('one independent cell/core/DSP: '+cell)
        row=rows[0];register=dsp[0]['Output Register']
        packed=output_bits(register)
        result[cell]=dict(needed_ALM=number(row['ALMs needed [=A-B+C]']),
            placed_ALM=number(row['[A] ALMs used in final placement']),
            dedicated_fabric_registers=int(number(row['Dedicated Logic Registers'])),
            combinational_ALUTs=int(number(row['Combinational ALUTs'])),
            DSPs_needed=int(number(row['DSP Blocks needed [=A-B]'])),
            DSP_output_register=register,DSP_output_bits=packed)
    result['lazy_delta']={key:result['split_lazy'][key]-result['parent_lazy'][key]
        for key in ('needed_ALM','placed_ALM','dedicated_fabric_registers','combinational_ALUTs','DSPs_needed','DSP_output_bits')}
    result['canonical_delta']={key:result['split_canonical'][key]-result['parent_canonical'][key]
        for key in ('needed_ALM','placed_ALM','dedicated_fabric_registers','combinational_ALUTs','DSPs_needed','DSP_output_bits')}
    result['scope']='Same-layout independent-input scalar comparison only; no per-field multiplier credit, whole-area or clock adoption.'
    return result

def field_extract(text):
    """Count actual native packing rows and leaf-exclusive fabric registers."""
    entities=table(text,'Fitter Resource Utilization by Entity','Compilation Hierarchy Node')
    packing=table(text,'Fixed Point DSP Register Packing Details','Name')
    leaf_rows=[r for r in entities if r['Entity Name'] in
        ('genefer_stream27_product_split_core_v1','genefer_stream27_montgomery_factored_core_v1')]
    if not leaf_rows:raise ValueError('actual factored/split field leaves required')
    counts={}
    for entity in sorted({r['Entity Name'] for r in leaf_rows}):
        rows=[r for r in leaf_rows if r['Entity Name']==entity]
        counts[entity]=dict(instances=len(rows),
            dedicated_fabric_registers=sum(int(number(r['Dedicated Logic Registers'])) for r in rows),
            needed_ALM=round(sum(number(r['ALMs needed [=A-B+C]']) for r in rows),1),
            placed_ALM=round(sum(number(r['[A] ALMs used in final placement']) for r in rows),1))
    return dict(leaf_entities=counts,DSP_rows=len(packing),
        product_s1_DSP_output_rows=sum('product_s1[' in r['Output Register'] for r in packing),
        product_s1_DSP_output_bits=sum(output_bits(r['Output Register']) for r in packing if 'product_s1[' in r['Output Register']),
        parent_ab_s1_DSP_output_rows=sum('ab_s1[' in r['Output Register'] for r in packing),
        parent_ab_s1_DSP_output_bits=sum(output_bits(r['Output Register']) for r in packing if 'ab_s1[' in r['Output Register']),
        unregistered_DSP_output_rows=sum(r['Output Register']=='unregistered' for r in packing),
        scope='Actual field hierarchy/packing; totals are not scaled whole-core area credit.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=Path);p.add_argument('--field',action='store_true')
    a=p.parse_args();print(json.dumps((field_extract if a.field else extract)(a.report.read_text()),indent=2))
