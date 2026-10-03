"""Correct live canonical-overlap observation on the frozen full application70.

The failed v7/v8 used a counter copied only at canon_done. Production RTL,
physical parameters, input/reference/header, clocks/horizon and strict final
conjunction are literal; a passive observer now exposes the actual busy/owner.
"""
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha, need, dump, runtime_before_model
from fpga.reference import stream27_r15_shell_application_v4_native as parent

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_r15_application_full_live_monitor_v9.py'
PARENT = ROOT / 'results/throughput-20260929/trackS-r15-shell-application-native-v4/full-diagnostic-v8'
PARENT_PIN = 'a183688c67d1ff93dde9fb74853841f470a741ac5c5ce94aee888fe6811e1866'
ID = 's4-p16-c2-r15-shell-application-full-normal-q1-v9'
OUT = ROOT / 'results/throughput-20260929/trackS-r15-shell-application-native-v4/full-live-monitor-v9'
HOST = 'candidate.compute.direct_cold.candidate'
OLD_MONITOR = ' if(lane64(d.probe_canonical,0)>0&&lane32(d.probe_completed,1)<COUNTS[1]&&(d.probe_busy&2u))canonical_peer=true;'
NEW_MONITOR = ''' if(d.probe_live_canon_busy){
  unsigned c=unsigned(d.probe_live_canon_owner);if(canon_first[c]==0)canon_first[c]=age;
 }
 if(d.probe_live_canon_busy&&!d.probe_live_canon_owner&&lane32(d.probe_completed,1)<COUNTS[1]&&(d.probe_busy&2u)){
  canonical_peer=true;canonical_peer_edges++;
 }'''
STATE = 'static std::array<uint64_t,2> canon_first{};static uint64_t canonical_peer_edges=0;\n'
TRACE = ''' std::cout<<"R15_APPLICATION_LIVE_CANONICAL {\\"first\\":["<<canon_first[0]<<","<<canon_first[1]
  <<"],\\"peer_edges\\":"<<canonical_peer_edges<<",\\"publication_edges\\":["<<done_edges[0]<<","<<done_edges[1]
  <<"],\\"signed96_words\\":"<<read_words<<",\\"error\\":"<<unsigned(d.probe_error)<<"}\\n";
'''


def live_peer_event(canon_busy, canon_owner, peer_completed, peer_busy):
    return bool(canon_busy and canon_owner == 0 and peer_completed < 2 and peer_busy)


def config():
    return dict(parent.config('full'), canonical_overlap_probe='actual_canon_busy_and_owner',
                publication_edges=[680689,1340153], monitor_version=9)


def validate(stdout, stderr, rc, config, assets):
    need(config == globals()['config']() and assets == {}, 'R15_APP_V9_EXACT_SOURCE_CONFIG')
    lines = stdout.splitlines(keepends=True)
    need(len(lines) == 2 and lines[1].startswith('R15_APPLICATION_LIVE_CANONICAL '), 'R15_APP_V9_ACTUAL_LIVE_TRACE')
    base = parent.validate(lines[0], stderr, rc, parent.config('full'), {})
    v = json.loads(lines[1].removeprefix('R15_APPLICATION_LIVE_CANONICAL '))
    need(set(v) == {'first','peer_edges','publication_edges','signed96_words','error'} and
         all(type(x) is int for x in v['first']) and len(v['first']) == 2 and
         21224 + 4096 <= v['first'][0] < 25454 and v['first'][1] > 680689 and
         type(v['peer_edges']) is int and v['peer_edges'] > 0 and
         v['publication_edges'] == config['publication_edges'] and v['signed96_words'] == 262144 and v['error'] == 0,
         'R15_APP_V9_GENUINE_LIVE_PEER_AND_OWN_PUBLICATION_WORD_LEDGER')
    base['measurements'].update(actual_live_canonical_trace=v, publication_edges=v['publication_edges'])
    base['scope'] += ' Live canonical busy and context ownership are passive source probes; completed-service counter is not used as activity. Original equal-short v7/v8 witnesses preserved.'
    return base


def corrected_cpp(before):
    need(before.count(OLD_MONITOR) == 1, 'R15_APP_V9_ONE_RETROSPECTIVE_MONITOR')
    after = before.replace(OLD_MONITOR, NEW_MONITOR, 1)
    marker = 'static unsigned ctrl_transactions=0,cold_words=0,read_words=0;'
    need(after.count(marker) == 1, 'R15_APP_V9_PASSIVE_COUNTER_STATE')
    after = after.replace(marker, STATE + marker, 1)
    footer = ' std::cout<<"' + parent.FOOTERS['full'].rstrip('\n') + '\\n";\n'
    need(after.count(footer) == 1, 'R15_APP_V9_POSITIVE_FOOTER_UNCHANGED')
    after = after.replace(footer, footer + TRACE, 1)
    need(after.replace(NEW_MONITOR, OLD_MONITOR, 1).replace(STATE, '', 1).replace(TRACE, '', 1) == before,
         'R15_APP_V9_ONLY_MONITOR_AND_PASSIVE_TRACE_REVERSAL')
    runtime_before_model(after)
    return after


