"""Source-bound phase forecast from an actual P8/P16 continuous100 result.

Metadata/scalar only: no role import, numeric oracle, HDL, execution or policy
override. Candidate controller cycles, native reference operations, one final
read and fixed setup are distinct measured work terms, not whole-bench ticks.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP = 'stream27-s4-continuous-normal'
SHAPE = dict(model_command_seconds=10450, overall_seconds=10700,
             outer_seconds=10800, stop_grace_seconds=15)
TIMERS = {'candidate_ms', 'reference_ms', 'read_ms'}


def need(ok, why):
    if not ok:
        raise ValueError('S4 phase duration: ' + why)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def positive(value):
    need(type(value) in (int, float) and math.isfinite(value) and value > 0,
         'positive finite measurement')
    return value


def model_threads(build,probe):
    """Exact declared/context/model binding, not thread-normalized timing."""
    count=build.get('runtime_threads',1)
    need(type(count) is int and count in (1,4,8),'explicit finite1/4/8 model threads')
    flags=build.get('cflags',[])
    need(type(flags) is list and all(type(flag) is str for flag in flags),'typed compiler flags')
    overrides=re.findall(r'(?:^|\s)(-[DU](?:GFN16_RUNTIME_THREADS|CORE27_[A-Z_0-9]*RUNTIME_THREADS)(?:[^\s]*))',' '.join(flags))
    expected=[f'-DGFN16_RUNTIME_THREADS={count}'] if 'runtime_threads' in build else []
    need(overrides==expected,'exact runtime macro/default without extra overrides')
    wanted=dict(context_threads=count,model_threads=count,expected_threads=count)
    need(type(probe) is dict and probe==wanted and all(type(value) is int for value in probe.values()),
         'exact typed context/model/expected probe')
    return count


def source_selection(manifest):
    """Exact frozen source calendars, never an arbitrary claimed warm interval."""
    continuous=manifest['continuous'];parameters=manifest['build']['parameters']
    stages=continuous['canonical_pipe_stages'];boundary=continuous.get('boundary_inputreg',0)
    diet=continuous.get('p16_diet',0);timing=continuous.get('p16_timing',0);r75=continuous.get('p8_r75',0)
    need(all(type(v) is int and v in (0,1) for v in (stages,boundary,diet,timing,r75)) and
         (not boundary or stages==1) and (not timing or diet==1) and
         (not r75 or stages==1 and boundary==diet==timing==0), 'explicit source selectors')
    need(parameters.get('CANONICAL_PIPE_STAGES',0)==stages,'source canonical pipeline')
    if diet:
        need(stages==1 and boundary==0 and all(parameters.get(key)==value for key,value in
             dict(AW=16,P=16,CONTEXTS=1,EPOCH_SEED=65534,CORR_SERIAL_BFS=2,
                  COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1).items()),'exact composed P16 diet flags')
        flags=dict(BOUNDARY_INPUTREG=1,DESCRIPTOR_FIFO_FF=1,QUARANTINE_REPLICAS=1,
            FINAL_GS_INPUTREG=1,CANONICAL_LOCALBASE=1,CARRY_LOCALBASE=1,TERM_SELECT_TOKEN=1)
        need(all(parameters.get(key,0)==(value if timing else 0) for key,value in flags.items()),
             'exact baseline or all-seven P16 flags')
        geo=dict(interval=8460 if timing else 8459,carry_done=12558 if timing else 12557,
                 first_digit=8459 if timing else 8458,cold_first=102)
        plan=continuous['plan'];profile=plan['profile']
        need(all(profile.get(key)==value for key,value in dict(aw=16,n=65536,p=16,
             contexts=1,base=604832956,epoch_seed=65534,canonical_pipe_stages=1,p16_diet=1,
             corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1).items()),'exact P16 record profile')
        root='0011468ec67d7ca7ebb86fac88103fd19ea0207dc75685289da64d508228ea28' if timing else 'b683cb1113a17652f5d6266c4298c5eb825c6af6b9f92bd28f758dba9b8de898'
        need(plan['geometry']==geo and plan['candidate_root_sha256']==root and
             profile.get('p16_timing',0)==timing and
             (not timing or profile.get('timing_flags')==flags),'frozen P16 source/calendar/root')
    elif r75:
        flags=dict(BOUNDARY_INPUTREG=1,DESCRIPTOR_FIFO_FF=1,QUARANTINE_REPLICAS=1,
            FINAL_GS_INPUTREG=1,CANONICAL_LOCALBASE=1,CARRY_LOCALBASE=1)
        wanted=dict(AW=16,P=8,CONTEXTS=1,EPOCH_SEED=65534,CANONICAL_PIPE_STAGES=1,**flags)
        need(all(parameters.get(key)==value for key,value in wanted.items()) and
             parameters.get('TERM_SELECT_TOKEN',0)==0,'exact six-flag P8 r75 source')
        geo=dict(interval=16654,carry_done=24848,first_digit=16653,cold_first=102)
        plan=continuous['plan'];profile=plan['profile']
        need(all(profile.get(key)==value for key,value in dict(aw=16,n=65536,p=8,
             contexts=1,base=604832956,epoch_seed=65534,canonical_pipe_stages=1,p8_r75=1).items()) and
             profile.get('timing_flags')==flags and plan['geometry']==geo and
             plan['candidate_root_sha256']=='c13871f9d9bf13bdd50c2e4c0084d58351a5d30cdeca614537d0445dd62458d7',
             'frozen P8 r75 source/calendar/root')
    else:
        need(not timing and parameters.get('P',8)==8 and
             parameters.get('BOUNDARY_INPUTREG',0)==boundary,'explicit legacy P8 source')
        geo=dict(interval=16653,carry_done=24847,first_digit=16652,cold_first=102)
        need('geometry' not in continuous['plan'] or continuous['plan']['geometry']==geo,
             'frozen P8 source calendar')
    selected=dict(stages=stages,boundary=boundary,p16_diet=diet,p16_timing=timing,geometry=geo)
    if r75:selected['p8_r75']=1
    return selected


def normal_config(count,selection):
    config=dict(operations=count,negative='none',canonical_pipe_stages=selection['stages'])
    for source,key in (('boundary','boundary_inputreg'),('p16_diet','p16_diet'),('p16_timing','p16_timing'),('p8_r75','p8_r75')):
        if selection.get(source,0):config[key]=1
    return config


def predict(candidate_cycles, full_candidate_cycles_max, timers,
            model_seconds, overall_seconds, margin=1.75):
    need(type(candidate_cycles) is int and candidate_cycles > 0 and
         type(full_candidate_cycles_max) is int and full_candidate_cycles_max >= candidate_cycles,
         'candidate-controller cycle denominator, not whole-bench ticks')
    need(type(timers) is dict and set(timers) == TIMERS and
         all(type(value) is int and value > 0 for value in timers.values()),
         'three positive native millisecond phase measurements')
    model_seconds, overall_seconds, margin = map(positive, (model_seconds, overall_seconds, margin))
    need(margin >= 1.75 and overall_seconds >= model_seconds,
         'explicit at-least1.75 margin and retained nonmodel time')
    measured_phase_seconds = sum(timers.values()) / 1000
    need(model_seconds >= measured_phase_seconds, 'phase sum within measured command')
    candidate = timers['candidate_ms'] / 1000 * full_candidate_cycles_max / candidate_cycles * margin
    native_reference = timers['reference_ms'] / 1000 * 10 * margin
    read = timers['read_ms'] / 1000 * margin
    fixed = (model_seconds - measured_phase_seconds) * margin
    nonmodel = (overall_seconds - model_seconds) * margin
    model_estimate = candidate + native_reference + read + fixed
    overall_estimate = model_estimate + nonmodel
    return dict(method='candidate_cycles_linear_native_reference_fixed_read_setup',
        margin=margin, pilot_operations=100, continuous_operations=1000,
        measured_candidate_cycles=candidate_cycles,
        continuous_candidate_cycles_max=full_candidate_cycles_max,
        measured_phase_wall_ms=timers, measured_model_seconds=model_seconds,
        measured_overall_seconds=overall_seconds,
        candidate_seconds_per_controller_cycle_observed=timers['candidate_ms'] / 1000 / candidate_cycles,
        candidate_seconds_estimate=candidate,
        native_reference_seconds_estimate=native_reference,
        read_seconds_estimate=read, fixed_model_seconds_estimate=fixed,
        nonmodel_seconds_estimate=nonmodel,
        continuous_command_seconds_estimate=model_estimate,
        overall_seconds_estimate=overall_estimate,
        full_reference_replay_seconds_estimate=0,
        finite_shape=SHAPE,
        fits_finite_shape=model_estimate <= SHAPE['model_command_seconds'] and
                          overall_estimate <= SHAPE['overall_seconds'],
        scope='Scalar planning estimate, not native1000 success or achievable clock. '
              'Reference is included in the model command; no external GMP replay. '
              'Candidate cycles include one worst-special finalization, not fabricated whole-model ticks.')


def prepare(role, pilot_dir, gate_path, output):
    role, pilot_dir, gate_path, output = map(lambda value: Path(value).resolve(),
                                           (role, pilot_dir, gate_path, output))
    need(not output.exists() and not (ROOT / 'docs/briefs/PAUSE').exists(), 'fresh output/no PAUSE')
    paths = dict(pilot_manifest=pilot_dir / 'approved-manifest.json',
                 pilot_report=pilot_dir / 'report.json', pilot_gate=gate_path)
    values = {name: json.loads(path.read_text()) for name, path in paths.items()}
    pins = {name: sha(path) for name, path in paths.items()}
    m = json.loads((role / 'manifest.json').read_text())
    p, r, g = (values[name] for name in ('pilot_manifest', 'pilot_report', 'pilot_gate'))
    need(g['status'] == 'PASS_expected_contracts' and g['promotion_allowed'] is False and
         g['manifest_sha256'] == pins['pilot_manifest'] and g['report_sha256'] == pins['pilot_report'],
         'actual automatic native pilot gate/raw bindings')
    host = r['host']
    need(host in ('gfn16-azure-sim-f32', 'gfn16-pilot-c4d') and
         r['status'] == 'completed_native_commands_unreviewed' and
         r['manifest_sha256'] == pins['pilot_manifest'], 'actual completed admitted pilot')
    need(m['build'] == p['build'] and m['probe'] == p['probe'],
         'unchanged source/build/exact same pilot and full probe')
    threads=model_threads(m['build'],m['probe']['expected_json'])
    need(r['probe']==m['probe']['expected_json'] and type(r['model_threads']) is int and
         r['model_threads']==threads,'actual pilot runtime matches declared model, never borrow serial timing')
    need(len(m['steps']) == len(p['steps']) == 1 and
         m['steps'][0]['name'] == p['steps'][0]['name'] == STEP and
         m['steps'][0]['argv'] == ['{exe}', '1000'] and p['steps'][0]['argv'] == ['{exe}', '100'],
         'one continuous100 pilot to one continuous1000 command')
    selected=source_selection(m);need(source_selection(p)==selected,'exact same pilot/full source selection')
    stages=selected['stages'];boundary=selected['boundary'];diet=selected['p16_diet'];timing=selected['p16_timing'];r75=selected.get('p8_r75',0)
    for model, count in ((m, 1000), (p, 100)):
        config=normal_config(count,selected)
        need(model['steps'][0]['validator']['config'] ==
             config and model['continuous'].get('boundary_inputreg',0)==boundary and
             model['continuous'].get('p8_r75',0)==r75 and
             model['continuous']['operations'] == count and
             model['continuous']['plan'] == m['continuous']['plan'],
             'same source-bound plan, initial state, bits and normal mode')
    row = [value for value in r['steps'] if value['name'] == STEP]
    gates = [value for value in g['steps'] if value['name'] == STEP]
    need(len(row) == len(gates) == 1 and row[0]['returncode'] == 0 and
         row[0]['error'] is None and gates[0]['actual_returncode'] == 0,
         'unique successful actual model command')
    native = gates[0]['validation']
    need(native == r['validations'][STEP] and native['status'] == 'PASS_expected_contracts' and
         native['canonical_pipe_stages'] == stages and native['base'] == 604832956 and
         native.get('boundary_inputreg',0)==boundary and
         native.get('p16_diet',0)==diet and native.get('p16_timing',0)==timing and
         native.get('p8_r75',0)==r75 and
         native['candidate_root_sha256'] == m['continuous']['plan']['candidate_root_sha256'] and
         native['independent_reference_equal'] is True and native['operations'] == 100 and
         native['final_actual_sha256'] == native['final_expected_sha256'],
         'typed native target/case/full-reference equality retained')
    observed = native['counts']; wanted = p['continuous']['counts_ordinary_source_projection']
    special = observed['special']
    need(type(special) is int and special in (0, 1), 'actual special representation')
    expected = dict(wanted)
    expected.update(special=special, canonical_cycles=wanted['canonical_cycles'] + special * 65536,
                    candidate_cycles=wanted['candidate_cycles'] + special * 65536)
    need(observed == expected, 'actual all100 source-cycle/job/descriptor counters')
    full = m['continuous']['counts_ordinary_source_projection']
    need(full['operations'] == 1000 and full['doubles'] == 500 and
         full['case_id'] == observed['case_id'] and
         all(full[key] == 1 for key in ('resets', 'loads', 'starts', 'readbacks')) and
         full['candidate_cycles'] == 102 + 999 * selected['geometry']['interval'] + selected['geometry']['carry_done'] + 2 + (7 + 3 * stages) * 65536 + 4,
         'explicit1000 one-job source ledger')
    names = set(m['build']['sv_sources']) | {m['build']['cpp_source'],
        'rtl/tb/stream27_s4_continuous_config_v1.h', 'rtl/tb/native_runtime_context_v1.h',
        'rtl/tb/stream27_host_chain_full_reference_v1.h', 'rtl/tb/stream27_shared_reference_ntt_v1.h'}
    validator = m['steps'][0]['validator']
    names.add(validator['source']); names.update(validator['assets'].values())
    source_pins = {name: m['sources'][name] for name in sorted(names)}
    need(all(p['sources'].get(name) == pin and sha(role / 'source/fpga' / name) == pin
             for name, pin in source_pins.items()), 'unchanged compiled/harness/reference/plan sources')
    estimate = predict(observed['candidate_cycles'], full['candidate_cycles'] + 65536,
                       native['phase_wall_ms'], row[0]['seconds'], r['seconds'])
    result = dict(schema='stream27-s4-continuous-phase-forecast-v1',
        status='PASS_S4_measured_phase_forecast' if estimate['fits_finite_shape'] else 'BLOCKED_S4_phase_forecast_exceeds_finite_shape',
        generator_sha256=sha(__file__), compatible_hosts=[host],
        short_manifest_sha256=pins['pilot_manifest'], short_report_sha256=pins['pilot_report'],
        short_gate_sha256=pins['pilot_gate'], source_model_build=m['build'], source_model_pins=source_pins,
        canonical_pipe_stages=stages, model_threads=threads, model_step=STEP, pilot_native_validation=native,
        forecast=estimate, local_full_n_integer_computation=False, promotion_allowed=False)
    if boundary:result['boundary_inputreg']=1
    if diet:result['p16_diet']=1
    if timing:result['p16_timing']=1
    if r75:result['p8_r75']=1
    output.mkdir(parents=True)
    (output / 'forecast.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('role', 'pilot-dir', 'gate', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.role, args.pilot_dir, args.gate, args.output), indent=2))
