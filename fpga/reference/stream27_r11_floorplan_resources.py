"""Parse captured exact R11 SYN hierarchy rows, never estimate LAB regions."""
import hashlib
import json
from pathlib import Path
from fpga.reference.stream27_r11_floorplan_feasibility import audit

ROOT=Path(__file__).resolve().parents[1]
CAPTURE=ROOT/'results/throughput-20260929/trackS-r11-floorplan-feasibility-v1/installed-r11-resource-rows.json'
SYN_SHA='61393c591a196ea7a29afca8231ae34acb635fa513e7ff5f8e2df6b3989f8828'


def resources():
    raw=CAPTURE.read_bytes();capture=json.loads(raw)
    syn=capture['reports']['probe.syn.rpt'];assert syn['sha256']==SYN_SHA
    rows=syn['matched_rows'];assert len(rows)==36
    header=[v.strip() for v in rows[0].split(';')]
    expected=['Compilation Hierarchy Node','Combinational ALUTs','Dedicated Logic Registers',
              'Block Memory Bits','DSP Blocks','Pins','Virtual Pins','IOPLLs','Max Depth',
              'Full Hierarchy Name','Entity Name','Library Name']
    assert header[1:13]==expected
    graph=audit();parsed={}
    for row in rows[1:]:
        fields=[v.strip() for v in row.split(';')]
        assert len(fields)==14 and fields[10] not in parsed
        def number(index):return int(fields[index].split()[0])
        parsed[fields[10]]=dict(hierarchy=fields[10],entity=fields[11],
            combinational_aluts=number(2),dedicated_logic_registers=number(3),
            block_memory_bits=number(4),dsp_blocks=number(5))
    expected_nodes={f['path'] for f in graph['three_field_instances']}|set(graph['central_instance_members'])
    assert set(parsed)==expected_nodes
    fields=[parsed[f['path']] for f in graph['three_field_instances']]
    spine=[parsed[p] for p in graph['central_instance_members']]
    metrics=('combinational_aluts','dedicated_logic_registers','block_memory_bits','dsp_blocks')
    total=lambda nodes:{metric:sum(row[metric] for row in nodes) for metric in metrics}
    return dict(status='NATIVE_EXISTING_SYN_ROWS_CONSUMED_NOT_REGION_LEGALITY',
        capture_sha256=hashlib.sha256(raw).hexdigest(),syn_report_sha256=SYN_SHA,
        source_graph_matches_all35_nodes=True,field_regions=fields,
        central32_instance_subtotals=total(spine),disjoint_selected35_node_subtotals=total(fields+spine),
        plan_report_sha256=capture['reports']['probe.fit.plan.rpt']['sha256'],
        plan_matching_resource_rows=len(capture['reports']['probe.fit.plan.rpt']['matched_rows']),
        stage='Synthesis hierarchical inclusive counts (leading number), not own-node parentheses; selected nodes disjoint.',
        omitted='Shared setup, root-level transport/control/profile registers, host memories/controller and other outside logic; not whole totals.',
        limits='Do NOT convert ALUTs/FF to LABs, divide memorybits byM20K capacity, multiply field fit, or treat SYN DSPcounts as placed hardblock counts.',
        floorplan_warning='Central spine has substantial multiplier/divider resources, not a thin logic-only center strip. Exact mapped DSP/RAM columns and retained transport register collection still required.',
        device_spatial_coordinates=None,region_capacity_proven=False,
        installed_options_validated=False,DRC_smoke_pass=False,optional_ticket_submitted=False,
        baseline_gate=False,physical_benefit=None)


if __name__=='__main__':print(json.dumps(resources(),indent=2))
