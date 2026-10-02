"""Exact source and cached-mask model checks; no HDL tools or remote calls."""
from pathlib import Path
import unittest
from unittest.mock import patch
from fpga.reference import prefetch_r2_periodmask_structure as s

ROOT=Path(__file__).resolve().parents[1]


class PeriodMaskTests(unittest.TestCase):
    def test_exact_isolated_source_chain_and_bench(self):
        self.assertEqual(len(s.validate_files(ROOT)),5)
        for new in s.NAMES.values():
            text=(ROOT/'rtl/kernel'/(new+'.sv')).read_text()
            self.assertNotIn('orient8',text)
            self.assertNotIn('rootfused',text)
            self.assertNotIn('rowcompact',text)

    def test_frozen_ancestor_and_mutated_latch_rejected(self):
        original=(ROOT/'rtl/kernel'/(s.RECURRENCE+'.sv')).read_text()
        with self.assertRaisesRegex(ValueError,'frozen ancestor'):s.expected(s.RECURRENCE,original+'\n')
        target=ROOT/'rtl/kernel'/(s.NAMES[s.RECURRENCE]+'.sv')
        read=Path.read_text;mutant=target.read_text().replace("config_period-17'd1","config_period")
        def changed(path,*args,**kwargs):return mutant if path==target else read(path,*args,**kwargs)
        with patch.object(Path,'read_text',changed),self.assertRaisesRegex(ValueError,'unreviewed period-mask'):
            s.validate_files(ROOT)

    def test_all_legal_periods_and_all_17bit_issued_values(self):
        count=0
        for period in s.LEGAL_PERIODS:
            mask=s.cached_mask(period)
            for issued in range(1<<17):
                old=s.old_position(period,issued)
                # Modulo is an independent oracle for valid power-of-two periods.
                expected=issued%period if period else issued
                if old!=expected or issued&mask!=expected:self.fail((period,issued,old,expected))
                count+=1
        self.assertEqual(count,2359296)

    def test_every_17bit_period_mask_on_all_input_bit_basis_vectors(self):
        # Bitwise AND is independently determined by these 17 basis vectors.
        # Cover rejected encodings as algebra, without treating them as starts.
        values=(0,s.MASK)+tuple(1<<bit for bit in range(17));count=0
        for period in range(1<<17):
            mask=s.cached_mask(period)
            for issued in values:
                old=s.old_position(period,issued)
                if old!=issued&mask:self.fail((period,issued))
                count+=1
        self.assertEqual(count,2490368)

    def test_zero_and_maximum_width_cases(self):
        self.assertEqual(s.cached_mask(0),0x1ffff)
        self.assertEqual(s.cached_mask(65536),0xffff)
        self.assertEqual(s.old_position(0,65536),65536)
        self.assertEqual(s.old_position(65536,65536),0)
        self.assertNotEqual(65536&s.cached_mask(0),65536&0xffff)
        self.assertNotEqual(9&s.cached_mask(8),9&8)

    def test_configuration_validation_all_period_encodings(self):
        for lanes in (1,64):
            seeds=((1<<(4*lanes))-1,)*2
            accepted=[period for period in range(1<<17)
                      if s.config_valid(dict(period=period,seed_valid=seeds),lanes)]
            self.assertEqual(accepted,list(s.LEGAL_PERIODS))
        for field in (104857601,69206017,67239937):
            for bad in (dict(groups=0),dict(groups=65537),dict(active=0),dict(active=65),dict(step=field)):
                event=dict(seed_valid=((1<<256)-1,)*2);event.update(bad)
                self.assertFalse(s.config_valid(event,p=field))

    def sequence(self,period,bank=0):
        seeds=((1<<256)-1,)*2
        events=[dict(reset=True),dict(start=True,period=period,groups=9,bank=bank,seed_valid=seeds)]
        for issued in range(9):
            events.append(dict(start=True,period=(131071 if issued%2 else 0),groups=0,request=False))
            events.append(dict(start=True,period=(0 if issued%2 else 1),request=True,available=True,bypass=True))
        events.extend(dict(start=True,period=3,request=True) for _ in range(4))
        events.append(dict(start=True,period=3,seed_valid=seeds))
        events.append(dict(start=True,period=0,bank=1-bank,groups=1,seed_valid=seeds))
        events.extend([dict(request=True),{},{},{},{}])
        return events

    def test_configuration_latching_bubbles_busy_starts_drain_and_bank_switch(self):
        for period in s.LEGAL_PERIODS:
            for bank in (0,1):
                trace=s.config_trace(self.sequence(period,bank))
                rows=[r for r in trace if not r['reset']]
                self.assertTrue(all(r['old_position']==r['new_position'] and r['old_ready']==r['new_ready'] for r in rows))
                self.assertEqual([r['bank'] for r in rows if r['accepted']],[bank,1-bank])
                self.assertEqual(sum(r['error'] for r in rows),1)
                self.assertEqual(next(r['mask'] for r in rows if r['error']),s.cached_mask(period))
                self.assertEqual(sum(r['done'] for r in rows),3)
                self.assertEqual(sum(r['state']=='DRAIN' for r in rows),8)

    def test_seed_bank_eligibility_and_rejected_start_hold_mask(self):
        valid=(1<<256)-1
        self.assertTrue(s.config_valid(dict(bank=1,seed_valid=(0,valid))))
        self.assertFalse(s.config_valid(dict(bank=0,seed_valid=(0,valid))))
        trace=s.config_trace(self.sequence(8)+[dict(start=True,period=32,seed_valid=(0,0))])
        self.assertTrue(trace[-1]['error']);self.assertEqual(trace[-1]['mask'],s.MASK)
        for depth in range(1,10):
            events=self.sequence(8)[:2+depth]+[dict(reset=True),dict(start=True,period=8,seed_valid=(0,0))]
            rows=s.config_trace(events)
            self.assertEqual(rows[-2]['issued'],0);self.assertEqual(rows[-2]['mask'],s.MASK)
            self.assertTrue(rows[-1]['error']);self.assertEqual(rows[-1]['state'],'IDLE')

    def test_wrong_live_or_zero_mask_latches_are_detectable(self):
        for kw in (dict(wrong_busy_latch=True),dict(wrong_zero_mask=True)):
            rows=s.config_trace(self.sequence(0),**kw)
            self.assertTrue(any(not r['reset'] and r['old_position']!=r['new_position'] for r in rows))

    def test_pipeline_and_seed_arbitration_remain_exact(self):
        old=(ROOT/'rtl/kernel'/(s.RECURRENCE+'.sv')).read_text()
        new=(ROOT/'rtl/kernel'/(s.NAMES[s.RECURRENCE]+'.sv')).read_text()
        for line in old.splitlines():
            if any(token in line for token in ('assign bypass=','assign seed_access=','assign seed_legal=',
                'context_value[context_pipe[3]]','context_pipe[c]<=','available[context_id]<=','drain_left<=4',
                'seed_valid[0][c]<=0','assign current_root[j]=','bypass ? update_result[j]')):
                self.assertIn(line,new)
        self.assertNotIn('repeat_period',new)
        self.assertEqual(new.count('repeat_mask<='),2)


if __name__=='__main__':unittest.main()
