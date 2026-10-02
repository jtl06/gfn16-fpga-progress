"""Local source/model coverage only; no HDL or remote execution."""
from pathlib import Path
import hashlib
import re
import unittest
from fpga.reference import rowcompact_reset_probe_structure as s

ROOT=Path(__file__).resolve().parents[1]


class ResetProbeTests(unittest.TestCase):
    def test_exact_new_derivatives_and_frozen_vector_identity(self):
        self.assertEqual(len(s.validate_files(ROOT)),4)
        self.assertEqual(hashlib.sha256((ROOT/s.VECTOR).read_bytes()).hexdigest(),s.VECTOR_SHA)
        for name,digest in s.PINS.items():self.assertEqual(s.sha((ROOT/'rtl/kernel'/(name+'.sv')).read_text()),digest)

    def test_engine_functional_source_identical_outside_simulation(self):
        old=(ROOT/'rtl/kernel'/(s.ENGINE+'.sv')).read_text()
        new=(ROOT/'rtl/tb'/(s.NAMES[s.ENGINE]+'.sv')).read_text()
        remove=lambda text:re.sub(r'// synthesis translate_off.*?// synthesis translate_on','',text,flags=re.S)
        self.assertEqual(remove(new).replace(s.NAMES[s.ENGINE],s.ENGINE),remove(old))
        for counter in s.COUNTERS:
            self.assertEqual(new.count(counter+'<=0;'),1)
            self.assertEqual(new.count(counter+'<='+counter),1)
        self.assertIn('if(data_wa[b]!==legacy_row_tag[6][b]) $fatal(1,"compact row write address mismatch");',new)

    def test_observation_top_only_reads_selected_hierarchy(self):
        top=(ROOT/'rtl/tb'/(s.TOP+'.sv')).read_text()
        self.assertNotIn('always',top)
        self.assertNotIn('public_flat_rw',top)
        self.assertNotIn('force ',top)
        self.assertNotRegex(top,r'assign dut\.')
        self.assertEqual(top.count('assign probe_base['),3*8*7)
        self.assertEqual(top.count('assign probe_pair['),3*8*7)
        self.assertEqual(top.count('assign probe_bf_checks['),3)
        self.assertNotIn('data_q[',top)

    def test_matrix_exact_and_target_rows_independent(self):
        cases=s.matrix();self.assertEqual(len(cases),64)
        self.assertEqual(len({tuple(c.values()) for c in cases}),64)
        for case in cases:
            target=s.target(case)
            if case['kind']=='bf':
                # First DIF stage15: group0/1 map low fixed position bit1.
                base=target['group']<<1;orientation=(base>>1)&1
                row=(base|((1<<15) if ((target['bank']>>1)&1)^orientation else 0))>>7
                self.assertEqual(orientation,case['variant'])
            else:
                point=target['group']<<6;row=point>>7
                self.assertEqual(target['bank']//64,(point>>6)&1)
            self.assertEqual(row,target['row']);self.assertGreater(row,0)

    def test_each_reset_age_against_seven_slot_token_pipeline(self):
        for case in s.matrix():
            pipe=[None]*7;committed=[];token=s.target(case)['row']
            for edge in range(case['age']+1):
                if pipe[-1] is not None:committed.append(pipe[-1])
                pipe=[token if edge==0 else None]+pipe[:6]
            predicted=s.timing_model(case['age'])
            self.assertEqual(bool(committed),predicted['committed'])
            if case['age']<7:self.assertEqual(pipe[case['age']],token)
            pipe=[None]*7 # asynchronous reset before any further rising edge
            for _ in range(8):
                self.assertIsNone(pipe[-1]);pipe=[None]+pipe[:6]

    def test_full_recovery_counter_math(self):
        counts=s.expected_counts()
        self.assertEqual(counts,dict(bf=2097152,mul=196608,bf_nonzero=2093056,mul_nonzero=196224))
        self.assertEqual((counts['bf']+counts['mul'])*3,6881280)
        # For each bank, every row0..511 is written once per pass.
        self.assertEqual(sum(1 for bank in range(128) for row in range(512) if row!=0)*32,counts['bf_nonzero'])

    def test_bad_age_and_address_mutants_have_nonvacuous_shadow_witness(self):
        source=(ROOT/'rtl/tb'/(s.NAMES[s.ENGINE]+'.sv')).read_text()
        for kind,first in (('bad-age',1),('bad-address',0)):
            mutant=s.mutant(source,kind)
            self.assertNotEqual(mutant,source)
            self.assertEqual(mutant.count('$fatal(1,"compact row write address mismatch")'),1)
            for issued in range(first+1):
                correct=issued//2
                wrong=(issued+1)//2 if kind=='bad-age' else correct^1
                self.assertEqual(correct!=wrong,issued==first)
            # Earliest root-point witness writes the opposite bank half from
            # the read seven edges later, avoiding the collision monitor.
            self.assertNotEqual(first%2,(first+7)%2)

    def test_cpp_bounded_single_case_and_actual_event_observations(self):
        text=(ROOT/'rtl/tb/rowcompact_reset_probe.cpp').read_text()
        for token in ('context.threads(1)','--runtime-probe','--recover-only','edges<=500000','wait<100000',
                      'd.probe_issue==7&&d.probe_read==7','probe_ra[f]==target_row','E0 registered request missing',
                      'target E7 write missing','committed==(age==7?1u:0u)','d.rst_n=0;d.eval();reset_flags()',
                      'd.probe_bf_checks[f]==2097152','d.probe_mul_checks[f]==196608','recovery_cycles=41708'):
            self.assertIn(token,text)
        self.assertNotIn('ntt_cycles>=',text)
        self.assertNotIn('public-flat',text)

    def test_first_two_pinned_vector_transactions_suitable_for_cold_recovery(self):
        lines=(ROOT/s.VECTOR).read_text().splitlines()
        self.assertEqual(lines[0],'65536')
        start=lines.index('LOAD full-random 604832956')
        self.assertEqual(lines[start+2],'RUN full-random-s0-d0 0')
        self.assertEqual(lines[start+4],'RUN full-random-s1-d1 1')
        for offset in (1,3,5):self.assertEqual(len(lines[start+offset].split()),65536)


if __name__=='__main__':unittest.main()
