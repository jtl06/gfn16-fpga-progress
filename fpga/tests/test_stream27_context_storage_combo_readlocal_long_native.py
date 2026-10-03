import copy
import json
import math
import unittest
from fpga.reference import stream27_context_storage_combo_readlocal_long_native as pilot
from fpga.reference import stream27_context_storage_combo_readlocal_continuous as long


class OwnLongTests(unittest.TestCase):
    def test_role_same_rtl_and_cpp_exact_count_delta(self):
        p,pf=pilot.role(100,1)
        m,f=long.role()
        self.assertEqual({n:v for n,v in pf.items() if n.endswith('.sv')},
                         {n:v for n,v in f.items() if n.endswith('.sv')})
        self.assertEqual(pf[pilot.CPP],f[pilot.CPP])
        self.assertEqual(p['build'],m['build'])
        self.assertEqual(m['steps'][0]['name'],'normal-full-c2-combo-r4-continuous1000-percontext')
        self.assertEqual(p['steps'][0]['name'],long.PILOT_STEP)
        self.assertEqual(m['steps'][0]['validator']['source'],pilot.SELF)
        self.assertEqual(long.bits(100),[row[:100] for row in long.bits()])
        self.assertEqual(long.header(pf[pilot.HEADER]),f[pilot.HEADER])
        self.assertEqual(pilot.config(100,1)['doubles'],101)
        self.assertEqual(pilot.config(1000,1)['doubles'],1022)
        self.assertEqual(m['context_storage_combo_readlocal']['own_long']['own_calendar']['frames'],2000)

    def test_scalar_forecast_finite_and_margin(self):
        p=long.predict(100,200)
        self.assertTrue(p['fits_finite_shape'])
        self.assertEqual(p['continuous_command_seconds_estimate'],1750)
        self.assertFalse(long.predict(1000,1100)['fits_finite_shape'])
        for args in ((math.nan,200),(100,math.inf),(True,200),(200,100),(100,200,1.5)):
            with self.assertRaises(ValueError):long.predict(*args)

    def test_forecast_cannot_borrow_before_actual_own_pilot(self):
        # Pilot source preparation is allowed; actual forecast paths are only
        # the R4 report/gate/approved source, never an R2/R3 result.
        self.assertEqual(long.PILOT_ID,'s4-p16-c2-combo-r4-own100-serial-q1-v1')
        self.assertIn(long.PILOT_ID,str(long.PILOT_REPORT))
        self.assertIn(long.PILOT_ID,str(long.PILOT_GATE))
        if not long.PILOT_REPORT.exists():
            with self.assertRaises(FileNotFoundError):long.forecast(long.role()[0])
        for count in (True,2,999):
            with self.assertRaises(ValueError):pilot.config(count,1)
        with self.assertRaises(ValueError):pilot.config(100,2)

    def test_typed_pilot_scalar_output_and_malformed_counts(self):
        # Synthetic scalar-only parser fixtures, not native results or an
        # arithmetic oracle. Exact publication formula is source-grounded.
        count=100
        launches=[[204+k*8459 for k in range(count)],[4433+k*8459 for k in range(count)]]
        warm=[row[-1]+12558 for row in launches]
        release=-1;done=[]
        for edge in warm:
            release=max(edge+2,release+1)+4096+10*65536+6;done.append(release)
        row=dict(aw=16,p=16,contexts=2,bases=pilot.BASES,count_per_context=count,squares=200,
            descriptors=198,doubles=101,reads=262144,signed96=True,independent_reference=True,
            initial_resets=1,initial_load_words=131072,interval=8459,peer_live_reads=65536,model_threads=1,
            launches=launches,joint_cycles=release+65536,overlap_edges=1,done_edges=done,warm_edges=warm,
            setup_edges=[99,199],reference_seconds=2.0,model_seconds=8.0,seconds=10.0)
        def check(value,**kw):
            return pilot.validate('R84_C2_THREAD100_PASS '+json.dumps(value)+'\n',kw.get('stderr',''),
                                  kw.get('rc',0),pilot.config(count,1),{})
        self.assertEqual(check(row)['status'],'PASS_expected_contracts')
        for key,value in [('squares',100),('reads',65536),('initial_resets',2),('initial_load_words',262144),
                          ('model_threads',2),('descriptors',197),('signed96',1),('seconds',float('nan'))]:
            altered=copy.deepcopy(row);altered[key]=value
            with self.assertRaises(ValueError):check(altered)
        altered=copy.deepcopy(row);altered['launches'][1][71]+=1
        with self.assertRaises(ValueError):check(altered)
        altered=copy.deepcopy(row);altered['done_edges'][0]-=1
        with self.assertRaises(ValueError):check(altered)
        with self.assertRaises(ValueError):check(row,rc=True)
        with self.assertRaises(ValueError):check(row,stderr='tool failed')


if __name__=='__main__':unittest.main()
