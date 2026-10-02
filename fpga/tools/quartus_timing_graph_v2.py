"""Bounded native timing-graph parser. Never grants cross-block/fit admission."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

FPGA = Path(__file__).resolve().parents[1]
SCRIPT = FPGA/'synthesis/capture_timing_graph_v2.tcl'
base_spec = importlib.util.spec_from_file_location('prefit_graph_base', FPGA/'tools/quartus_prefit_native_v3.py')
base = importlib.util.module_from_spec(base_spec); base_spec.loader.exec_module(base)
identities = base.identities
sha = base.sha


def native_argv(mode, bin_directory, project, revision, output, design_sha256, clock=None):
    if mode != 'graph' or clock not in ('synthesized', 'final') or not re.fullmatch('[0-9a-f]{64}', design_sha256):
        raise ValueError('exact graph mode/snapshot/design required')
    return [str(Path(bin_directory)/'quartus_sta'), '-t', str(SCRIPT), str(project), revision,
            str(output), design_sha256, clock]


def parse(log, report, design, snapshot, returncode):
    blockers = base.native_errors(log, returncode)
    lines = report.splitlines()
    rows = [line.split('\t') for line in lines]
    if not rows or rows[0] != ['QUARTUS_NODE_EDGE_V1', snapshot, design]:
        blockers.append('native_graph_header_identity')
    markers = base.markers(log, 'NODE_GRAPH')
    if [r for r in markers if r[0] == 'IDENTITY'] != [['IDENTITY', design, snapshot]] or any(r[0] == 'FAILED' for r in markers):
        blockers.append('native_graph_identity_or_failure')
    nodes, edges, registers, keepers, queries = {}, {}, [], [], {}
    begin, end, options = [], [], []
    for row in rows[1:]:
        try:
            tag = row[0]
            if tag == 'NODE' and len(row) == 4:
                if row[1] in nodes or row[2] not in ('reg', 'port', 'pin', 'net', 'comb'):
                    raise ValueError('node')
                name = bytes.fromhex(row[3]).decode('utf-8')
                nodes[row[1]] = dict(type=row[2], name=name)
            elif tag == 'EDGE' and len(row) == 6:
                if row[1] in edges or row[4] not in ('synchronous', 'asynchronous', 'clock', 'combinational') or row[5] not in ('0', '1'):
                    raise ValueError('edge')
                edges[row[1]] = dict(src=row[2], dst=row[3], type=row[4], is_disabled=row[5] == '1')
            elif tag in ('REGISTER', 'KEEPER') and len(row) == 2:
                (registers if tag == 'REGISTER' else keepers).append(row[1])
            elif tag == 'QUERY' and len(row) == 4:
                key = (row[1], row[2]); count = int(row[3])
                if key in queries or row[2] not in ('fanout_edges', 'fanout_synch_edges', 'fanout_asynch_edges', 'fanout_clock_edges') or count < 0:
                    raise ValueError('query')
                queries[key] = count
            elif tag == 'BEGIN' and len(row) == 4:
                begin.append(tuple(map(int, row[1:])))
            elif tag == 'END' and len(row) == 4:
                end.append(tuple(map(int, row[1:])))
            elif tag == 'OPTIONS':
                options.append(row[1:])
            else:
                raise ValueError('unknown or malformed row')
        except (ValueError, UnicodeDecodeError):
            blockers.append('malformed_native_graph_row')
    if len(begin) != 1 or len(end) != 1 or not rows or rows[-1][0] != 'END' or end != [(len(nodes), len(edges), 0)]:
        blockers.append('missing_incomplete_or_duplicate_graph_counts')
    if len(options) != 1 or options[0] != ['get_nodes:*:include_duplicates', 'fanout_edges,fanout_synch_edges,fanout_asynch_edges,fanout_clock_edges', 'read_sdc:unchanged', 'node_cap:250000', 'edge_cap:1000000']:
        blockers.append('wrong_graph_capture_options')
    if begin != [(len(nodes), len(registers), len(keepers))] or not nodes or not registers or len(nodes) > 250000 or len(edges) > 1000000:
        blockers.append('enumeration_count_or_cap_mismatch')
    if [row for row in markers if row[0] == 'COLLECTION_COUNT'] != [
            ['COLLECTION_COUNT', 'nodes', str(len(nodes))],
            ['COLLECTION_COUNT', 'registers', str(len(registers))],
            ['COLLECTION_COUNT', 'keepers', str(len(keepers))]]:
        blockers.append('native_collection_counts_missing_or_inconsistent')
    if len(set(registers)) != len(registers) or len(set(keepers)) != len(keepers):
        blockers.append('duplicate_sequential_set_id')
    expected_queries = {(node, query) for node in nodes for query in ('fanout_edges', 'fanout_synch_edges', 'fanout_asynch_edges', 'fanout_clock_edges')}
    if set(queries) != expected_queries or sum(queries.values()) < len(edges):
        blockers.append('incomplete_query_collections')
    missing = sorted(({edge[key] for edge in edges.values() for key in ('src', 'dst')} | set(registers) | set(keepers))-set(nodes))
    if missing:
        blockers.append('native_graph_endpoint_closure_missing')
    if [r for r in markers if r[0] == 'COMPLETE'] != [['COMPLETE', str(len(nodes)), str(len(edges))]]:
        blockers.append('native_graph_completion_missing')
    regtypes = {node for node, entry in nodes.items() if entry['type'] == 'reg'}
    discrepancy = dict(register_not_node_reg=sorted(set(registers)-regtypes), node_reg_not_register=sorted(regtypes-set(registers)))
    return dict(complete=not blockers, blockers=blockers, snapshot=snapshot,
                nodes=nodes, edges=edges, registers=registers, keepers=keepers,
                collection_query_counts={query: sum(count for (_, kind), count in queries.items() if kind == query) for query in ('fanout_edges', 'fanout_synch_edges', 'fanout_asynch_edges', 'fanout_clock_edges')},
                node_type_counts={kind: sum(n['type'] == kind for n in nodes.values()) for kind in ('reg', 'port', 'pin', 'net', 'comb')},
                edge_type_counts={kind: sum(e['type'] == kind for e in edges.values()) for kind in ('synchronous', 'asynchronous', 'clock', 'combinational')},
                disabled_edges=sum(e['is_disabled'] for e in edges.values()), missing_endpoint_ids=missing,
                register_membership_discrepancy=discrepancy,
                cross_block_coverage_complete=False, fit_allowed=False,
                limitation='Native enumerated timing-graph closure only. No keeper==register assumption, stage-count proof, complete HDL graph or declared-interface fit admission.')


def receipt(root, specification, log, report, returncode, execution):
    ids = identities(specification)
    raw = {str(path.relative_to(root)): sha(path.read_bytes()) for path in (log, report)}
    context = json.loads(execution.read_text())
    if (context.get('schema') != 'quartus-prefit-execution-v1' or context.get('platform') != 'Linux' or
            any(context.get(k) != v for k, v in ids.items()) or context.get('helper_sha256') != sha(Path(__file__).read_bytes()) or
            context.get('native_script_sha256') != sha(SCRIPT.read_bytes()) or context.get('tool_sha256') != specification['vendor_tool_sha256'] or
            context.get('returncode') != returncode or context.get('owner_admission_passed') is not True or context.get('raw_report_sha256') != raw or
            context.get('original_tree_unchanged') is not True or not context.get('database_before_sha256') or
            context['database_before_sha256'] != context.get('database_after_sha256')):
        raise ValueError('exact admitted graph execution source/tool/DB/raw identity required')
    for key, expected in (('source', specification['sources']), ('settings', specification['settings'])):
        if context.get(key+'_before_sha256') != expected or context.get(key+'_after_sha256') != expected:
            raise ValueError('graph input drift')
    graph = parse(log.read_text(), report.read_text(), ids['design_sha256'], specification['graph_snapshot'], returncode)
    graph['derived_output_identity_policy'] = 'Only exact observed report.cmp/report.taw and ss100slow I/O cache model/payload pairs are pinned separately; all other DB files and the original full tree are immutable.'
    graph['derived_output_before'] = context.get('derived_output_before', {})
    graph['derived_output_after'] = context.get('derived_output_after', {})
    graph['derived_output_schema_evidence_sha256'] = context.get('derived_output_schema_evidence_sha256')
    return dict(schema='quartus-native-node-edge-evidence-v1', **ids, scope=specification['scope'],
                helper_sha256=sha(Path(__file__).read_bytes()), native_script_sha256=sha(SCRIPT.read_bytes()),
                tool_sha256=specification['vendor_tool_sha256'], raw_report_sha256={**raw, str(execution.relative_to(root)): sha(execution.read_bytes())},
                native_execution_identity_verified=True, native_execution_context=dict(path=str(execution.relative_to(root)), sha256=sha(execution.read_bytes())),
                graph=graph, cross_block_coverage_complete=False, fit_allowed=False, promotion_allowed=False)