def corrected_observer(before):
    marker = ' output wire probe_error,probe_link_ready,'
    addition = ' output wire probe_live_canon_busy,probe_live_canon_owner,\n'
    assigns = ' assign probe_live_canon_busy=' + HOST + '.canon_busy;\n assign probe_live_canon_owner=' + HOST + '.canonical_owner;\n'
    need(before.count(marker) == 1 and before.count('endmodule') == 1, 'R15_APP_V9_STATELESS_OBSERVER_ANCHORS')
    after = before.replace(marker, addition + marker, 1).replace('endmodule', assigns + 'endmodule', 1)
    need(after.replace(addition, '', 1).replace(assigns, '', 1) == before, 'R15_APP_V9_ONLY_PASSIVE_WIRE_REVERSE')
    return after


def temporal_proof():
    # Exact source field intervals, ROWS-wide scratch loading and captured PUB1
    # service. No native result or predecessor period supplies this calculation.
    n, rows, interval, carry = 65536, 4096, 8461, 12558
    warm = [f + interval + carry + 1 for f in (204,4434)]
    allocation0 = warm[0] + 2
    first_live0 = allocation0 + rows + 3
    publication0 = allocation0 + rows + 10*n + 7
    allocation1 = max(warm[1] + 2, publication0 + 1)
    publication1 = allocation1 + rows + 10*n + 7
    need(first_live0 < warm[1] and [publication0,publication1] == [680689,1340153],
         'R15_APP_V9_SOURCE_TIMELY_LIVE_CANONICAL_OVERLAP')
    return dict(warm_edges=warm, first_live0_model=first_live0, peer_overlap_margin=warm[1]-first_live0,
                publication_edges=[publication0,publication1], source_arithmetic_only=True,
                native_execution_inherited=False, period_ns=None)


def role():
    raw = (PARENT/'manifest.json').read_bytes()
    need(sha(raw) == PARENT_PIN, 'R15_APP_V9_PRESERVED_DIAGNOSTIC_CAPTURE')
    m = json.loads(raw)
    b = json.loads((PARENT/'production-bundle.json').read_bytes())
    f = {n:(PARENT/'source/fpga'/n).read_bytes() for n in m['sources']}
    need(all(sha(f[n]) == h for n,h in m['sources'].items()), 'R15_APP_V9_CAPTURE_CLOSURE')
    cpp = m['build']['cpp_source']; obs = 'rtl/'+m['build']['top']+'.sv'
    f[cpp] = corrected_cpp(f[cpp].decode()).encode()
    f[obs] = corrected_observer(f[obs].decode()).encode()
    f[SELF] = (ROOT/SELF).read_bytes()
    need(all(f['rtl/'+n] == t.encode() for n,t in b['files'].items()) and len(b['files']) == 70 and
         m['build']['parameters']['EPOCH_SEED0'] == m['build']['parameters']['EPOCH_SEED1'] == 0,
         'R15_APP_V9_ALL70_AND_PHYSICAL_PARAMS_LITERAL')
    host = next(t for n,t in b['files'].items() if n.endswith('_r15_host_ports_v1.sv'))
    need('context_canonical_cycles[canonical_owner]<=canon_cycles;phase[canonical_owner]<=COPY;' in host and
         'if(canon_done && canonical_owned && phase[canonical_owner]==CANON_WAIT)' in host and
         'wire canon_busy,canon_done' in host and 'logic canonical_owner,canonical_owned' in host,
         'R15_APP_V9_RETROSPECTIVE_COUNTER_CAUSE_AND_LIVE_SIGNAL_SOURCE')
    m['steps'] = [dict(name='normal-full-r15-application-v4-live-monitor-v9',argv=['{exe}'],expected_returncode=0,
        validator=dict(source=SELF,function='validate',config=config(),assets={}))]
    m['r15_application_live_monitor_v9'] = dict(parent_manifest_sha256=PARENT_PIN,
        source_temporal_proof=temporal_proof(), production70_header_reference_params_unchanged=True,
        observer_two_passive_wires_only=True, strict_final_conjunction_retained=True,
        original_v7_v8_failures_preserved=True, host_GL=False, vendor_simulated=False, promotion_allowed=False)
    m['sources'] = {n:sha(v) for n,v in f.items()}
    m['source_root'] = m['output_parent'] = 'UNBOUND'
    m['rtl_readiness']['candidate_id'] = ID.removesuffix('-q1-v9')
    return m,f,b


def freeze():
    m,f,b = role(); need(not OUT.exists(), 'R15_APP_V9_FRESH_CORRECTIVE_NORMAL')
    source = OUT/'source/fpga'; source.mkdir(parents=True)
    for n,value in f.items():
        p = source/n; p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(value)
    m['source_root'] = str(source)
    dump(OUT/'manifest.json',m); dump(OUT/'production-bundle.json',b)
    return dict(id=ID,manifest=str(OUT/'manifest.json'),sha256=sha((OUT/'manifest.json').read_bytes()),status='CORRECTIVE_NORMAL_SOURCE_NOT_NATIVE')


if __name__ == '__main__':print(json.dumps(freeze(),indent=2))
