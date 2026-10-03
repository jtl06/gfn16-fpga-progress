"""Additive R9 actual-log binding; ec9 source/model producer stays frozen.

Only normal-full's artifact basename is corrected from the provisional donor
guess to its actual report-bound R9 name. No RTL/native/index/clock changes.
"""
import json
from . import stream27_c2_r9_healthy_sample_join as base

ROOT=base.ROOT
SELF='reference/stream27_c2_r9_healthy_sample_join_v2.py'
BASE_PIN='ec9d8f85c524f57f4128844b15f568739204c98de890380cd6a28b859b337b7e'
INDEX_PIN='3ce202af137753f9be1d258614bc303bf7307e52b8472bf1bc8c5c72115ea473'


def close():
    base.need(base.own.sha((ROOT/base.SELF).read_bytes())==BASE_PIN,'FROZEN_SOURCE_MODEL_PRODUCER')
    base.need(base.own.sha((ROOT/base.PARSERS).read_bytes())==base.PARSERS_PIN,'FROZEN_READ_ONLY_PARSERS')
    b=base.source();raw=(ROOT/base.INDEX).read_bytes()
    base.need(base.own.sha(raw)==INDEX_PIN,'IMMUTABLE_OWN_NUMERICAL_INDEX')
    index=json.loads(raw)
    base.need(index['production']['all55_generated_sha256']==b['generated_sha256'] and
              index['production']['captured_bundle']['sha256']==base.CAPTURE_PIN,'ALL55_OWN_INDEX_CAPTURE')
    jobs=dict(base.JOBS)
    identity,_,prefix=jobs[2]
    jobs[2]=(identity,'normal-full-c2-r9-alone-and-joint.log',prefix)
    refs=[];actual={}
    for count,(identity,name,prefix) in jobs.items():
        ref,report,manifest,native=base.parsers.native_join(identity,b,index)
        footer=base.parsers.read_footer(native,report,name,prefix)
        e=base.validate_footer(footer,count,b['geometry'])
        ref['log_name']=name;ref['log_sha256']=report['artifacts'][name];refs.append(ref)
        actual[str(count)]=dict(calendar=e,joint_cycles=footer['joint_cycles'],joint_squares=2*count,
                               native_total_squares=footer['squares'],native_total_reads=footer['reads'])
    ref,report,manifest,native=base.parsers.native_join(base.WRAP_ID,b,index)
    base.validate_footer(base.parsers.read_footer(native,report,base.WRAP_LOG,'R84_C2_FULL_PASS '),2,b['geometry'])
    base.need('R9_FULL_WRAP_PASS aliases=3 cold_accepts=2 cache_events_per_field=4 reads=393216 masks=1/2/3 '
              'independent_reference=1 real_datapath_edges=1 simulation_only=1\n' in (native/base.WRAP_LOG).read_text(),
              'OWN_FULL_NATIVE_ONE_SHOT_HOST_TIMESTAMP_ALIASES')
    ref['log_name']=base.WRAP_LOG;ref['log_sha256']=report['artifacts'][base.WRAP_LOG];refs.append(ref)
    out=base.source_ledger()
    out.update(status='OWN_SOURCE_NATIVE_CALENDAR_JOIN_PASS_CLOCK_NULL',
        source_model_producer=out['producer'],producer=dict(path=SELF,sha256=base.own.sha((ROOT/SELF).read_bytes())),
        numerical_index=dict(path=base.INDEX,sha256=INDEX_PIN),native_calendars=actual,native_references=refs,
        actual_log_binding_delta=dict(old_guess=base.JOBS[2][1],actual_report_name=jobs[2][1],
            old_model_source_result_preserved=True,no_native_rerun_or_source_change=True),
        accepted_second_cold_edge=8436,healthy_peer_lease_argument=dict(first_peer=4433,correction=8436,
            next_ctx0_feedback=8663,first_auto_boundaries=[12761,16990],no_legal_cold_auto_collision=True),
        mandatory_own_full_accelerated_host_wrap_native_pass=True,
        parser_reuse=dict(path=base.PARSERS,sha256=base.PARSERS_PIN,
            functions_only=['native_join','read_footer'],no_ancestor_source_native_clock_review_credit=True),
        limits=['No real billions of protocol timesteps or measured full-sample PRP.',
            'Cache test is eventual duplicate-abort, not first matching-token age protection.',
            'Reset-at-wrap and independent bank oracle not inferred from timestamp aliases.',
            'Targeted AUTHOR barrier/scoped fault/context review and own physical/clock/advisor stay separate.'])
    return out


if __name__=='__main__':print(json.dumps(close(),indent=2))
