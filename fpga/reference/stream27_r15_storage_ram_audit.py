"""Read-only exact FIELD100 source/represented-storage bill, no fit forecast."""
import hashlib
import json
from pathlib import Path
from fpga.reference import stream27_r15_storage_ram_bind as binder

ROOT=binder.ROOT
REPORT=ROOT/'queue/standing-fit-state/terminal/s4-p16-c2-protected-field100-whole-12000-aws12-seed2-v1/evidence/project/output_files'


def rows(path, needles):
    return [line for line in path.read_text().splitlines()
            if line.startswith(';') and any(n in line for n in needles)]


def report():
    syn,fit=REPORT/'probe.syn.rpt',REPORT/'probe.fit.rpt'
    ram=[line for line in rows(fit,['; engine|arithmetic|crt_tag_rtl_0|auto_generated|altera_syncram4|altsyncram5|ALTSYNCRAM '])
         if len(line.split(';'))>2 and line.split(';')[2].strip()=='M20K']
    binder.need(len(ram)==1 and '; M20K ;' in ram[0], 'ACTUAL_METADATA_M20K')
    entities=rows(syn,['; engine|arithmetic|arithmetic[0].crt ', '; engine|arithmetic|crt_tag_rtl_0 '])
    # Hierarchy paths appear in table columns, not just printed instance labels.
    binder.need(any('1808 (1247)' in line and 'genefer_crt3_27_mont_pipe' in line for line in entities),
                'ACTUAL_CRT_LOCAL_REGISTERS')
    return dict(schema='r15-field100-represented-storage-audit-v1',
        exact_parent='protected FIELD100 AWS seed2',
        reports={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (syn,fit)},
        metadata=dict(declared_tag_double_width=38,declared_depth=16,
            actual_inferred_interior_width=13,actual_altshift_tap_distance=12,
            actual_memory_bits=208,actual_M20K=1,actual_local_synthesis_registers=8,
            already_RAM=True,unimplemented_523FF_saving=False,raw_mapping_row=ram[0]),
        numeric=dict(instances=16,one_CRT_synthesis_registers_inclusive=1808,
            one_CRT_synthesis_registers_local=1247,one_CRT_block_memory_bits=0,
            register_delay_targets=[dict(name='r1 tail',width=27,delay=6,stage0_preserved=True),
                                    dict(name='d3',width=27,delay=5),
                                    dict(name='x12',width=53,delay=6)],
            raw_entity_rows=entities,
            optimizer_endpoint_widths_not_individually_measured=True,
            proposed_declared_register_reduction_upper_bound=7840,
            proposed_new_MLAB_mapping_not_yet_measured=True),
        exclusions=['Existing P2/packed/storage2 gains are not counted again',
                    'Term-payload OLD_DATA/collision path remains excluded',
                    'No whole LAB/FF/clock saving extrapolated from source declarations',
                    'No owner,validity,reset,fault or public schedule removal'],
        actual_new_component_or_whole_saving=None,promotion_allowed=False)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();binder.need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_AUDIT_OUTPUT')
    value=report();out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps(dict(path=str(out),metadata_parent_M20K=1,numeric_existing_memory_bits=0,
                         mapped_new_saving=None)))
