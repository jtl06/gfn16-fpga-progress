"""Strict small-N A-next values/phase contract for the shared native runner.

The unchanged command harness retains its historical A4_CORE output prefixes;
the native manifest binds the new top. No parent seed/profile count is reused.
"""
import hashlib
from fpga.reference.track_a4_core_output_v2 import PROFILES
from fpga.reference.track_a4_core_aw5_output_v1 import FIELDS,need,tokens
from fpga.reference.anext_point_contract_v1 import schedule


def validate(stdout_text,stderr_text,returncode_int,config_dict,assets_text_map):
    need(type(returncode_int) is int and returncode_int==0 and stderr_text=='','native success/empty stderr')
    need(set(config_dict)=={'mode','aw'} and config_dict['mode']=='normal' and config_dict['aw'] in (5,8),'exact small geometry')
    need(set(assets_text_map)=={'vectors'},'exact vectors asset')
    aw=config_dict['aw'];vectors=assets_text_map['vectors'];profile=PROFILES[aw]
    need(hashlib.sha256(vectors.encode()).hexdigest()==profile['sha'],'frozen independent vector identity')
    lines=vectors.splitlines();need(lines[0]==f'A4CORE1 {aw} {profile["commands"]}','vector header')
    commands=[list(map(int,line.split())) for line in lines[1:]]
    need(len(commands)==profile['commands'] and all(len(row)==10 for row in commands),'complete vector rows')
    identities=[dict(index=i,cold=row[8],load=row[9],double=row[4]) for i,row in enumerate(commands) if row[0]==5]
    lines=stdout_text.splitlines();need(len(lines)==15 and stdout_text.endswith('\n'),'exact fourteen rows/footer')
    rows=[tokens(line,'A4_CORE_SQUARE',FIELDS) for line in lines[:-1]]
    counts=dict(aw=aw,commands=profile['commands'],squares=14,cold_squares=8,profile_loads=4,
        readbacks=profile['readbacks'],hold_checks=profile['holds'])
    footer=tokens(lines[-1],'A4_CORE_PASS',tuple(counts)+('ticks','max_latency'))
    need(all(footer[k]==v for k,v in counts.items()),'complete fixed coverage')
    budget=schedule(aw)
    for row,identity in zip(rows,identities):
        need({key:row[key] for key in identity}==identity,'ordered vector-bound operation')
        total=budget['warm_backend']+(budget['cold_cached_backend']-budget['warm_backend'])*row['cold']+9*row['load']
        expected=dict(ntt=budget['ntt_controller_cycles'],seed=0,root=9*row['load'],
            prefill=budget['cold_prefill_child_cycles']*row['cold'],post=budget['post_child_cycles'],total=total,latency=total+2)
        need(all(row[key]==value for key,value in expected.items()),'A-next source-bound phase mismatch')
        need(0<row['latency']<=footer['max_latency'],'positive bounded measured latency')
    need(footer['ticks']>sum(row['latency'] for row in rows),'host traffic and hold ticks retained')
    return dict(status='PASS_expected_contracts',candidate='A-next-hostcut-v1',aw=aw,metrics=rows,footer=footer,
        vector_sha256=profile['sha'],source_budget_matched=True,promotion_allowed=False,
        scope='Fourteen normal/canonical-readback/held-response squares and one reset; no full fault/PRP/fit qualification.')
