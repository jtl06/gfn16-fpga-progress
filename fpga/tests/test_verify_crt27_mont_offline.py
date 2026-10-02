"""Independent CRT27 G2 evidence and tamper tests; never execute HDL/binaries."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import verify_crt27_mont_offline as v

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results/throughput-20260929'
POSITIVE=RESULTS/'crt27-mont-positive-v1'
NEGATIVE=RESULTS/'crt27-mont-mutations-v1'
STAGE=RESULTS/'crt27-mont-mutation-stage-v1'
COUNTS=dict(cycles=1413219,accepted=1005119,baseline_checked=1003268,candidate_checked=1004659,
    matched=1003268,baseline_canceled=1851,candidate_canceled=460,hold_checks=818511,async_checks=652,
    port_checks=5653528,resets=163,bubbles=408100,discarded_partial=1851)


def footer(row=COUNTS):return 'PASS '+' '.join(f'{key}={row[key]}' for key in v.FOOTER)+'\n'


def rehash_log(root,report,name,text):
    (root/(name+'.log')).write_text(text)
    value=v.sha(root/(name+'.log'));report['artifacts'][name+'.log']=value
    next(step for step in report['steps'] if step['name']==name)['sha256']=value


class CRTMontOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coverage=v.audit_vectors(POSITIVE/'vectors.txt')
        cls.report=json.loads((NEGATIVE/'report.json').read_text())
        cls.sources=v.common().archive(NEGATIVE/'sources.tar.gz',v.PINS)

    def test_actual_complete_G2_evidence_audit(self):
        result=v.verify(NEGATIVE,POSITIVE)
        self.assertEqual(result['status'],'verified_G2_component_correctness_and_required_mutation_sensitivity')
        self.assertEqual(result['counts'],COUNTS)
        self.assertEqual((result['source_members'],result['artifacts'],result['builds'],result['generated_members']),(11,80,8,120))
        self.assertEqual(result['report_sha256'],'551d5365dbd8059a372c9bed26fc860b47191a72b596e4f911af862753c3902e')
        self.assertEqual(result['mutations']['cb-off-one']['returncode'],1)
        self.assertEqual(result['mutations']['center-ge']['returncode'],1)
        self.assertEqual(result['mutations']['t2m3-removed']['returncode'],-6)
        self.assertIn('No archived binary executed',result['limitation'])
        self.assertIn('No G3 resources',result['limitation'])

    def test_fresh_vector_seed_arithmetic_and_transaction_counts(self):
        self.assertEqual(self.coverage['counts'],COUNTS)
        self.assertEqual(self.coverage,json.loads((STAGE/'manifest.json').read_text())['vectors'])
        self.assertEqual(self.coverage['random_accepted'],1000000)
        self.assertEqual(self.coverage['categories']['random_bubble'],401142)
        self.assertEqual(self.coverage['reset_ages'],list(range(61)))
        self.assertEqual(COUNTS['accepted'],COUNTS['baseline_checked']+COUNTS['baseline_canceled'])
        self.assertEqual(COUNTS['accepted'],COUNTS['candidate_checked']+COUNTS['candidate_canceled'])
        self.assertEqual(COUNTS['hold_checks'],2*COUNTS['cycles']-COUNTS['baseline_checked']-COUNTS['candidate_checked'])

    def test_integer_center_and_all_residue_inverses(self):
        self.assertEqual(v.M,v.PRIMES[0]*v.PRIMES[1]*v.PRIMES[2])
        for value in (0,1,-1,v.HALF-1,v.HALF,v.HALF+1,-v.HALF-1,v.M,v.M+1):
            residues=tuple(value%prime for prime in v.PRIMES);expected=value%v.M
            if expected>v.HALF:expected-=v.M
            self.assertEqual(v.direct_crt(residues),expected)
        for index,prime in enumerate(v.PRIMES):
            for value in (-1,prime,True):
                row=[0,0,0];row[index]=value
                with self.assertRaises(ValueError):v.direct_crt(row)

    def test_bad_expected_coefficient_rejected_without_global_hash_check(self):
        # Generate a small input file from the independently reconstructed
        # events; corrupt the first expected word, not metadata/hash labels.
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'vectors.txt'
            with path.open('w') as stream:
                stream.write('CRT27_MONT_V1 candidate_delay=15 frozen_delay=60 coefficient_bits=96\n')
                first=True
                for event in v.expected_records(1):
                    if event[0]=='RESET':stream.write('RESET\n');continue
                    _,valid,residues,_=event;expected=v.direct_crt(residues) if valid else 0
                    if first:expected+=1;first=False
                    stream.write('STEP '+str(int(valid))+' '+' '.join(map(str,residues))+' '+str(expected)+'\n')
            with self.assertRaisesRegex(ValueError,'fresh independent CRT/input sequence mismatch'):v.audit_vectors(path,1)

    def test_frozen_closures_and_prepared_mutation_stage(self):
        self.assertEqual(len(v.PINS),11);self.assertEqual(len(v.original_pins()),9)
        self.assertEqual(v.sha(STAGE/'manifest.json'),v.MANIFEST_SHA)
        self.assertEqual(v.sha(STAGE/'source.tar.gz'),v.STAGE_ARCHIVE_SHA)
        self.assertEqual(v.common().archive(STAGE/'source.tar.gz',v.PINS,'fpga/'),self.sources)
        for name,value in v.PINS.items():self.assertEqual(v.sha(ROOT/name),value)

    def test_literal_independent_mutation_transformations(self):
        original=self.sources[v.CANDIDATE].decode();derived=v.derived_sources(original)
        self.assertEqual(len(derived),7)
        for name,text in derived.items():self.assertEqual((NEGATIVE/name).read_text(),text)
        self.assertEqual(derived['control-center-ge.sv'],original)
        self.assertEqual(derived['control-t2m3-removed.sv'],original)
        self.assertNotIn('CRT27_CONSTANT_CHECK_BEGIN',derived['control-cb-off-one.sv'])
        self.assertIn('CRT27 Montgomery constants',derived['mutant-active-cb-guard.sv'])
        for name in ('mutant-cb-off-one.sv','control-cb-off-one.sv'):
            for token in ('noncanonical CRT27 input','CRT27 Montgomery valid alignment','CRT27 t2_mod3 bound','CRT27 value bound'):
                self.assertIn(token,derived[name])
        with self.assertRaises(ValueError):v.derived_sources(original+'\n')

    def test_exact_footer_all_counts_and_no_threshold_shortcut(self):
        self.assertEqual(v.check_footer(footer(),COUNTS),COUNTS)
        for key in COUNTS:
            row=dict(COUNTS);row[key]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):v.check_footer(footer(row),COUNTS)
        for text in (footer()+footer(),footer()+'ignored\n',footer().replace('PASS','FAIL')):
            with self.assertRaises(ValueError):v.check_footer(text,COUNTS)

    def test_probe_bool_thread_and_delay_are_rejected(self):
        good=dict(context_threads=1,model_threads=1,candidate_delay=15,frozen_delay=60,coefficient_bits=96,
            p1=v.PRIMES[0],p2=v.PRIMES[1],p3=v.PRIMES[2])
        self.assertEqual(v.probe(json.dumps(good)),good)
        for key in good:
            bad=dict(good);bad[key]=True if key=='context_threads' else good[key]+1
            with self.subTest(key=key),self.assertRaises(ValueError):v.probe(json.dumps(bad))

    def test_typed_arithmetic_negative_is_not_constant_guard_or_crash(self):
        step=deepcopy(next(row for row in self.report['steps'] if row['name']=='reject-cb-off-one'))
        wanted=['CRT27_MONT_ARITHMETIC_SIGN_MISMATCH'];v.rejection(step,wanted[0]+'\n',wanted,True)
        for code,text in ((0,wanted[0]+'\n'),(True,wanted[0]+'\n'),(-6,wanted[0]+'\n'),(1,'CRT27 Montgomery constants\n'),(1,'free(): invalid pointer\n')):
            bad=deepcopy(step);bad['returncode']=code
            with self.subTest(code=code,text=text),self.assertRaises(ValueError):v.rejection(bad,text,wanted,True)

    def test_internal_bound_rejection_is_distinct_and_not_coefficient_claim(self):
        step=next(row for row in self.report['steps'] if row['name']=='reject-t2m3-removed')
        log=(NEGATIVE/step['log']).read_text();v.rejection(step,log,['CRT27 t2_mod3 bound','noncanonical Montgomery27 input'])
        self.assertIn('mont_b3',log)
        with self.assertRaises(ValueError):v.rejection(step,log,['CRT27_MONT_ARITHMETIC_SIGN_MISMATCH'],True)

    def test_resource_metadata_malformed_boolean_limits_rejected(self):
        for change in ('memory','affinity','cores','threads','quota','unit'):
            bad=deepcopy(self.report)
            if change=='memory':bad['limits']['memory_max_bytes']=True
            elif change=='affinity':bad['limits']['affinity']=[0,1]
            elif change=='cores':bad['limits']['physical_cores']=[[0,0],[0,0]]
            elif change=='threads':bad['model_threads']=True
            elif change=='quota':bad['limits']['cpu_max']=['max','100000']
            else:bad['limits']['cgroup']='/old-affinity-failed.service'
            with self.subTest(change=change),self.assertRaises(ValueError):v.resource_contract(bad,64,'gfn-crt27-mont-mutations-v2')

    def test_generated_context_widths_macros_and_actual_bench_compilation(self):
        members=v.common().archive(NEGATIVE/'generated-control-center-ge.tar.gz');log=(NEGATIVE/'build-control-center-ge.log').read_text()
        v.generated(members,log,v.SOURCE)
        for change in ('width','threads','flags','duplicate','macro'):
            altered=dict(members);text=log;prefix='V'+v.TOP
            if change=='width':altered[prefix+'.h']=altered[prefix+'.h'].replace(b'candidate_coefficient,95,0,3',b'candidate_coefficient,94,0,3')
            elif change=='threads':altered[prefix+'.cpp']=altered[prefix+'.cpp'].replace(b'threads() const { return 1;',b'threads() const { return 2;')
            elif change=='flags':altered[prefix+'.mk']=altered[prefix+'.mk'].replace(b'-Werror=return-type ',b'')
            elif change=='duplicate':text+=next(line+'\n' for line in log.splitlines() if '-c -o '+v.TOP+'.o' in line)
            else:text=text.replace('-DCRT27_CANDIDATE_DELAY=15','-DCRT27_CANDIDATE_DELAY=16',1)
            with self.subTest(change=change),self.assertRaises(ValueError):v.generated(altered,text,v.SOURCE)

    def test_cryptographic_raw_artifact_tamper_and_missing_control(self):
        for change in ('raw-log','extra-role','missing-control','derived-file','input-list','source-pin'):
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)/'negative';shutil.copytree(NEGATIVE,root);report=json.loads((root/'report.json').read_text())
                if change=='raw-log':(root/'normal-control-center-ge.log').write_text('PASS incomplete\n')
                elif change=='extra-role':report['artifacts']['unapproved.log']='0'*64
                elif change=='missing-control':report['steps']=[step for step in report['steps'] if step['name']!='normal-control-cb-off-one']
                elif change=='derived-file':(root/'control-cb-off-one.sv').write_text(self.sources[v.CANDIDATE].decode())
                elif change=='input-list':report['input_rejections'].pop()
                else:report['sources'][v.RUNNER]='0'*64
                (root/'report.json').write_text(json.dumps(report))
                with patch.object(v,'audit_vectors',return_value=self.coverage),self.subTest(change=change),self.assertRaises(ValueError):v.verify(root,POSITIVE)

    def test_rehashed_semantic_footer_negative_category_and_command_tamper(self):
        for change in ('footer','cb-guard','t2-category','build-command','reuse-control','bool-exit'):
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)/'negative';shutil.copytree(NEGATIVE,root);report=json.loads((root/'report.json').read_text())
                if change=='footer':
                    row=dict(COUNTS);row['candidate_checked']-=1;rehash_log(root,report,'normal-control-center-ge',footer(row))
                elif change=='cb-guard':rehash_log(root,report,'reject-cb-off-one','CRT27 Montgomery constants\n')
                elif change=='t2-category':report['mutations']['t2m3-removed']['category']='arithmetic_mismatch'
                elif change=='build-command':next(step for step in report['steps'] if step['name']=='build-control-center-ge')['command'][-1]='unlisted.cpp'
                elif change=='reuse-control':next(step for step in report['steps'] if step['name']=='normal-control-center-ge')['command'][0]=v.REMOTE+'/V'+v.TOP+'-pristine'
                else:report['steps'][0]['returncode']=False
                (root/'report.json').write_text(json.dumps(report))
                with patch.object(v,'audit_vectors',return_value=self.coverage),self.subTest(change=change),self.assertRaises(ValueError):v.verify(root,POSITIVE)

    def test_verifier_imports_no_CRT_runner_or_candidate_arithmetic(self):
        source=Path(v.__file__).read_text();tree=ast.parse(source)
        names=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):names.extend(alias.name for alias in node.names)
            elif isinstance(node,ast.ImportFrom):names.extend(alias.name for alias in node.names)
        self.assertFalse(any('crt27_mont_regression' in name or 'crt27_mont_mutation_regression' in name for name in names))
        self.assertNotIn('subprocess',names)
        self.assertNotIn('crt_mont(',source)
        with patch.object(v,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'generic offline archive helper'):v.common()


if __name__=='__main__':unittest.main()
