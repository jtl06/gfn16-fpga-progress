import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_root_lookahead_debt_v3 as g
from fpga.reference import root_lookahead_debt_prepare_v3 as p


class DebtGate(unittest.TestCase):
    def setup_packet(self, directory):
        out = Path(directory).resolve()/'packet'
        p.prepare(out)
        root = out/'source/fpga'
        m = json.loads((out/'manifest.json').read_text())
        tools = dict(taskset=Path('/usr/bin/taskset'), verilator=Path('/pinned/verilator'))
        build = Path('/dev/shm/exact-test/build')
        c = m['build']
        cmd = [str(tools['taskset']), '-c', '0,2', str(tools['verilator']), '--lint-only', '-Wall',
               '--threads', '1', '--top-module', c['top'], *[f'-G{k}={v}' for k,v in c['parameters'].items()],
               '--Mdir', str(build), *[str(root/x) for x in c['sv_sources']]]
        old = json.loads((root/g.BASELINE).read_text())
        stderr = (root/g.STDERR).read_bytes().replace(old['source_root'].encode(), str(root).encode())
        return root, m, tools, build, cmd, stderr

    def test_exact_observation_and_negative_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            root,m,tools,build,cmd,err = self.setup_packet(temp)
            with patch.object(g, 'ROOT', str(root)):
                result = g.accept_exact_lint_debt('lint',cmd,1,b'',err,m,tools,root,build)
                self.assertEqual(result['warning_count'],2)
                self.assertIn('NOT_clean_lint',result['status'])
                cases = [dict(code=0),dict(code=2),dict(code=True),dict(stdout=b'noise'),
                    dict(stderr=err+b'%Warning-WIDTH: new\n'), dict(stderr=b''),
                    dict(stderr=err.replace(b'UNUSEDSIGNAL',b'UNOPTFLAT')),
                    dict(stderr=err.replace(b'lane[15]',b'lane[14]')),
                    dict(stderr=err.replace(b'2 warning(s)',b'1 warning(s)')),
                    dict(stderr=err.replace(str(root).encode(),b'/unapproved/path')),
                    dict(stderr=err.replace(b':72:16',b':74:16')),
                    dict(stderr=err+b'%Error: native failure\n'),dict(stderr=err+b'\0'),
                    dict(command=cmd+['-Wno-fatal']), dict(command=cmd[::-1]), dict(name='build')]
                baseline=dict(name='lint',command=cmd,code=1,stdout=b'',stderr=err,
                              manifest=m,tools=tools,root=root,build=build)
                for delta in cases:
                    with self.subTest(delta=delta):
                        with self.assertRaises(ValueError):g.accept_exact_lint_debt(**(baseline|delta))
                for key,value in [('LANES',64),('P',69206017)]:
                    changed=copy.deepcopy(m);changed['build']['parameters'][key]=value
                    with self.assertRaises(ValueError):g.accept_exact_lint_debt(**(baseline|{'manifest':changed}))
                changed=copy.deepcopy(m);changed['sources'][g.PARENT]='0'*64
                with self.assertRaises(ValueError):g.accept_exact_lint_debt(**(baseline|{'manifest':changed}))
                changedtools=dict(tools,verilator=Path('/wrong/tool'))
                with self.assertRaises(ValueError):g.accept_exact_lint_debt(**(baseline|{'tools':changedtools}))
                (root/g.PARENT).write_text('changed')
                with self.assertRaises(ValueError):g.accept_exact_lint_debt(**baseline)

    def test_parent_changes_only_self_and_return_admission(self):
        raw=(p.ROOT/g.PARENT).read_bytes();new=g.adapted_source(raw)
        before=ast.parse(raw.decode());after=ast.parse(new)
        functions=lambda tree:{x.name:ast.dump(x) for x in tree.body if isinstance(x,ast.FunctionDef)}
        oldf,newf=functions(before),functions(after)
        self.assertEqual([k for k in oldf if oldf[k]!=newf[k]],['execute'])
        # Existing lock and lint-before-build body are byte-for-byte untouched.
        fragment="            run('lint', lint)\n            run('build', command)"
        self.assertIn(fragment,new)
        self.assertIn("'--lint-only', '-Wall'",new)
        self.assertNotIn('-Wno',new)
        self.assertIn("tools_for(profile)",new)
        self.assertIn("check_sources(root, manifest['sources'])",new)
        with self.assertRaises(ValueError):g.adapted_source(raw+b'\n')

    def test_diagnostic_rejection_prevents_build_control_flow(self):
        tree=ast.parse(g.adapted_source((p.ROOT/g.PARENT).read_bytes()))
        statements=[x for x in ast.walk(tree) if isinstance(x,ast.If) and ast.unparse(x.test)=="name == 'lint'"]
        self.assertEqual(len(statements),1)
        unit=ast.Module(body=statements,type_ignores=[]);ast.fix_missing_locations(unit)
        class Log:
            def read_bytes(self):return b''
        class Child:returncode=1
        def reject(*args):raise ValueError('unapproved diagnostics')
        scope=dict(name='lint',report={},accept_exact_lint_debt=reject,command=[],child=Child(),
                   log=Log(),error_log=Log(),manifest={},toolpaths={},root=Path('/bad'),build=Path('/bad'),save=lambda:None)
        with self.assertRaisesRegex(ValueError,'unapproved'):exec(compile(unit,'exact-return-admission','exec'),scope)
        self.assertNotIn('lint_debt',scope['report'])


if __name__=='__main__':unittest.main()
