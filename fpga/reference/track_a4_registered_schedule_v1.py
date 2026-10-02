"""r13 source/destination register budget: full-N events, no numeric NTT."""
from fpga.reference.track_a4_blockcarry_model import route_row, schedule


def registered_schedule(n=65536, ntt_cycles=20558):
    old = schedule(n)
    t = n//16
    # Two request registers before RAM, two response registers after RAM.
    request_delay, response_delay, write_delay = 2, 2, 2
    read_extra = request_delay+response_delay
    reads, writes = {}, {}
    for event in old["events"]:
        edge = event["edge"]
        if event["read_offset"] is not None:
            reads[edge+request_delay] = event["read_offset"]
        value = event["write_offset"] if event["write_offset"] is not None else event["patch_offset"]
        if value is not None:
            writes[edge+read_extra+write_delay] = value
    pairs = overlaps = 0
    for edge in reads.keys() & writes.keys():
        r, w = dict(route_row(n, reads[edge])), dict(route_row(n, writes[edge]))
        pairs += len(r.keys() & w.keys())
        overlaps += 1
        assert all(r[bank] != w[bank] for bank in r.keys() & w.keys())
    internal_done = old["check_edge"]+read_extra
    final_write = max(writes)
    # POST_WAIT observes registered post.done next edge; DRAIN observes quiet
    # only after final acceptance; CHECK observes the destination error tail.
    backend_done = max(internal_done+2, final_write+1)+1
    patch_launch = old["patch_launch_edge"]+read_extra
    boundary_commit = old["boundary_pair_ready_edge"]+1+read_extra+2
    assert boundary_commit < patch_launch
    warm_backend = 2+ntt_cycles+backend_done
    return dict(n=n,block_length=t,source_read_edge=0,ram_first_read_edge=2,
        crt_consume_edge=5,first_digit_edge=46,first_image_write_edge=49,
        first_ram_write_edge=54,ram_to_ram_displacement=52,
        boundary_commit_edge=boundary_commit,patch_launch_edge=patch_launch,
        last_normal_ram_write_edge=t+53,patch_ram_write_edges=[t+61,t+62],
        internal_post_clocks=internal_done+1,backend_done_from_post_start=backend_done,
        post_through_backend_done_clocks=backend_done+1,
        cold_prefill_child_cycles=t+10,cold_backend_penalty=t+12,
        warm_backend_cycles=warm_backend,warm_host_latency=warm_backend+2,
        simultaneous_read_write_edges=overlaps,simultaneous_bank_pairs=pairs,
        same_address_collisions=0,read_edges=reads,write_edges=writes,
        status="source-derived budget, pending native confirmation")
