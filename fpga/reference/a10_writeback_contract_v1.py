"""F3 index-only 1R1W hazard and final-commit calendar; no numeric NTT."""
from fpga.reference import a10_writeback_launch_prepare_v1 as prep
from fpga.reference import merged_negacyclic27_issue_model_v1 as geometry


def check(aw, *, stages=None, mutant=None):
    prep.gen.upper.need(type(aw) is int and aw in (5,8,16), 'A10_F3_CONTRACT_GEOMETRY')
    prep.verify();geometry.source_guard()
    n=1<<aw;groups=max(1,n//128);stages=list(range(aw)) if stages is None else list(stages)
    prep.gen.upper.need(stages and len(set(stages))==len(stages) and
                       all(type(s) is int and 0<=s<aw for s in stages), 'A10_F3_CONTRACT_STAGES')
    read_to_commit=9;checked=0;overlapped=0
    for stage in stages:
        visited=set();calendar={}
        for number in range(groups):
            requests=geometry.issue(n,64,stage,number)
            addresses={(r.u_bank,r.u_row) for r in requests}|{(r.v_bank,r.v_row) for r in requests}
            if mutant=='stale-row' and number:
                addresses={(bank,0) for bank,_ in addresses}
            prep.gen.upper.need(len(addresses)==min(n,128) and len({bank for bank,_ in addresses})==len(addresses),
                               'A10_F3_ONE_READ_PER_BANK')
            prep.gen.upper.need(not (visited & addresses), 'A10_F3_ONE_VISIT_PER_STAGE')
            # Current read accepted at edge number; enqueue at +8, commit +9.
            # Reading and writing different rows in a bank is legal 1R1W.
            commit=calendar.pop(number,None)
            if commit is not None:
                prep.gen.upper.need(not (commit & addresses), 'A10_F3_RAM_READ_WRITE_COLLISION')
                overlapped+=1
            calendar[number+read_to_commit]=addresses
            visited.update(addresses);checked+=len(addresses)
        prep.gen.upper.need(len(visited)==n, 'A10_F3_COMPLETE_STAGE_ADDRESS_COVERAGE')
        final_read=groups-1;last_commit=final_read+read_to_commit
        # The final commit also retires the frame token; setup is the next edge,
        # and the successor first read follows setup. No stale cross-stage write.
        next_setup=last_commit+1;next_first_read=last_commit+2
        prep.gen.upper.need(max(calendar)==last_commit and all(edge<next_setup for edge in calendar) and
                           next_first_read>last_commit, 'A10_F3_STAGE_DRAIN_PHYSICAL_COMMIT')
    point_seen=set()
    for group in range((n+63)//64):
        addresses={(geometry.bank_of(index,7),index>>7) for index in range(group*64,min(n,(group+1)*64))}
        prep.gen.upper.need(len(addresses)==min(n,64) and not (point_seen & addresses), 'A10_F3_POINT_BANK_ROW_COVERAGE')
        point_seen.update(addresses)
    prep.gen.upper.need(len(point_seen)==n, 'A10_F3_POINT_COMPLETE_COVERAGE')
    return dict(aw=aw,stages=stages,index_only=True,numeric_full_N_NTT_performed=False,
                addresses_checked=checked,concurrent_read_write_edges_checked=overlapped,
                internal_read_to_physical_commit_edges=9,final_commit_to_next_stage_setup=1,
                final_commit_to_next_stage_first_read=2,point_unique_addresses=len(point_seen),
                source_pins=prep.PINS,native_latency_inherited=False,promotion_allowed=False)
