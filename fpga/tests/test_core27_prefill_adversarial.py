import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import core27_prefill_adversarial_regression as gate
from fpga.reference import core27_prefill_aw5_v2_regression as normal
from fpga.reference import core27_prefetch_r2_regression as baseline
from fpga.reference import core27_prefill_mutant_sources as recipe

ROOT=Path(__file__).resolve().parents[1]


class AdversarialPreparation(unittest.TestCase):
    def test_exact_all_eight_pairs_and_control_deltas(self):
        self.assertEqual(recipe.NAMES,gate.MUTATION_NAMES)
        for name in recipe.NAMES:
            control,mutant,contract=recipe.pair_sources(ROOT,name)
            self.assertEqual(set(control),{recipe.CORE,recipe.CARRY,recipe.BRIDGE})
            self.assertEqual(set(control),set(mutant))
            self.assertTrue(contract['lines'])
            changed={k for k in control if control[k]!=mutant[k]}
            self.assertEqual(changed,{recipe.CORE,recipe.BRIDGE} if name in recipe.MUTANTS else {recipe.CARRY})
            self.assertEqual(recipe.bridge(control[recipe.CORE]),control[recipe.BRIDGE])
            self.assertEqual(recipe.bridge(mutant[recipe.CORE]),mutant[recipe.BRIDGE])
            if name in recipe.TEE_MUTANTS:
                for sources in (control,mutant):
                    self.assertNotIn('T5_EMIT_SIGNED32_REPRESENTATION',sources[recipe.CARRY])
                    self.assertIn('T5_EMIT_NOT_ACTUAL_COMMIT',sources[recipe.CARRY])

    def test_pair_commands_are_exactly_matched_except_executable(self):
        for name in recipe.NAMES:
            a=recipe.command('/fresh-control','/vectors',name)
            b=recipe.command('/mutant','/vectors',name)
            self.assertEqual(a[1:],b[1:])
        self.assertEqual(recipe.command('/e','/v','late_host_error')[1:],['--tail-error','/v','6','final','control'])
        self.assertEqual(recipe.command('/e','/v','eligibility_after_load')[1],'--reload-control')

    def test_all_typed_fatals_reject_wrong_status_scope_line_and_message(self):
        for name in recipe.NAMES:
            contract=recipe.pair_sources(ROOT,name)[2]
            line=contract['lines'][0]
            log=f"[0] %Fatal: core27_prefill_tail_probe_v3.sv:{line}: Assertion failed in TOP.core27_prefill_tail_probe_v3: {contract['fatal']}\nAborting...\n"
            self.assertEqual(recipe.check_fatal(log,-6,contract)['fatal'],contract['fatal'])
            for code in (0,1,-9,-11,124):
                with self.assertRaisesRegex(ValueError,'SIGABRT'):recipe.check_fatal(log,code,contract)
            for altered in [log.replace(f':{line}:',':9999:'),log.replace(contract['fatal'],'data mismatch'),
                            log.replace('TOP.core27_prefill_tail_probe_v3:','TOP.core27_prefill_tail_probe_v3evil:'),
                            log.replace('core27_prefill_tail_probe_v3.sv','wrong.sv'),log+'T5_TARGET_PASS mode=x\n',log*2]:
                with self.assertRaises(ValueError):recipe.check_fatal(altered,-6,contract)

    def test_one_build_suite_keeps_seven_bounded_groups(self):
        groups=gate.suite_commands('/e','/v',normal)
        self.assertEqual(len(groups),7)
        self.assertEqual(sum(len(cases) for _,cases in groups),28)
        self.assertLessEqual(max(len(cases) for _,cases in groups),7)
        names=[name for _,cases in groups for name,_ in cases]
        self.assertEqual(len(names),len(set(names)))
        self.assertEqual(groups[-1][0],'reload-control')

    def test_reload_footer_and_every_field_are_bound(self):
        argv=['/e','--reload-control','/v','control']
        fields=dict(mode='--reload-control',age='0',row='none',row_index='1',middle_aliases_final='1',
                    event_hits='1',successful='2',readbacks='2',recoveries='0')
        render=lambda f:'T5_TARGET_PASS '+' '.join(k+'='+v for k,v in f.items())+'\n'
        self.assertEqual(recipe.check_footer(render(fields),argv),fields)
        for key in fields:
            changed=dict(fields);changed[key]='wrong'
            with self.assertRaisesRegex(ValueError,'command-bound'):recipe.check_footer(render(changed),argv)
        with self.assertRaisesRegex(ValueError,'unique'):
            recipe.check_footer(render(fields).strip()+' mode=x\n',argv)

    def test_driver_allows_named_observer_to_classify_mutants(self):
        s=(ROOT/'rtl/tb/core27_prefill_adversarial_v1.cpp').read_text()
        self.assertIn('if(!reload_case)need(!d.dbg_prefilled',s)
        self.assertIn('if(d.done && !d.error){tick();throw',s)
        self.assertIn('load(a);start(a,0);finish(a,v[1],false);',s)
        self.assertIn('d.final();return 0;',s)

    def test_gzip_executable_roundtrip_and_no_raw_deletion(self):
        payload=b'\x7fELF'+bytes(range(256))*4096
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name);source=directory/'native';source.write_bytes(payload)
            target=directory/'native.gz'
            result=gate.compressed_executable(source,target)
            self.assertEqual(result['uncompressed_sha256'],hashlib.sha256(payload).hexdigest())
            self.assertEqual(result['compressed_sha256'],gate.sha(target))
            self.assertEqual(gzip.decompress(target.read_bytes()),payload)
            self.assertEqual(source.read_bytes(),payload)
            with self.assertRaisesRegex(ValueError,'fresh'):gate.compressed_executable(source,target)

    def test_closed_source_ancestry_and_snapshot(self):
        pins=gate.source_pins(ROOT)
        old=json.loads((ROOT/gate.PREDECESSOR_MANIFEST).read_text())['sources']
        self.assertEqual(len(old),98)
        self.assertTrue(all(pins.get(k)==v for k,v in old.items()))
        self.assertEqual(len(pins),104)
        self.assertEqual(pins[gate.NORMAL_T5_REPORT],gate.NORMAL_T5_SHA)
        self.assertIn('core27-prefill-aw5-qualification/snapshot-v1/fpga',str(gate.ROOT))

    def test_actual_collected_normal_prerequisite_replays_offline(self):
        local=(ROOT/gate.NORMAL_T5_REPORT).parent.resolve()
        with patch.object(gate,'NORMAL_OUTPUT',local):
            report=gate.normal_prerequisite(ROOT,local/'report.json',gate.NORMAL_T5_SHA,baseline,normal)
            self.assertEqual(len(report['metrics']),568)
            with self.assertRaisesRegex(ValueError,'path/hash'):
                gate.normal_prerequisite(ROOT,local/'report.json','0'*64,baseline,normal)

    def test_no_unqualified_cache_or_aggregate_mutation_sweep(self):
        s=(ROOT/gate.RUNNER).read_text()
        self.assertIn("build=scratch/('build-'+role);require(not build.exists()",s)
        self.assertIn("CCACHE_DISABLE='1'",s)
        self.assertNotIn('for mutation in',s)
        self.assertIn('one explicit mutation',s)
        self.assertIn('durable_reserve=32*MIB',s)
        for token in ['10*GIB','2*GIB','4*GIB','resource.RLIMIT_CORE','resource.RLIMIT_AS',
                      "limits['affinity']==[0,2]",'-Werror=return-type','sha(normal_path)==normal_sha',
                      'compressed executable round-trip','durable executable decompressed identity']:
            self.assertIn(token,s)
        self.assertNotIn("'.gch'",s)


if __name__=='__main__':unittest.main()
