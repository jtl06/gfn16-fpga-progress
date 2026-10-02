"""Source-matched original A-next full-square scalar projection, not a PRP run."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COUNT=1911814
REPORT='queue/evidence/anext-soak-continuous-aw16-q1-v2/attempt-0/collected/output/native/report.json'
REPORT_SHA='d0accac2acef9bdb943e024dfd74c24d325b42b7e2238ce4a31d0506b3598c84'
AUDIT='results/throughput-20260929/anext-9668-12068-timing-audit-v1/interpretation-v1.json'
AUDIT_SHA='42e49fa9815f104dbe5dd481c4ec1819213090970c0a129ed0e6b2d24c23e1ae'
PHYSICAL='artifacts/anext-9668ps-f16-plain-v2/project/manifest.json'
PHYSICAL_SHA='41b2fe9d4eb5648f4728ff89cd2ce5a0c43242d6ef6bc0b6b8818f38b9c37742'
SAMPLE='results/throughput-20260929/core27-t5b-promotion-readiness-v3.json'
SAMPLE_SHA='11960a89c87402455e7f08e811655a4a350050d12e02a5357e1a6f85839d203a'

def need(ok,message):
    if not ok:raise ValueError(message)
def pinned(path,pin):
    data=(ROOT/path).read_bytes();need(hashlib.sha256(data).hexdigest()==pin,'projection evidence pin '+path);return json.loads(data)

def calculate(count=COUNT,period_ps=12068):
    need(type(count) is int and count>0 and type(period_ps) is int and period_ps>0,'positive exact projection arguments')
    phase=dict(ntt=count*17709,post_ntt=count*4158,cold_prefill=4106,cold_root_load=9,
               backend_control=7+(count-1)*5)
    clocks=sum(phase.values());command=clocks+2*count
    need(clocks==25989+(count-1)*21872,'complete first-cold/cache-warm ledger')
    seconds=lambda cycles,ps:str(Decimal(cycles)*Decimal(ps)/Decimal(10**12))
    t5b=41674+(count-1)*28826
    return dict(status='source_matched_fixed_schedule_compute_projection_not_full_PRP',
        sample=dict(n=65536,base=604832956,square_conditional_double_operations=count,
                    exponent_bit_count_reused=True,exact_sample_popcount_not_recomputed=True),
        selected_period_ps=period_ps,selected_frequency_mhz=str(Decimal(10**6)/Decimal(period_ps)),
        backend_cycles_by_phase=phase,backend_cycles=clocks,backend_seconds=seconds(clocks,period_ps),
        command_square_edge_overhead=2*count,command_square_latency_cycles=command,
        command_latency_sum_seconds=seconds(command,period_ps),
        parent_t5b_backend_cycles=t5b,parent_t5b_backend_seconds=seconds(t5b,9668),
        cold_operations=1,warm_operations=count-1,root_loads=1,root_cache_hits=count-1,
        recurrence_seed_cycles=0,conditional_double_extra_cycles=0,
        double_scope='Each operation is square with optional post-CRT integer doubling at the same fixed phase latency. No separate multiplication/operation charge and no F2 recurrence credit.',
        initial_host_digit_load_commands=65536,initial_host_setup_load_seconds_included=False,
        host_scope='Command latency sum adds measured two-edge square response overhead only. Initial configure/full load, intercommand/response hold gaps and final canonical readback remain excluded, not assumed zero.',
        checkpoint_scope='No intermediate checkpoint in this cached-chain projection. Native1000 diagnostic has nine read-induced extra cold-prefill transitions; those measured counts are not this warm-throughput schedule.',
        same_base_native_chain_exists=True,measured_exact_sample_PRP=False,FPGA_board_runtime_measured=False,
        independent_audit_review_required=True,advisor_verification_required=True,promotion_allowed=False)

def project():
    native=pinned(REPORT,REPORT_SHA);audit=pinned(AUDIT,AUDIT_SHA);physical=pinned(PHYSICAL,PHYSICAL_SHA)
    need(audit['source_manifest_sha256']==PHYSICAL_SHA and audit['selected_period_ns']==12.068 and
         audit['selected_measured_tns_ns']==0 and audit['selected_measured_failing_endpoints']==0,'selected native audit scope')
    need(all(native['sources']['rtl/kernel/'+name]==pin for name,pin in physical['source_sha256'].items()),'same physical/native30SV')
    v=native['validations']['anext-soak-chunk00'];rows=v['native_anext_metrics']['metrics']
    need(len(rows)==1000 and {r['bit'] for r in rows}=={0,1},'both optional-double settings observed')
    for i,r in enumerate(rows):
        cold=i%100==0;load=i==0
        expected=dict(ntt=17709,post=4158,prefill=4106 if cold else 0,roots=9 if load else 0,
                      control=7 if cold else 5,cycles=25989 if load else 25980 if cold else 21872)
        need(all(type(r[k]) is int and r[k]==x for k,x in expected.items()),'measured source-matched phase calendar')
    donor=v['donor_reference_validation'];need(donor['operations']==1000 and donor['doubles']==488 and donor['cycles']==21913089 and donor['independent_gmpy2_boundary_replay'] is True,'actual fullchain reference evidence')
    # This scalar descriptor is inherited, not a new enormous exponent or PRP.
    sample=pinned(SAMPLE,SAMPLE_SHA)['projection']
    need((sample['n'],sample['base'],sample['exponent_bits_from_frozen_reference'])==(65536,604832956,COUNT),'frozen promoted sample descriptor')
    oracle_path='artifacts/anext-soak-continuous-bound-role-v1/source/fpga/donor/reference/continuous.json'
    oracle=pinned(oracle_path,native['sources']['donor/reference/continuous.json'])
    need((oracle['plan']['profile']['n'],oracle['plan']['profile']['base'])==(65536,604832956),'native same-base chain, not full sample PRP')
    result=calculate();result['evidence_pins']=dict(native_report=REPORT_SHA,physical_manifest=PHYSICAL_SHA,
        audit_interpretation=AUDIT_SHA,audit_terminal=audit['terminal_receipt_sha256'],
        original_aw16_independent='1029d023b6633432daa76e46961ab9b1619a18929a747931eadc7c71d7537ea0',
        valid_base_E2E_independent='d648650ba55db469d47068328dd813abd66195a38056d200fcbab2ebeb760231',
        continuous_owner='277648ebebd9d478e707319928a351dcd0a19a1b7456c06e589a067cac5d40cf',sample_descriptor=SAMPLE_SHA)
    result['audit_limitations']=audit['limitations'];result['local_full_N_integer_computations']=0
    return result

if __name__=='__main__':print(json.dumps(project(),indent=2))
