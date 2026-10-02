"""Pinned CPU0/2-only admission, no native tools or remote operations."""
import ast
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import native_source_gate_aethia_cpu02_v1 as r
from fpga.reference import root_lookahead_cpu02_prepare_v1 as p


class CPU02Gate(unittest.TestCase):
    def test_exact_minimal_parent_delta_and_inherited_locked_lint(self):
        original=(p.ROOT/p.PARENT).read_text();source=Path(r.__file__).read_text()
        self.assertEqual(source,p.launcher_source(original))
        def functions(text):
            return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
        old,new=functions(original),functions(source)
        self.assertEqual({name for name in old if old[name]!=new[name]},{'load_manifest','execution_limits'})
        self.assertEqual(set(r.PROFILES),{'aethia'})
        self.assertEqual(r.PROFILES['aethia']['cpus'],[0,2])
        self.assertIn("with lockpath.open('r') as lock:",new['execute'])
        self.assertLess(new['execute'].index("run('lint', lint)"),new['execute'].index("run('build', command)"))

    def limits(self,swap='0',affinity=(0,2),cores=None):
        values={'/proc/self/cgroup':'0::/fixture\n','/sys/fs/cgroup/fixture/memory.max':str(4<<30),
                '/sys/fs/cgroup/fixture/memory.swap.max':swap,'/sys/fs/cgroup/fixture/cpu.max':'200000 100000'}
        for cpu,core in (cores or {0:0,2:1,4:2,6:3}).items():
            prefix=f'/sys/devices/system/cpu/cpu{cpu}/topology/'
            values[prefix+'physical_package_id']='0';values[prefix+'core_id']=str(core)
        with patch.object(r.Path,'read_text',lambda path,*args,**kwargs:values[str(path)]),\
             patch.object(r.os,'sched_getaffinity',return_value=set(affinity),create=True):
            return r.execution_limits([0,2])

    def test_no_swap_exact_physical_cores_and_cpu46_disjoint(self):
        result=self.limits();self.assertEqual(result['physical_cores'],[[0,0],[0,1]])
        self.assertEqual(result['excluded_cpu46_physical_cores'],[[0,2],[0,3]])
        self.assertEqual(result['swap_max_bytes'],0)
        for swap in ('max','1'):
            with self.assertRaisesRegex(ValueError,'no swap'):self.limits(swap=swap)
        with self.assertRaisesRegex(ValueError,'affinity'):self.limits(affinity=(4,6))
        with self.assertRaisesRegex(ValueError,'CPU0/2 physical'):self.limits(cores={0:0,2:0,4:2,6:3})
        with self.assertRaisesRegex(ValueError,'CPU4/6 topology'):self.limits(cores={0:0,2:1,4:0,6:3})

    def test_old_profile_and_other_host_refused_before_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'manifest.json'
            for host,profile in (('aethia',None),('aethia','old'),('gfn16-pilot-c4',p.PROFILE)):
                path.write_text(json.dumps(dict(schema='native-source-gate-v1',status='prepared_not_executed',host=host,cpu_profile=profile)))
                with patch.object(r.socket,'gethostname',return_value=host),\
                     patch.object(r,'check_sources',side_effect=AssertionError('too early')):
                    with self.assertRaises(ValueError):r.load_manifest(path,r.sha(path))

    def test_single_manifest_preserves_all_parent_inputs_and_native_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp).resolve()/'packet';report=p.prepare(output)
            manifest=json.loads((output/'manifest.json').read_text())
            parent=json.loads((p.ROOT/p.PARENT_PACKET/'aethia-component-l16-f1.json').read_text())
            for key in ('build','probe','steps'):self.assertEqual(manifest[key],parent[key])
            self.assertEqual(manifest['cpu_profile'],p.PROFILE)
            self.assertTrue(all(manifest['sources'][name]==pin for name,pin in parent['sources'].items()))
            r.check_sources(output/'source/fpga',manifest['sources'])
            with tarfile.open(output/'source.tar.gz') as archive:
                self.assertEqual(len(archive.getmembers()),report['source_members'])
                self.assertTrue(all(m.isfile() for m in archive.getmembers()))
                self.assertEqual({m.name.removeprefix('fpga/'):r.hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                                  for m in archive.getmembers()},manifest['sources'])
            # Source-only mocked placement/hostname verifies final manifest API.
            manifest['source_root']=str(output/'source/fpga');manifest['output_parent']=str(output)
            path=output/'local-contract.json';path.write_text(json.dumps(manifest))
            profile=dict(r.PROFILES['aethia'],base=str(output))
            with patch.dict(r.PROFILES,{'aethia':profile}),patch.object(r.socket,'gethostname',return_value='aethia'),\
                 patch.object(r,'__file__',str(output/'source/fpga'/r.SELF)):
                self.assertEqual(r.load_manifest(path,r.sha(path))[0],manifest)
                manifest['steps'][0]['name']='lint';path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError,'unique step names'):r.load_manifest(path,r.sha(path))


if __name__=='__main__':unittest.main()
