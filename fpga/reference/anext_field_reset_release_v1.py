"""Event-level reset/acceptance contract; no whole generator or physical claim."""
import argparse
from dataclasses import dataclass,field
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RTL='rtl/kernel/genefer_anext_field_reset_release_v1.sv'
DIAGNOSIS='results/throughput-20260929/anext-upper-recovery-reset-readonly-v1.json'
DIAGNOSIS_SHA='9312a9a24db0c542f0defaa12b4a151ca9053d22ed03462950e8698912ef34ba'
PINS={
    'rtl/kernel/genefer_anext_upper_ntt_sequencer_v1.sv':'6da1f271db2a6cd820d48e9a68fb12b2401dfe4384d91c17f9964fede8b7b295',
    'rtl/kernel/genefer_anext_upper_square_backend_v1.sv':'e31528f0ccdc61abe74d19193dd49936ec7e3fbc0415bc0aca8fe769ca3124d5',
    'rtl/kernel/genefer_anext_upper_block_engine_v1.sv':'053a9a88be0bdd8ac5a6ff3ff90d4c6dc5e461a4158ef28f2b3bfa02a7e2a5dd',
    'rtl/kernel/genefer_track_a4_field_transfer_v2.sv':'dd0e0401965741201fcfa8fddfacd530d8fec3da66030c8d307a480d54244688',
    'rtl/kernel/genefer_sdp_ram32.sv':'993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0',
    'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv':'501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
    'rtl/kernel/genefer_track_a4_control_fsm_v2.sv':'343d392e1b69f4230e3a59029aafd3355e8139b502589ff56c7b1fbe1bf49d03',
    'rtl/kernel/genefer_track_a4_blockroute_v2.sv':'0d292ef6072f250f9255b758319e0754b0265a3d26be694601bb96b25a9e1cfa',
    'rtl/kernel/genefer_a10_profile3_v1.sv':'526ede3d3bbb7bd43baf9f6830a087c5ba3f89ee0c6f5d32a8de24e57f27fd4b',
    # Existing fitted source uses exactly this preserve/dont_merge pattern.
    'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv':'704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7',
}


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def guard():
    need(sha((ROOT/DIAGNOSIS).read_bytes())==DIAGNOSIS_SHA,'ANEXT_RESET_MEASURED_DIAGNOSIS')
    for name,pin in PINS.items():need(sha((ROOT/name).read_bytes())==pin,'ANEXT_RESET_FROZEN_SOURCE '+name)
    d=json.loads((ROOT/DIAGNOSIS).read_text())
    need(d['measured']['recovery_wns_ns']==-.267 and d['measured']['critical_distribution'][1]['native_fanout']==140134,
         'ANEXT_RESET_ACTUAL_RECOVERY_NOT_ARITHMETIC')
    text=(ROOT/RTL).read_text()
    need(text.count('(* preserve, dont_merge *)')==2 and 'for(genvar f=0;f<3;f=f+1)' in text and
         'assign field_rst_n[f]=release_driver_q;' in text and
         'posedge clk or negedge assertion_rst_n' in text and
         'assign field_allow[f]=assertion_rst_n && release_driver_q;' in text,
         'ANEXT_RESET_DISTINCT_REAL_DRIVERS_AND_RAW_KILL')
    need('if(rst_n && write_en)' in (ROOT/'rtl/kernel/genefer_sdp_ram32.sv').read_text(),
         'ANEXT_RESET_RAM_RETAINS_PAYLOAD_GATES_ACCESS')
    control=(ROOT/'rtl/kernel/genefer_track_a4_control_fsm_v2.sv').read_text()
    need('bus.cancel<=0;' in control and 'bus.cancel<=1;' in control and
         'always_ff @(posedge bus.clk or negedge bus.rst_n)' in control,
         'ANEXT_RESET_LEGAL_REGISTERED_CANCEL_WIDTH')


