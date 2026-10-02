import json
import unittest
from fpga.reference import a10_native_roles_v1 as roles
from fpga.reference import core27_crtmont_prp_e2e_v1 as prp

class RoleTests(unittest.TestCase):
    def test_three_geometry_exact_counter_contract(self):
        for aw in (5,8,16):
            metrics=roles.engine_metrics(aw)
            for field in roles.FIELDS:
                stdout=f'A10_ENGINE_PASS aw={aw} field={field} cases=5 operations=15 residues={metrics["residues"]} cycles={metrics["cycles"]} profile_words=4\n'
                c=dict(role='engine',negative=None,aw=aw,field=field)
                r=roles.validate(stdout,'',0,c,{})
                self.assertFalse(r['promotion_allowed'])
                for output,error,code in [(stdout.replace('cases=5','cases=4'),'',0),(stdout,'oops',0),(stdout,'',1),(stdout+'extra\n','',0)]:
                    with self.assertRaises(ValueError):roles.validate(output,error,code,c,{})

    def test_typed_negative_specific_kind_phase_and_bound(self):
        for kind in ('root','form','normalization'):
            phase='inverse' if kind=='normalization' else 'forward'
            error=f'A10_NUMERIC_{kind.upper()}_MISMATCH phase={phase} index=1\n'
            c=dict(role='engine',negative=kind,aw=8,field=roles.FIELDS[0])
            self.assertFalse(roles.validate('',error,1,c,{})['promotion_allowed'])
            for out,err,code in [('','timeout\n',1),('',error,0),('oops',error,1),('',error.replace('index=1','index=256'),1)]:
                with self.assertRaises(ValueError):roles.validate(out,err,code,c,{})

    def fixture(self):
        _,oracle=prp.corpus();lines=[]
        for c in oracle['cases']:
            lines.append(f'E2E_RESULT case={c["index"]} base={c["base"]} class={c["classification"]} steps={c["operations"]} doubles={c["doubles"]} cycles={c["operations"]*200} prp={int(c["expected_prp"])} digits='+','.join(map(str,c['expected_digits'])))
        lines.append(f'E2E_PASS aw=5 cases=8 operations={oracle["operations"]} doubles={oracle["doubles"]} readbacks=8 cycles={oracle["operations"]*200}')
        return '\n'.join(lines)+'\n',dict(oracle=json.dumps(oracle))

    def test_small_e2e_bigint_controls_and_comparator(self):
        stdout,assets=self.fixture()
        r=roles.validate(stdout,'',0,dict(role='e2e1',negative=None),assets)
        self.assertEqual(len(r['cases']),8);self.assertFalse(r['promotion_allowed'])
        first=stdout.splitlines()[0]+'\n'
        self.assertFalse(roles.validate(first,'E2E_RESIDUE_MISMATCH case=0 digit=0\n',1,dict(role='e2e1',negative='comparator'),assets)['promotion_allowed'])
        for out,err,code in [(stdout,'',1),(stdout.replace('readbacks=8','readbacks=7'),'',0),(stdout+'extra\n','',0)]:
            with self.assertRaises(ValueError):roles.validate(out,err,code,dict(role='e2e1',negative=None),assets)
        bad=dict(oracle=assets['oracle'].replace('"n": 32','"n": 65536'))
        with self.assertRaisesRegex(ValueError,'A10_E2E_ORACLE_SCOPE'):roles.validate(stdout,'',0,dict(role='e2e1',negative=None),bad)

if __name__=='__main__':unittest.main()
