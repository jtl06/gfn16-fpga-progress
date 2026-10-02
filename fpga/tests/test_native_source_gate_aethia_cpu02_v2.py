"""Mandatory -Wall lint gate and immutable CPU02/component lineage; no HDL."""
import ast
import inspect
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from fpga.tools import native_source_gate_aethia_cpu02_v2 as r
from fpga.reference import root_lookahead_cpu02_prepare_v2 as p


class CPU02WallGate(unittest.TestCase):
    def test_only_identity_and_Wall_delta(self):
        parent=(p.ROOT/p.PARENT).read_text();source=Path(r.__file__).read_text()
        self.assertEqual(source,p.launcher_source(parent))
        def funcs(text):
            return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
        old,new=funcs(parent),funcs(source)
        self.assertEqual({name for name in old if old[name]!=new[name]},{'execute'})
        self.assertEqual(new['execute'].replace("'--lint-only', '-Wall',","'--lint-only',"),old['execute'])
        self.assertNotIn('-Wno',source)
        self.assertEqual(r.PROFILES['aethia']['cpus'],[0,2])

    def exercise_lock_block(self,lint_fails):
        # Execute the exact inherited lock/lint/build AST with a fake run()
        # callback. No compiler or subprocess can execute in this test.
        tree=ast.parse(inspect.getsource(r.execute))
        blocks=[n for n in ast.walk(tree) if isinstance(n,ast.With)
                and ast.unparse(n.items[0].context_expr)=="lockpath.open('r')"]
        self.assertEqual(len(blocks),1)
        block=ast.Module(body=blocks,type_ignores=[]);ast.fix_missing_locations(block)
        seen=[]
        with tempfile.TemporaryDirectory() as temp:
            lockpath=Path(temp)/'compile.lock';lockpath.write_text('')
            def run(name,argv):
                with lockpath.open('r') as other:
                    with self.assertRaises(BlockingIOError):
                        r.fcntl.flock(other,r.fcntl.LOCK_EX|r.fcntl.LOCK_NB)
                seen.append((name,argv))
                if name=='lint' and lint_fails:raise ValueError('warning-fatal lint returned1')
            config=dict(top='root_recurrence27_lookahead_pair_v1',parameters=dict(LANES=16,P=104857601,Q=4190109697,TAG_W=32),
                        sv_sources=['rtl/a.sv','rtl/b.sv'])
            scope=dict(lockpath=lockpath,time=r.time,fcntl=r.fcntl,guard=lambda:None,require=r.require,
                       config=config,toolpaths={'verilator':Path('/pinned/verilator')},
                       build=Path('/scratch/build'),root=Path('/pinned/source'),run=run,command=['build-sentinel'])
            if lint_fails:
                with self.assertRaisesRegex(ValueError,'warning-fatal'):exec(compile(block,'exact-locked-lint','exec'),scope)
                self.assertEqual([name for name,_ in seen],['lint'])
            else:
                exec(compile(block,'exact-locked-lint','exec'),scope)
                self.assertEqual([name for name,_ in seen],['lint','build'])
            self.assertEqual(seen[0][1],['/pinned/verilator','--lint-only','-Wall','--threads','1','--top-module',config['top'],
                '-GLANES=16','-GP=104857601','-GQ=4190109697','-GTAG_W=32','--Mdir','/scratch/build',
                '/pinned/source/rtl/a.sv','/pinned/source/rtl/b.sv'])

    def test_successful_exact_parameter_lint_precedes_build_under_lock(self):self.exercise_lock_block(False)
    def test_warning_fatal_lint_prevents_build_under_same_lock(self):self.exercise_lock_block(True)

    def test_single_closed_packet_preserves_parent_component(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp).resolve()/'packet';result=p.prepare(output)
            m=json.loads((output/'manifest.json').read_text())
            old=json.loads((p.ROOT/p.PARENT_PACKET/'manifest.json').read_text())
            for key in ('build','probe','steps','cpu_profile'):self.assertEqual(m[key],old[key])
            self.assertTrue(all(m['sources'][name]==pin for name,pin in old['sources'].items()))
            self.assertTrue(m['admission']['lint_all_warnings'])
            self.assertEqual(m['admission']['lint_warning_waivers'],[])
            r.check_sources(output/'source/fpga',m['sources'])
            with tarfile.open(output/'source.tar.gz') as archive:
                self.assertEqual(len(archive.getmembers()),result['source_members'])
                self.assertTrue(all(x.isfile() for x in archive.getmembers()))
                self.assertEqual({x.name.removeprefix('fpga/'):r.hashlib.sha256(archive.extractfile(x).read()).hexdigest()
                                  for x in archive.getmembers()},m['sources'])


if __name__=='__main__':unittest.main()
