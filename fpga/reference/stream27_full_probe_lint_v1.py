"""Closed AW16 lint-only inputs for existing P16-c and P8-b physical projects.

No numerical gate is asserted. The C++ source is a runtime-thread probe only;
the admitted ticket phase must be lint, so neither build nor probe is executed.
"""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
PROJECTS={
 'p16c':('stream27-p16c-aw16-p16-f0-prepared-v2','9c8b31cb54f95bd797ec7f53ba95bf3a845bbbe054d157dc861524fd7e32d825'),
 'p8b':('stream27-p8b-aw16-p8-f0-prepared-v1','97a2eb399b7d7f50c68bcc97d1b002916072c330ab7207fc9a71b92f9fa112e0')}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination,variant):
    destination=Path(destination).resolve();assert variant in PROJECTS and not destination.exists()
    assert not (ROOT/'docs/briefs/PAUSE').exists()
    name,pin=PROJECTS[variant];project=ROOT/'artifacts'/name/'project'
    assert sha(project/'manifest.json')==pin
    m=json.loads((project/'manifest.json').read_text());source=destination/'inputs/fpga'
    for name,pin in m['source_sha256'].items():
        assert sha(project/'rtl'/name)==pin
        target=source/'rtl'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(project/'rtl'/name,target)
    (source/'lineage').mkdir();shutil.copyfile(project/'manifest.json',source/'lineage/full-physical-project-manifest.json')
    bench='rtl/tb/full_probe_thread_context_v1.cpp';(source/'rtl/tb').mkdir()
    cpp='''#include "VTOP.h"
#include "verilated.h"
#include <iostream>
#include <string>
int main(int argc,char **argv){
 VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
 if(argc!=2 || std::string(argv[1])!="--runtime-probe")return 2;
 VTOP model{&context};
 std::cout<<"{\\"context_threads\\":"<<context.threads()<<",\\"model_threads\\":"<<model.threads()<<",\\"expected_threads\\":1}\\n";
 return context.threads()==1 && model.threads()==1 ? 0 : 2;
}
'''.replace('TOP',m['top'])
    (source/bench).write_text(cpp)
    expected='{"context_threads":1,"model_threads":1,"expected_threads":1}\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND_NO_DISPATCH',
        source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),
        sources={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()},
        build=dict(top=m['top'],sv_sources=['rtl/'+name for name in m['source_sha256']],cpp_source=bench,
                   parameters={'AW':16,'CONTEXTS':1},cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='thread-probe-only-no-numerical-test',argv=['{exe}','--runtime-probe'],expected_returncode=0,
                    expected_stdout=expected,expected_stderr='')],
        role_scope='AW16 lint-only exact physical project RTL; no fullN arithmetic or timing qualification.')
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result=dict(status='prepared_lint_only_no_numerical_execution',project_manifest_sha256=PROJECTS[variant][1],
        unchanged_rtl_sources=len(m['source_sha256']),required_package_phase='lint',
        manifest_sha256=sha(destination/'manifest.json'))
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    import sys
    assert len(sys.argv)==3
    print(json.dumps(prepare(sys.argv[1],sys.argv[2]),indent=2))