@dataclass
class Release:
    guard_q:list=field(default_factory=lambda:[False]*3)
    driver_q:list=field(default_factory=lambda:[False]*3)
    rst_n:bool=False
    cancel:bool=False
    failed:bool=False

    @property
    def raw_live(self):return self.rst_n and not self.cancel and not self.failed

    @property
    def allow(self):return [self.raw_live and x for x in self.driver_q]

    @property
    def ready(self):return self.raw_live and all(self.driver_q)

    def inputs(self,*,rst_n=None,cancel=None,failed=None):
        for name,value in (('rst_n',rst_n),('cancel',cancel),('failed',failed)):
            if value is not None:
                need(type(value) is bool,'ANEXT_RESET_BOOL_INPUT');setattr(self,name,value)
        if not self.raw_live:self.guard_q=[False]*3;self.driver_q=[False]*3
        return dict(field_rst_n=list(self.driver_q),field_allow=self.allow,ready=self.ready,kill=not self.raw_live)

    def edge(self):
        before=self.inputs()
        if self.raw_live:self.driver_q=list(self.guard_q);self.guard_q=[True]*3
        return dict(before=before,after=self.inputs())


def ledger():
    return dict(schema='anext-field-reset-release-contract-v1',fields=3,release_FFs_per_field=2,diagnosis_sha256=DIAGNOSIS_SHA,
        assertion='Asynchronous same-predicate assertion on external reset/cancel/seqFAILED; raw field_allow drops immediately, driver asynchronously clears all existing leaf resets.',
        release='After raw predicate deassertion: first eligible edge primes guard; second drives reset high after edge; earliest direct leaf acceptance third edge. No request buffered or silently delayed.',
        ready='Reset-only ready. Profile-loaded/cache/image/base/generation/coherence/quiet/admission conditions still independently required. Invalid direct request before ready must be explicitly rejected by integrator, never silently dropped.',
        pulse_contract='Whole cancel must retain its current registered full-clock width, FAILED registered/steady. Controller/leaves assert on subcycle pulses, but synchronous transfer cancellation of an outstanding request requires a sampled cancel edge; otherwise missing response must genuinely quarantine. Global rst_n asynchronously clears transfer tokens.',
        cold_direct_admission_extra_edges=2,warm_extra_edges=0,
        transfer='Earliest caller request at first eligible post-cancel edge E0 traverses unchanged source/destination stages: leafRAM E2 sees released reset. Caller response consumed E5. Thus no extra transfer edge/drop; hold/reject earlier request while raw kill asserted.',
        cold_whole_cost='Two-edge release guard may overlap existing setup/reload/transfer; do not add +2 to NTT phase counters blindly. Integrator measures command calendar and accounts any exposed initial/reload delay explicitly.',
        abort='Any pulse, even between clocks, clears all release history; restart two-edge release. FAILED holds reset until original sequencer cancel recovery clears it. Outer fault/quarantine must latch genuine error before child reset clears transient errors.',
        metadata='All existing leaf state/valid/type/tag/profile/header/cache/read_due eligibility resets retained. No stale completion/read/profile publication during release; owner/generation and complete reload remain external.',
        payload='All existing multiplier payload resets retained. SDP memory/read_q and already-unreset transfer payload retain data behind validity; no zeroing/reset-diet or rollback.',
        preservation='Six field-local FFs, three directly consumed final drivers; preserve/dont_merge matches existing fitted source pattern. Synthesis retention, nonmerge, global-buffer routing and actual fanout must still be verified later.',
        physical_benefit_proven=False,fanout_reduction_claim=False,audited_clock=False,timing_exception=False,whole_sources_changed=False,promotion_allowed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();guard();result=ledger()
    result.update(controller_sha256=sha((ROOT/RTL).read_bytes()),source_pins=PINS,native_executed=False)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(schema=result['schema'],controller_sha256=result['controller_sha256'],
                         warm_extra_edges=result['warm_extra_edges'],cold_direct_admission_extra_edges=result['cold_direct_admission_extra_edges']),indent=2))
