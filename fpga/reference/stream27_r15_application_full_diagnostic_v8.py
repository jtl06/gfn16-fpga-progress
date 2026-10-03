"""Passive failure-fields successor of the preserved app-v4 full v7 witness.

No production70/header/parameters/reference/calendar/horizon/assertion change.
The existing positive validator still requires the same complete all-word run.
"""
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha, need, dump, runtime_before_model

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_r15_application_full_diagnostic_v8.py'
PARENT = ROOT / 'results/throughput-20260929/trackS-r15-shell-application-native-v4/full-normal'
PARENT_PIN = '971e5835f8f45f4653091574fd7e2c606fa40f99e20116ac194d0884aa5bfdc8'
CPP_PIN = '2497f6f9a4ecb60f6d305ac41ea4a6e16aafc5d59814048012baec99e89be073'
ID = 's4-p16-c2-r15-shell-application-full-normal-q1-v8'
OUT = ROOT / 'results/throughput-20260929/trackS-r15-shell-application-native-v4/full-diagnostic-v8'
OLD = '"R15_APPLICATION_CORE_PUBLICATION_INTERLEAVE");'
NEW = '''"R15_APPLICATION_CORE_PUBLICATION_INTERLEAVE tracking="+std::to_string(tracking)+
      " age="+std::to_string(age)+" ticks="+std::to_string(ticks)+
      " ready="+std::to_string(unsigned(d.probe_ready))+" busy="+std::to_string(unsigned(d.probe_busy))+
      " done0="+std::to_string(done_count[0])+" done1="+std::to_string(done_count[1])+
      " edge0="+std::to_string(done_edges[0])+" edge1="+std::to_string(done_edges[1])+
      " waiting_b="+std::to_string(waiting_b)+" capture_copy="+std::to_string(capture_copy)+
      " expected_capture_copy="+std::to_string(EXPECT_CAPTURE_COPY)+" canonical_peer="+std::to_string(canonical_peer)+
      " started0="+std::to_string(lane32(d.probe_started,0))+" started1="+std::to_string(lane32(d.probe_started,1))+
      " completed0="+std::to_string(lane32(d.probe_completed,0))+" completed1="+std::to_string(lane32(d.probe_completed,1))+
      " rows0="+std::to_string(lane32(d.probe_rows,0))+" rows1="+std::to_string(lane32(d.probe_rows,1))+
      " canonical0="+std::to_string(lane64(d.probe_canonical,0))+" canonical1="+std::to_string(lane64(d.probe_canonical,1))+
      " copy0="+std::to_string(lane64(d.probe_copy,0))+" copy1="+std::to_string(lane64(d.probe_copy,1))+
      " error="+std::to_string(unsigned(d.probe_error)));'''


def diagnostic_cpp(before):
    need(before.count(OLD) == 1 and 'i<432ull*N' in before and 'next%12==6' in before,
         'R15_APP_FULL_V8_ACTUAL_FAILED_CPP_AND_EXISTING_UNIT_CORRECTION')
    after = before.replace(OLD, NEW, 1)
    need(after.replace(NEW, OLD, 1) == before, 'R15_APP_FULL_V8_ONLY_PASSIVE_ERROR_TEXT_REVERSAL')
    runtime_before_model(after)
    return after


def role():
    raw = (PARENT / 'manifest.json').read_bytes()
    need(sha(raw) == PARENT_PIN, 'R15_APP_FULL_V8_PRESERVED_PARENT')
    m = json.loads(raw)
    b = json.loads((PARENT / 'production-bundle.json').read_bytes())
    f = {n: (PARENT / 'source/fpga' / n).read_bytes() for n in m['sources']}
    need(all(sha(f[n]) == h for n, h in m['sources'].items()), 'R15_APP_FULL_V8_PARENT_CLOSURE')
    cpp = m['build']['cpp_source']
    need(sha(f[cpp]) == CPP_PIN, 'R15_APP_FULL_V8_ACTUAL_COMPILED_CPP')
    before = f[cpp].decode()
    f[cpp] = diagnostic_cpp(before).encode()
    f[SELF] = (ROOT / SELF).read_bytes()
    need(len(b['files']) == 70 and all(f['rtl/' + n] == t.encode() for n, t in b['files'].items()) and
         m['build']['parameters']['EPOCH_SEED0'] == m['build']['parameters']['EPOCH_SEED1'] == 0,
         'R15_APP_FULL_V8_LITERAL70_PHYSICAL_PARAMS')
    m['steps'][0]['name'] = 'normal-full-r15-application-v4-passive-diagnostic-v8'
    m['r15_application_passive_diagnostic_v8'] = dict(
        parent_manifest_sha256=PARENT_PIN, parent_cpp_sha256=CPP_PIN,
        new_cpp_sha256=sha(f[cpp]), strict_interleave_conjunction_unchanged=True,
        horizon_432N_ticks_36N_core_edges_unchanged=True, only_failure_message_fields_added=True,
        production70_header_reference_parameters_unchanged=True, all_word_positive_validator_unchanged=True,
        failed_v7_preserved=True, native_outcome_not_inherited=True, promotion_allowed=False)
    m['sources'] = {n: sha(v) for n, v in f.items()}
    m['source_root'] = m['output_parent'] = 'UNBOUND'
    m['rtl_readiness']['candidate_id'] = ID.removesuffix('-q1-v8')
    return m, f, b


def freeze():
    m, f, b = role()
    need(not OUT.exists(), 'R15_APP_FULL_V8_FRESH_DIAGNOSTIC_ROLE')
    source = OUT / 'source/fpga'
    source.mkdir(parents=True)
    for n, value in f.items():
        p = source / n
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as stream:
            stream.write(value)
    m['source_root'] = str(source)
    dump(OUT / 'manifest.json', m)
    dump(OUT / 'production-bundle.json', b)
    return dict(id=ID, manifest=str(OUT / 'manifest.json'), sha256=sha((OUT / 'manifest.json').read_bytes()),
                status='PASSIVE_DIAGNOSTIC_SOURCE_READY_NOT_NATIVE')


if __name__ == '__main__':
    print(json.dumps(freeze(), indent=2))
