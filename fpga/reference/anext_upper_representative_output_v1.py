"""Scalar recipe identities plus strict A-next phase metrics; no full-N oracle."""
from fpga.reference.track_a4_core_aw5_output_v1 import FIELDS,need,tokens
from fpga.reference.track_a4_representative_recipe_v1 import geometry
from fpga.reference.anext_point_contract_v1 import schedule

def validate(stdout_text,stderr_text,returncode_int,config_dict,assets_text_map):
    need(type(returncode_int) is int and returncode_int==0 and stderr_text=='','native success/empty stderr')
    need(set(config_dict)=={'mode','aw'} and config_dict['mode']=='representative' and config_dict['aw'] in (5,8,16),'exact geometry')
    need(assets_text_map=={},'native closed-form recipe; no substituted vector asset')
    aw=config_dict['aw'];g=geometry(aw);s=schedule(aw);lines=stdout_text.splitlines()
    need(len(lines)==17 and stdout_text.endswith('\n'),'sixteen rows and unique complete footer')
    rows=[tokens(line,'A4_CORE_SQUARE',FIELDS) for line in lines[:-1]]
    counts={k:g[k] for k in ('aw','commands','squares','cold_squares','profile_loads','readbacks','hold_checks')}
    footer=tokens(lines[-1],'A4_CORE_PASS',tuple(counts)+('ticks','max_latency'))
    need(all(footer[k]==v for k,v in counts.items()),'exact representative coverage')
    for row,identity in zip(rows,g['identities']):
        need({k:row[k] for k in identity}==identity,'ordered recipe identity')
        total=s['warm_backend']+(s['cold_cached_backend']-s['warm_backend'])*row['cold']+9*row['load']
        expected=dict(total=total,latency=total+2,ntt=s['ntt_controller_cycles'],seed=0,
                      root=9*row['load'],prefill=s['cold_prefill_child_cycles']*row['cold'],post=s['post_child_cycles'])
        need(all(row[k]==v for k,v in expected.items()),'A-next representative source-bound schedule mismatch')
        need(0<row['latency']<=footer['max_latency'],'measured latency bound')
    need(footer['ticks']>sum(r['latency'] for r in rows),'complete host traffic')
    return dict(status='PASS_expected_contracts',candidate='A-next-upper-v1',aw=aw,metrics=rows,footer=footer,
                source_budget_matched=True,promotion_allowed=False,
                scope='Sixteen deterministic signed monomial/dense squares; eight full readbacks; holds and one reset. No random/full faults/PRP/soak/clock claim.')
