"""CRT positive/mutation gate contracts; ordinary Python only, no HDL tools."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import crt27_mont_regression as p
from fpga.reference import crt27_mont_mutation_regression as n

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results/throughput-20260929'
POSITIVE=RESULTS/'crt27-mont-positive-v1'
STAGE=RESULTS/'crt27-mont-positive-stage-v1'
NEGATIVE_STAGE=RESULTS/'crt27-mont-mutation-stage-v1'


def positive_footer(counts):return 'PASS '+' '.join(f'{key}={counts[key]}' for key in p.FOOTER_KEYS)+'\n'


class CRTMontGateTests(unittest.TestCase):
    def test_positive_frozen_nine_and_negative_eleven_closures(self):
        pins=p.source_pins(ROOT);self.assertEqual(len(pins),9)
        self.assertEqual(pins[p.RUNNER],n.POSITIVE_SHA)
        successor,_=n.source_pins(ROOT);self.assertEqual(len(successor),11)
        self.assertEqual({key:value for key,value in successor.items() if key not in (n.RUNNER,n.ANSWER)},pins)
        self.assertEqual(n.sha(STAGE/'manifest.json'),n.POSITIVE_MANIFEST_SHA)
        self.assertEqual(n.sha(STAGE/'source.tar.gz'),n.POSITIVE_STAGE_ARCHIVE_SHA)
        self.assertEqual(n.sha(POSITIVE/'report.json'),n.POSITIVE_REPORT_SHA)
        self.assertEqual(n.sha(ROOT/n.CANDIDATE),n.CANDIDATE_SHA)

    def test_plain_integer_crt_constants_and_reconstruction(self):
        self.assertEqual(p.PRIMES[0]*p.PRIMES[1]*p.PRIMES[2],p.M)
        for column,term in enumerate(p.TERMS):
            for row,prime in enumerate(p.PRIMES):self.assertEqual(term%prime,int(row==column))
        for r1 in (0,1,p.PRIMES[1]-1,p.PRIMES[1],p.PRIMES[2]-1,p.PRIMES[2],p.PRIMES[0]-1):
            for r2 in (0,1,p.PRIMES[1]-1):
                for r3 in (0,1,p.PRIMES[2]-1):
                    expected=p.direct_crt((r1,r2,r3))
                    self.assertTrue(-p.HALF<=expected<=p.HALF)
                    self.assertEqual(tuple(expected%prime for prime in p.PRIMES),(r1,r2,r3))

    def test_center_exact_rule_boundaries(self):
        for value in (0,1,-1,p.HALF-1,p.HALF,p.HALF+1,-p.HALF-1,-p.HALF,p.M-1,p.M,p.M+1):
            canonical=value%p.M;expected=canonical-p.M if canonical>p.HALF else canonical
            self.assertEqual(p.direct_crt(tuple(value%prime for prime in p.PRIMES)),expected)
        self.assertEqual(p.direct_crt(tuple(p.HALF%prime for prime in p.PRIMES)),p.HALF)

    def test_direct_crt_rejects_noncanonical_and_boolean_residues(self):
        for index,prime in enumerate(p.PRIMES):
            for value in (-1,prime,prime+1,1<<27,0xffffffff,True):
                row=[0,0,0];row[index]=value
                with self.subTest(index=index,value=value),self.assertRaises(ValueError):p.direct_crt(row)

    def test_distinct_exact_due_edges_and_reset_every_age(self):
        for age in range(61):
            events=p.EventCounts();events.reset();events.step(True)
            for _ in range(age):events.step(False)
            self.assertEqual(events.row['candidate_checked'],int(age>=15))
            self.assertEqual(events.row['baseline_checked'],int(age>=60))
            events.reset()
            self.assertEqual(events.row['candidate_canceled'],int(age<15))
            self.assertEqual(events.row['baseline_canceled'],int(age<60))
            self.assertEqual(events.row['matched'],int(age>=60))
            self.assertEqual(events.row['async_checks'],8)
            self.assertEqual(events.row['port_checks'],4*events.row['cycles']+8)
            self.assertFalse(any(events.queues))

    def test_full_positive_native_footer_against_integer_event_accounting(self):
        manifest=json.loads((STAGE/'manifest.json').read_text());report=json.loads((POSITIVE/'report.json').read_text())
        counts=p.check_normal((POSITIVE/'normal.log').read_text(),manifest['vectors'])
        self.assertEqual(counts,report['normal_counts'])
        self.assertEqual((counts['accepted'],counts['matched'],counts['cycles'],counts['resets']),(1005119,1003268,1413219,163))
        self.assertEqual(manifest['vectors']['random_accepted'],1000000)
        self.assertEqual(manifest['vectors']['categories']['cross_edges'],896)
        self.assertEqual(manifest['vectors']['categories']['center'],17)
        self.assertEqual(manifest['vectors']['categories']['t2m3_witness'],105)
        self.assertEqual(manifest['vectors']['reset_ages'],list(range(61)))
        self.assertEqual(n.sha(POSITIVE/'vectors.txt'),n.VECTOR_SHA)
        self.assertEqual((POSITIVE/'vectors.txt').stat().st_size,n.VECTOR_BYTES)
        self.assertEqual(report['status'],'passed_positive_only_mutations_pending')

    def test_positive_footer_rejects_missing_duplicate_changed_typed_counters(self):
        coverage=json.loads((STAGE/'manifest.json').read_text())['vectors'];counts=coverage['counts']
        for key in p.FOOTER_KEYS:
            bad=dict(counts);bad[key]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):p.check_normal(positive_footer(bad),coverage)
        for text in (positive_footer(counts)+positive_footer(counts),positive_footer(counts)+'ignored\n',positive_footer(counts).replace('PASS','FAIL')):
            with self.assertRaises(ValueError):p.check_normal(text,coverage)
        bad=deepcopy(coverage);bad['counts']['resets']=True
        with self.assertRaises(ValueError):p.check_normal(positive_footer(counts),bad)
        bad=deepcopy(coverage);bad['random_accepted']=999999
        with self.assertRaises(ValueError):p.check_normal(positive_footer(counts),bad)

    def test_generated_small_vectors_are_canonical_and_drained(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'vectors';coverage=p.write_vectors(path,random_cases=12)
            self.assertEqual(coverage['categories']['random_accepted'],12)
            self.assertEqual(coverage['reset_ages'],list(range(61)))
            self.assertEqual(coverage['counts']['accepted'],coverage['counts']['baseline_checked']+coverage['counts']['baseline_canceled'])
            self.assertEqual(coverage['counts']['accepted'],coverage['counts']['candidate_checked']+coverage['counts']['candidate_canceled'])
            for line in path.read_text().splitlines()[1:]:
                if line=='RESET':continue
                fields=line.split();self.assertEqual(len(fields),6);self.assertEqual(fields[0],'STEP')
                if fields[1]=='1':self.assertEqual(int(fields[5]),p.direct_crt(tuple(map(int,fields[2:5]))))

    def test_runtime_probe_typed_profile_and_threads(self):
        row=dict(context_threads=1,model_threads=1,candidate_delay=15,frozen_delay=60,coefficient_bits=96,
            p1=p.PRIMES[0],p2=p.PRIMES[1],p3=p.PRIMES[2])
        self.assertEqual(p.check_probe(json.dumps(row)),row)
        for key in row:
            bad=dict(row);bad[key]=True if key=='context_threads' else row[key]+1
            with self.subTest(key=key),self.assertRaises(ValueError):p.check_probe(json.dumps(bad))

    def test_exact_compile_context_warning_and_assertion_contract(self):
        command=p.compile_command(Path('/snapshot'),Path('/dev/shm/build'))
        self.assertEqual(command[4:8],['-j','2','--threads','1']);self.assertIn('--assert',command)
        self.assertIn('-GCANDIDATE_DELAY=15',command);self.assertIn('-GFROZEN_DELAY=60',command)
        self.assertIn('-Werror=return-type',command[command.index('-CFLAGS')+1].split())
        self.assertEqual(command[-6:],[str(Path('/snapshot')/name) for name in p.ORDER])
        cpp=(ROOT/'rtl/tb/crt3_27_mont_pair.cpp').read_text();sv=(ROOT/'rtl/tb/crt3_27_mont_pair.sv').read_text()
        for token in ('d{context}','context->threads(1)','return 0;','CRT27_MONT_ASYNC_RESET_MISMATCH',
                      'CRT27_MONT_COMBINATIONAL_PORT_MISMATCH','CRT27_MONT_INVALID_HOLD_MISMATCH','CRT27_MONT_TRANSACTION_INDEX_MISMATCH'):
            self.assertIn(token,cpp)
        self.assertIn('test_mode!=2',sv);self.assertIn('test_mode!=1',sv)
        self.assertNotIn('pair_mismatch',sv)

    def test_required_derivatives_literal_single_changes_and_approved_pins(self):
        text=(ROOT/n.CANDIDATE).read_text();manifest=json.loads((NEGATIVE_STAGE/'manifest.json').read_text())
        self.assertEqual(set(manifest['required_mutations']),set(n.MUTATIONS))
        for name in n.MUTATIONS:
            row=n.derivative(text,name);declared=manifest['required_mutations'][name]
            self.assertEqual(n.digest(row['control'].encode()),declared['control_sha256'])
            self.assertEqual(n.digest(row['mutant'].encode()),declared['mutant_sha256'])
            if name=='cb-off-one':
                self.assertEqual(row['control'],n.omit_constant_checker(text))
                self.assertEqual(row['mutant'],row['control'].replace("CB=32'd62755090;","CB=32'd62755091;"))
                self.assertNotIn('CRT27_CONSTANT_CHECK_BEGIN',row['control'])
            else:self.assertEqual(row['control'],text)
            for token in ('noncanonical CRT27 input','CRT27 Montgomery valid alignment','CRT27 t2_mod3 bound','CRT27 value bound'):
                self.assertIn(token,row['control']);self.assertIn(token,row['mutant'])
        for name in n.MUTATIONS:
            with self.assertRaises(ValueError):n.derivative(text+'\n',name)

    def test_typed_negative_classes_reject_untyped_abort_and_false_pass(self):
        token='CRT27_MONT_ARITHMETIC_SIGN_MISMATCH'
        self.assertEqual(n.typed_rejection(1,token,[token]),[token])
        self.assertEqual(n.typed_rejection(-6,'CRT27 t2_mod3 bound',['CRT27 t2_mod3 bound']),['CRT27 t2_mod3 bound'])
        for code,text in ((0,token),(False,token),(-6,'free(): invalid pointer'),(1,'compile failed'),(1,'CRT27 Montgomery constants')):
            with self.subTest(code=code,text=text),self.assertRaises(ValueError):n.typed_rejection(code,text,[token])

    def test_correction_witnesses_reach_threshold_and_center_mutant(self):
        inverse=pow(p.PRIMES[0],-1,p.PRIMES[1])
        for t2 in (p.PRIMES[2]-1,p.PRIMES[2],p.PRIMES[2]+1,p.PRIMES[1]-1):
            r1=1;r2=(r1+p.PRIMES[0]*t2)%p.PRIMES[1]
            actual=((r2-r1)%p.PRIMES[1])*inverse%p.PRIMES[1]
            self.assertEqual(actual,t2)
        centered=p.direct_crt(tuple(p.HALF%prime for prime in p.PRIMES))
        self.assertEqual(centered,p.HALF);self.assertNotEqual(centered,p.HALF-p.M)

    def test_negative_successor_preserves_original_positive_hash_and_archive(self):
        before=p.source_pins(ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            stage=Path(temporary)/'stage';manifest=n.prepare(stage)
            self.assertEqual(manifest['reused_vector_path'],str(n.VECTOR));self.assertEqual(len(manifest['sources']),11)
            self.assertFalse((stage/'vectors.txt').exists())
            with tarfile.open(stage/'source.tar.gz') as archive:
                self.assertEqual(len(archive.getmembers()),11)
                for member in archive:
                    self.assertTrue(member.isfile());name=member.name.removeprefix('fpga/')
                    self.assertEqual(n.digest(archive.extractfile(member).read()),manifest['sources'][name])
        self.assertEqual(p.source_pins(ROOT),before)

    def test_offhost_execution_rejects_before_subprocess(self):
        for module in (p,n):
            with patch.object(module.socket,'gethostname',return_value='not-aethia'),patch.object(module.subprocess,'Popen',side_effect=AssertionError('must not execute')):
                with self.assertRaisesRegex(ValueError,'aethia'):module.execute(Path('/tmp/out'),Path('/tmp/manifest'),'0'*64)

    def test_resource_and_fresh_control_rules_are_source_bound(self):
        source=Path(n.__file__).read_text()
        for token in ('64*MiB','10*GiB','768*MiB','2*GiB','p.execution_limits()','RLIMIT_AS,(6*GiB',
                      'LOCK.open','start_new_session=True','os.killpg','sha(VECTOR)==VECTOR_SHA',
                      "control=build('control-'+name,control_path)","'normal-control-'+name",'matched parent tool identity'):
            self.assertIn(token,source)
        self.assertNotIn("shutil.copyfile(VECTOR",source);self.assertNotIn("write_vectors(out/'vectors",source)
        self.assertIn("for role in ('baseline','candidate')",source)
        self.assertIn('(prime,prime+1,1<<27,0x80000001,0xffffffff)',source)


if __name__=='__main__':unittest.main()
