"""Read-only R11 delta evidence replay. No native execution or full-N arithmetic.

Reviewer p16_mlab authored unchanged ancestors and excludes their logic. This
checks new source/binding/calendar/evidence, not global nonauthorship or clocks.
"""
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
INDEX = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-transport11-ownlong-v1/numerical-index-v1.json'
INDEX_PIN = 'aa7b549b6cb8df2cca6f3eb735a69db4086e844be4e7fa315d31f403d3f71613'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError('R11_SCOPED_REVIEW_' + why)


def read_ref(ref):
    p = Path(ref['path'])
    if not p.is_absolute():
        p = ROOT / p
    raw = p.read_bytes()
    need(sha(raw) == ref['sha256'], 'PIN:' + str(p))
    return raw


def calendar(count):
    warm = [first + (count-1)*8463 + 12562 for first in (204,4435)]
    allocation, publication, release = [], [], -1
    for edge in warm:
        start = max(edge+2, release+1)
        release = start + 4096 + 10*65536 + 7
        allocation.append(start)
        publication.append(release)
    return dict(warm_edges=warm, allocation_edges=allocation, publication_edges=publication,
                pair_completion_cycles=release, full_read_completion_cycles=release+65536)


def replay():
    need(sha(INDEX.read_bytes()) == INDEX_PIN, 'INDEX')
    index = json.loads(INDEX.read_bytes())
    bundles = [json.loads(read_ref(index['production'][name])) for name in ('bundle','aw8_bundle')]
    by_aw = {b['geometry']['aw']: b for b in bundles}
    for b in bundles:
        need(len(b['files']) == 58 and {n:sha(t.encode()) for n,t in b['files'].items()} == b['generated_sha256'], '58_BUNDLE_BYTES')
        need(not any('crt_tag_delay_mlab' in n or 'term_prefetch_mlab' in n for n in b['files']), 'PRIVATE_HELPERS_NOT_INTEGRATED')
        need(b['context_transport11']['term_recurrence_edges'] == 4, 'E4')
    from fpga.reference import stream27_context_storage_combo_transport11_bind as binder
    from fpga.reference import stream27_context_storage_combo_transport11_source_v2 as closure
    for aw,b in by_aw.items():
        emitted = binder.prepare(1<<aw, enabled=1, lean_production=1, crt_transport_reg=1,
            inverse_ingress_reg=1, term_join_transport_reg=1, lean_progress_watchdog=1)
        need(emitted['files'] == b['files'] and emitted['geometry'] == b['geometry'], 'EXACT_SOURCE_REPRODUCTION')
        closed = closure.prepare(1<<aw, enabled=1, lean_production=1, crt_transport_reg=1,
            inverse_ingress_reg=1, term_join_transport_reg=1, lean_progress_watchdog=1)
        need(closed['files'] == b['files'], 'CLOSURE_ONLY_58_LITERAL')
        need(b['parameters'] == closed['parameters'], 'PRODUCTION_PARAMETERS')
        g=b['geometry']
        need(g['pointwise_accept'] == b['context_transport11']['calendar_before']['pointwise_accept'] and
             (g['correction_cache_latency'],g['term_seed_first'],g['term_seed_last']) == (78,71,74), 'PW_CACHE_SEEDS_UNCHANGED')
    jobs=[]
    for j in index['jobs']:
        m=json.loads(read_ref(j['selected_manifest'])); r=json.loads(read_ref(j['report'])); g=json.loads(read_ref(j['gate']))
        need(g['status']=='PASS_expected_contracts' and g['report_sha256']==j['report']['sha256'] and
             g['manifest_sha256']==j['selected_manifest']['sha256']==r['manifest_sha256'], 'ACTUAL_GATE_JOIN')
        pkg=j['selected_package']; need(sha(Path(pkg['archive']).read_bytes())==pkg['sha256'],'ACTUAL_PACKAGE')
        with tarfile.open(pkg['archive']) as tar:
            files={n:tar.extractfile('capture/source/fpga/'+n).read() for n in m['sources']}
        need({n:sha(raw) for n,raw in files.items()}==m['sources']==r['sources'], 'ALL_CAPTURED_SOURCES')
        b=by_aw[m['build']['parameters']['AW']]
        need(m['build']['parameters']==dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42), 'OWN_PARAMETERS')
        sv=m['build']['sv_sources']; need(len(sv)==j['compiled_sv_count'], 'COMPILED_SV_COUNT')
        need(all('rtl/'+n in sv and m['sources']['rtl/'+n]==pin for n,pin in b['generated_sha256'].items()), 'EVERY_PRODUCTION_FILE_ACTUALLY_COMPILED')
        build=next(x for x in r['steps'] if x['name']=='build')
        need(build['returncode']==0 and all('-G'+k+'='+str(v) in build['command'] for k,v in m['build']['parameters'].items()), 'ACTUAL_PARAMETER_ARGV')
        need(r['model_threads']==1 and r['probe']==dict(context_threads=1,model_threads=1,expected_threads=1), 'ACTUAL_RUNTIME')
        for n in set(sv)-{'rtl/'+n for n in b['files']}:
            text=files[n].decode()
            need('always' not in text and 'initial ' not in text, 'STATELESS_NATIVE_OBSERVER')
        checks=[]
        for step in m['steps']:
            row=next(x for x in r['steps'] if x['name']==step['name'])
            indexed=next(x for x in j['steps'] if x['name']==step['name'])
            out=Path(indexed['stdout_path']).read_bytes(); err=Path(indexed['stderr_path']).read_bytes()
            need(sha(out)==indexed['stdout_sha256']==row['sha256'] and sha(err)==indexed['stderr_sha256']==row['stderr_sha256'], 'RAW_LOG_JOIN')
            need(row['returncode']==step['expected_returncode']==indexed['actual_returncode'], 'EXACT_RETURN_CODE')
            if 'validator' in step:
                v=step['validator']; namespace={'__name__':'r11_review_captured_validator','__file__':str(ROOT/v['source'])}
                exec(compile(files[v['source']],str(ROOT/v['source']),'exec'),namespace)
                assets={k:files[n].decode() for k,n in v.get('assets',{}).items()}
                result=namespace[v['function']](out.decode(),err.decode(),row['returncode'],v['config'],assets)
                need(result['status']=='PASS_expected_contracts','CAPTURED_TYPED_VALIDATOR_REPLAY')
            else:
                need(out.decode()==step['expected_stdout'] and err.decode()==step['expected_stderr'],'EXACT_NATIVE_FOOTER')
            checks.append(dict(name=step['name'],actual_returncode=row['returncode'],stdout_sha256=sha(out),stderr_sha256=sha(err)))
        jobs.append(dict(id=j['id'],gate=j['gate'],report=j['report'],selected_manifest=j['selected_manifest'],
                         selected_archive_sha256=pkg['sha256'],source_count=len(files),compiled_sv_count=len(sv),steps=checks))
    ledger=json.loads(read_ref(index['own_healthy_source_native_ledger']))
    for count in (2,100,1000,1911814):
        c=calendar(count)
        need(all(ledger['calendars'][str(count)][k]==v for k,v in c.items()),'INDEPENDENT_CALENDAR:'+str(count))
        if count!=1911814:
            v=ledger['native'+str(count)]['measurements']
            need(v['warm_edges']==c['warm_edges'] and v['done_edges']==c['publication_edges'] and v['joint_cycles']==c['full_read_completion_cycles'],'ACTUAL_NATIVE_CALENDAR_JOIN')
    failure=index['retained_failure']; read_ref(failure['done']); bad=json.loads(read_ref(failure['report']))
    need(any(x.get('returncode')==1 for x in bad['steps']),'V2_FAILURE_PRESERVED')
    return dict(schema='r11-scoped-review-replay-v1',status='PASS_READ_ONLY_SOURCE_BINDINGS_EIGHT_NATIVE_LOGS_AND_OWN_CALENDAR',
                index=dict(path=str(INDEX),sha256=INDEX_PIN),jobs=jobs,ledger=index['own_healthy_source_native_ledger'],
                sample=calendar(1911814),production58_source_reproduced=True,closure_only_literal=True,
                no_native_rerun=True,no_full_N_numeric_locally=True,no_clock_or_layout_review=True)


if __name__=='__main__':
    print(json.dumps(replay(),indent=2))
