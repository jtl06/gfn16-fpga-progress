"""Independent raw evidence, arithmetic and tamper audits; no HDL/binary run."""
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import verify_root_recurrence27_periodmask_pair_offline as v

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'results/throughput-20260929/root-recurrence27-periodmask-pair-l64-p1-v2'
V1=ROOT/'results/throughput-20260929/root-recurrence27-periodmask-pair-l64-p1-v1'
STAGE=ROOT/'results/throughput-20260929/root-recurrence27-periodmask-pair-stage-l64-p1-v2'
COUNTS=dict(lanes=64,cases=322,runs=644,responses=594150,checked_cycles=745549,
            bubbles=148823,seed_checks=61251,aborts=117,rejects=124,pair_checks=1616690)


def fixture():
    return json.loads((RESULT/'report.json').read_text()),json.loads((RESULT/'approved-manifest.json').read_text())


def footer(counts=COUNTS):return 'PASS '+' '.join(f'{key}={counts[key]}' for key in v.FOOTER_KEYS)+'\n'


class PeriodmaskOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.members=v.archive(RESULT/'sources.tar.gz',v.SOURCE_PINS)
        cls.generated=v.archive(RESULT/'generated-sources.tar.gz')

    def test_actual_native_full_offline_audit_not_binary_execution(self):
        actual=v.verify(RESULT)
        self.assertEqual(actual['status'],'verified_component_pair')
        self.assertEqual(actual['normal_counts'],COUNTS)
        self.assertEqual(actual['checked_root_words'],3666546)
        self.assertEqual((actual['source_members'],actual['compiled_files'],actual['generated_members'],actual['artifacts']),(20,5,17,10))
        self.assertEqual(actual['report_sha256'],'89d50ed446849e4bf56b3425e2ee05803cd7815edcc84b3a11f18ba8a6e820ac')
        self.assertIn('no whole-core integration',actual['limitation'])
        self.assertIn('No binary executed',actual['limitation'])

    def test_frozen_stage_native_sources_and_exact_delta(self):
        self.assertEqual(v.sha(STAGE/'manifest.json'),v.MANIFEST_SHA)
        self.assertEqual(v.sha(STAGE/'source.tar.gz'),v.STAGE_ARCHIVE_SHA)
        self.assertEqual(v.sha(STAGE/'vectors.txt'),v.VECTOR_SHA)
        self.assertEqual(v.archive(STAGE/'source.tar.gz',v.SOURCE_PINS,'fpga/'),self.members)
        for name,value in v.SOURCE_PINS.items():self.assertEqual(v.sha(ROOT/name),value)
        v.source_delta(self.members)

    def test_cached_mask_configuration_reset_and_pipeline_delta_cannot_change(self):
        name='rtl/kernel/genefer_root_recurrence27_periodmask.sv'
        for old,new in ((b'position=issued&repeat_mask;',b'position=issued;'),
                        (b"repeat_mask<=17'h1ffff",b"repeat_mask<=17'h0"),
                        (b"repeat_mask<=config_period-17'd1",b'repeat_mask<=config_period'),
                        (b'issued<=0;',b'issued<=1;')):
            changed=dict(self.members);self.assertIn(old,changed[name]);changed[name]=changed[name].replace(old,new)
            with self.subTest(old=old),self.assertRaises(ValueError):v.source_delta(changed)

    def test_all_eleven_comparator_outputs_must_be_present_and_fatal(self):
        name='rtl/tb/'+v.TOP+'.sv'
        for port in v.OUTPUTS:
            changed=dict(self.members);old=f'({port} !== baseline_{port})'.encode()
            changed[name]=changed[name].replace(old,b"1'b0")
            with self.subTest(port=port),self.assertRaises(ValueError):v.source_delta(changed)
        name='rtl/tb/'+v.BENCH+'.cpp'
        for old,new in ((b'd.eval();compare();',b'd.eval();'),
                        (b'throw std::runtime_error("baseline/candidate port mismatch")',b'pair_checks++'),
                        (b'    return 0;\n}catch',b'}catch'),
                        (b'd.config_period=(elapsed&1) ? 0u : 131071u;',b'd.config_period=0;'),
                        (b'c.name.rfind("period-",0)==0',b'false')):
            changed=dict(self.members);self.assertIn(old,changed[name]);changed[name]=changed[name].replace(old,new)
            with self.subTest(old=old),self.assertRaises(ValueError):v.source_delta(changed)

    def test_pinned_compilation_closure_and_ancestor_names_cannot_change(self):
        for name in ('rtl/kernel/genefer_ntt_banked27_prefetch_r2_periodmask_engine.sv',
                     'rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_broadcast_periodmask_engine.sv',
                     'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_periodmask.sv',
                     'rtl/tb/'+v.BENCH+'_threaded.cpp'):
            changed=dict(self.members);changed[name]+=b'\n'
            with self.subTest(name=name),self.assertRaises(ValueError):v.source_delta(changed)
        for change in ('omit','extra','digest'):
            r,m=fixture()
            if change=='omit':r['sources'].pop(v.RUNNER)
            elif change=='extra':r['sources']['reference/unlisted.py']='0'*64
            else:r['sources'][v.RUNNER]='0'*64
            with self.subTest(change=change),self.assertRaises(ValueError):v.metadata(r,m)

    def test_standard_mersenne_twister_seed_and_twist_vectors(self):
        rng=v.MT19937(5489)
        self.assertEqual([rng.next() for _ in range(10)],
            [3499211612,581869302,3890346734,3586334585,545404204,4161255391,3922919429,949333985,2715962298,1323567403])
        # This extends over three twist boundaries and protects event-counter
        # determinism independently of the observed normal footer.
        rng=v.MT19937(5489);values=[rng.next() for _ in range(2000)]
        self.assertEqual((values[623],values[624],values[999]),(4020325887,4178893912,1341017984))

    def test_fresh_integer_geometry_vectors_and_exact_event_counters(self):
        raw=(RESULT/'vectors.txt').read_bytes();coverage=v.audit_vectors(raw)
        self.assertEqual(coverage,fixture()[1]['vectors'])
        self.assertEqual(coverage['legal_periods'],[0]+[1<<i for i in range(17)])
        self.assertEqual(v.expected_counts(coverage['cases']),COUNTS)
        self.assertEqual(sum(c['name'].startswith('period-') for c in coverage['cases']),18)
        self.assertEqual(coverage['case_count'],322)

    def test_wrong_expected_root_is_rejected_by_arithmetic_not_only_hash(self):
        raw=(RESULT/'vectors.txt').read_bytes();lines=raw.splitlines(keepends=True)
        # The first geometry root is recomputed before any global vector pin
        # check in audit_vectors; corrupt one otherwise well-formed word.
        lines[2]=b'1\n'
        with self.assertRaisesRegex(ValueError,'ordinary-integer vector record mismatch'):
            v.audit_vectors(b''.join(lines))

    def test_targeted_period_rows_use_direct_powers_not_candidate_mask(self):
        cases=[case for case in v.independent_cases() if case['name'].startswith('period-')]
        p=v.PROFILE['p']
        for case in cases:
            state=[row[0] for row in case['seeds']]
            for issued,row in enumerate(case['rows']):
                if case['period'] and issued%case['period']==0:state=[x[0] for x in case['seeds']]
                context=issued%len(state);self.assertEqual(row[0],state[context])
                if case['period']==0 or case['period']>4:state[context]=state[context]*7%p

    def test_footer_complete_exact_counters_not_positive_thresholds(self):
        self.assertEqual(v.check_normal(footer(),COUNTS),COUNTS)
        for key in COUNTS:
            changed=dict(COUNTS);changed[key]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):v.check_normal(footer(changed),COUNTS)
        weak=dict(COUNTS);weak['pair_checks']=2*weak['checked_cycles']
        with self.assertRaises(ValueError):v.check_normal(footer(weak),COUNTS)
        for text in (footer()+footer(),footer()+'ignored\n',footer().replace('PASS','FAIL')):
            with self.subTest(text=text[-20:]),self.assertRaises(ValueError):v.check_normal(text,COUNTS)

    def test_typed_metadata_failed_steps_and_resource_scope(self):
        for change in ('failed','error','bool-exit','threads','affinity','memory','cores','cpu-unlimited','duplicate-step',
                       'profile-bool','wrong-field','wrong-manifest','wrong-unit','nan-seconds','tool'):
            r,m=fixture()
            if change=='failed':r['status']='running'
            elif change=='error':r['error']='failed'
            elif change=='bool-exit':r['steps'][0]['returncode']=False
            elif change=='threads':r['model_threads']=True
            elif change=='affinity':r['limits']['affinity']=[0,1]
            elif change=='memory':r['limits']['memory_max_bytes']=7<<30
            elif change=='cores':r['limits']['physical_cores']=[[0,0],[0,0]]
            elif change=='cpu-unlimited':r['limits']['cpu_max']=['max','100000']
            elif change=='duplicate-step':r['steps'].append(deepcopy(r['steps'][-1]))
            elif change=='profile-bool':r['profile']['field']=True
            elif change=='wrong-field':r['profile']['field']=2
            elif change=='wrong-manifest':r['manifest_sha256']='0'*64
            elif change=='wrong-unit':r['limits']['cgroup']='/other.service'
            elif change=='nan-seconds':r['steps'][0]['seconds']=float('nan')
            else:r['tool_executable_sha256']['/usr/bin/python3.14']='0'*64
            with self.subTest(change=change),self.assertRaises(ValueError):v.metadata(r,m)

    def test_exact_native_commands_and_return_warning_flag(self):
        for change in ('top','thread','width','wrapper','extra','return-flag','probe','normal'):
            r,m=fixture();steps=v.metadata(r,m);argv=steps['build']['command']
            if change=='top':argv[9]='genefer_root_recurrence27'
            elif change=='thread':argv[7]='2'
            elif change=='width':argv[10]='-GLANES=16'
            elif change=='wrapper':argv[-1]=argv[-1].replace('_v2_threaded','_threaded')
            elif change=='extra':argv.append('unlisted.sv')
            elif change=='return-flag':argv[15]=argv[15].replace('-Werror=return-type ','')
            elif change=='probe':steps['probe']['command'][0]='/wrong/model'
            else:steps['normal']['command'].append('extra')
            with self.subTest(change=change),self.assertRaises(ValueError):v.commands(r,steps)

    def test_generated_width_context_strict_flags_and_compiled_wrapper(self):
        build=(RESULT/'build.log').read_text();v.generated_contract(self.generated,build)
        for change in ('width','threads','context','flags','unit','duplicate','suppression'):
            members=dict(self.generated);log=build;prefix='V'+v.TOP
            if change=='width':members[prefix+'.h']=members[prefix+'.h'].replace(b'2047,0,64',b'511,0,16')
            elif change=='threads':members[prefix+'.cpp']=members[prefix+'.cpp'].replace(b'threads() const { return 1;',b'threads() const { return 2;')
            elif change=='context':members[prefix+'.h']=members[prefix+'.h'].replace(b'VerilatedContext* contextp',b'const char* contextp')
            elif change=='flags':members[prefix+'.mk']=members[prefix+'.mk'].replace(b'-Werror=return-type ',b'')
            elif change=='unit':log=log.replace('_v2_threaded.cpp','_threaded.cpp')
            elif change=='duplicate':log+=next(line+'\n' for line in build.splitlines() if '-c -o '+v.BENCH+'_threaded.o' in line)
            else:log=log.replace('-Werror=return-type','-Werror=return-type -UTEST_LANES',1)
            with self.subTest(change=change),self.assertRaises(ValueError):v.generated_contract(members,log)

    def test_archive_unsafe_duplicate_link_extra_and_hash_members(self):
        for change in ('traversal','absolute','duplicate','link','extra','digest'):
            with tempfile.TemporaryDirectory() as temporary:
                path=Path(temporary)/'bad.tar.gz'
                with tarfile.open(path,'w:gz') as stream:
                    entries=[('ok',b'good')]
                    if change=='traversal':entries=[('../bad',b'x')]
                    elif change=='absolute':entries=[('/bad',b'x')]
                    elif change=='duplicate':entries+=[('ok',b'good')]
                    elif change=='extra':entries+=[('extra',b'x')]
                    for name,data in entries:
                        entry=tarfile.TarInfo(name);entry.size=len(data);stream.addfile(entry,io.BytesIO(data))
                    if change=='link':
                        entry=tarfile.TarInfo('link');entry.type=tarfile.SYMTYPE;entry.linkname='ok';stream.addfile(entry)
                pins={'ok':v.digest(b'bad' if change=='digest' else b'good')}
                with self.subTest(change=change),self.assertRaises(ValueError):v.archive(path,pins)

    def test_raw_artifact_hash_and_role_tamper_rejected(self):
        for change in ('normal','role','hash','generated'):
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)/'evidence';shutil.copytree(RESULT,root)
                r=json.loads((root/'report.json').read_text())
                if change=='normal':(root/'normal.log').write_text('PASS incomplete\n')
                elif change=='role':r['artifacts']['unused.log']='0'*64
                elif change=='hash':r['artifacts']['probe.log']='0'*64
                else:r['generated_source_sha256']['V'+v.TOP+'.cpp']='0'*64
                (root/'report.json').write_text(json.dumps(r))
                with self.subTest(change=change),self.assertRaises(ValueError):v.verify(root)

    def test_probe_boolean_and_report_footer_forgery_rejected(self):
        with self.assertRaises(ValueError):v.strict_equal(dict(context_threads=True),dict(context_threads=1),'probe')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'evidence';shutil.copytree(RESULT,root)
            r=json.loads((root/'report.json').read_text());r['normal_counts']['pair_checks']-=1
            (root/'report.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,'reported/raw normal counters'):v.verify(root)

    def test_failed_v1_is_never_relabelled_and_no_candidate_import(self):
        with self.assertRaises(ValueError):v.verify(V1)
        source=Path(v.__file__).read_text()
        for token in ('import subprocess','import root_recurrence27_periodmask_vectors',
                      'import prefetch_r2_periodmask_structure','import root_recurrence27_periodmask_pair_v2_regression'):
            self.assertNotIn(token,source)
        with patch.object(v,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'oracle source pin'):v.integer_oracle()


if __name__=='__main__':unittest.main()
