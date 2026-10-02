"""Explicit GCP-generation/Azure-replay bridge for promoted T5b soak.

Preserves the original oracle and generation provenance byte-for-byte. Native
validation independently replays the unchanged integer method on the target's
admitted runtime, checks every requested boundary array, and reports BOTH tool
identities. It never claims GCP generation ran on Azure. No runner is added.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/core27_t5b_soak_cross_runtime_v1.py'
ADAPTER = 'reference/core27_t5b_soak_native_v1.py'
ADAPTER_SHA = '43a35c1bd1c2d256fb793a8087681e9e2c0281441eeca57aa2fd6dfdf7934db0'
COMMAND = 'tools/native_reference_command_v2.py'
COMMAND_SHA = 'eddb3e2b9286f7800600af3a232b2b4027e88744a73731e24fdb1be11f6f151d'
GENERATION_RUNTIME_SHA = '84fb40c8e6452d4b660d9302e83584dd3c4761aa6219495e57f2df582401cf0b'
TARGET_RUNTIME_PINS = {
    'gfn16-azure-f16': '1ed8253a93078657227941ea9e1f08d2420dc1a27d992f0e767b2136ebf5f8dc',
    'gfn16-azure-sim-f32': '1a5125fa55711298b5412df91105e47aa4c13b6b42ab32191fd8b23696f081f2',
}
IDENTITY_KEYS = {'version', 'gmp_version', 'module_sha256', 'python_sha256', 'module_files_sha256'}
MATH_KEYS = {'engine', 'platform', 'native_qualification_allowed', 'method',
             'schedule_exponent_crosscheck', 'modulus_sha256'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def load(name, pin):
    path=ROOT/name
    need(path.is_file() and not path.is_symlink() and sha(path)==pin,'SOAK_CROSS_CLOSED_CODE')
    spec=importlib.util.spec_from_file_location('_soak_cross_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def runtime_identity(value):
    """Metadata only; actual target admission is separately mandatory."""
    if value['host']=='gfn16-pilot-c4d':
        files=value['toolchain_files_sha256'];origin=value['import_origin']
        version=value['package_version'];python=value['python_sha256'];gmp=value['gmp_version']
    else:
        files=value['files_sha256'];origin=str(Path(value['module_roots'][0])/'__init__.py')
        version=value['package_version'];python=files[value['python_resolved']];gmp='GMP 6.3.0'
    extension=[name for name in files if Path(name).parent==Path(origin).parent
               and Path(name).name.startswith('gmpy2.') and name.endswith('.so')]
    need(len(extension)==1 and origin in files,'SOAK_CROSS_EXACT_MODULE_IDENTITIES')
    return dict(version=version,gmp_version=gmp,module_sha256=files[origin],python_sha256=python,
                module_files_sha256={'gmpy2':files[origin],'gmpy2.gmpy2':files[extension[0]]})


def verify_pair(replayed, generated, generation_runtime, target_runtime):
    need(set(generated)==set(replayed)==IDENTITY_KEYS|MATH_KEYS,'SOAK_CROSS_COMPLETE_PROVENANCE')
    need({k:generated[k] for k in IDENTITY_KEYS}==runtime_identity(generation_runtime),
         'SOAK_CROSS_ORIGINAL_GENERATION_IDENTITY')
    need({k:replayed[k] for k in IDENTITY_KEYS}==runtime_identity(target_runtime),
         'SOAK_CROSS_ACTUAL_TARGET_IDENTITY')
    need({k:replayed[k] for k in MATH_KEYS}=={k:generated[k] for k in MATH_KEYS}
         and replayed['engine']=='gmpy2' and replayed['platform']=='Linux'
         and replayed['native_qualification_allowed'] is True,
         'SOAK_CROSS_IDENTICAL_INTEGER_METHOD_MODULUS')


def binding(assets):
    """Bind unchanged generation bytes to the actual typed reference receipt."""
    required={'oracle','runtime','generation-runtime','generation','generation-admission',
              'reference-config','reference-report','reference-execution'}
    need(set(assets)==required,'SOAK_CROSS_EXACT_ASSETS')
    need(digest(assets['generation-runtime'])==GENERATION_RUNTIME_SHA,'SOAK_CROSS_GENERATION_RUNTIME_PIN')
    target=json.loads(assets['runtime']);host=target['host']
    need(host in TARGET_RUNTIME_PINS and digest(assets['runtime'])==TARGET_RUNTIME_PINS[host],
         'SOAK_CROSS_TARGET_RUNTIME_PIN')
    original=json.loads(assets['generation-runtime'])
    command=load(COMMAND,COMMAND_SHA)
    config=json.loads(assets['reference-config']);command.validate(config)
    report=json.loads(assets['reference-report']);ticket=json.loads(assets['reference-execution'])
    receipt=ticket['reference_execution_receipt']
    need(ticket['kind']=='reference' and ticket['result']['properties']['Result']=='success'
         and ticket['result']['properties']['ExecMainStatus']=='0'
         and ticket['package']['runner_sha256']==COMMAND_SHA
         and ticket['package']['ticket_sha256']==digest(assets['reference-config'])
         and ticket['package']['worker_id']==config['identity']
         and ticket['package']['profile']==config['profile']
         and receipt['status']=='PASS_reference_execution_outputs_not_HDL_or_import'
         and receipt['config_sha256']==report['config_sha256']==digest(assets['reference-config'])
         and receipt['report_sha256']==digest(assets['reference-report'])
         and receipt['outputs']==report['outputs']
         and report['sources']==config['sources'] and report['returncode']==0
         and report['status']=='completed_reference_command_needs_import_validation'
         and report['HDL_executed'] is False and report['promotion_allowed'] is False,
         'SOAK_CROSS_ACTUAL_REFERENCE_EXECUTION_BINDING')
    limits=report['limits'];quota=limits['cpu_max']
    need(limits['memory_max_bytes']==8<<30 and limits['swap_max_bytes']==0
         and limits['affinity']==config['physical_cpus'] and len(quota)==2
         and quota[0]!='max' and int(quota[0])==2*int(quota[1]),
         'SOAK_CROSS_RECORDED_REFERENCE_CAPS')
    need(set(report['outputs'])=={*config['expected_files'],'command.stdout','command.stderr'},
         'SOAK_CROSS_COMPLETE_GENERATION_OUTPUTS')
    adapter=load(ADAPTER,ADAPTER_SHA);ref=adapter.reference()
    oracle=json.loads(assets['oracle']);plan,segment=ref.check_oracle(oracle)
    wanted=ref.make_plan(16,*(command.RECIPES[config['recipe']]),20261001,604832956)
    need(plan==wanted,'SOAK_CROSS_REFERENCE_RECIPE_CASE')
    generation=json.loads(assets['generation']);admission=json.loads(assets['generation-admission'])
    expected_generation_files={name.removeprefix('reference/') for name in config['expected_files']
        if name not in ('reference/generation.json','reference/auxiliary-runtime-admission.json')}
    need(set(generation['files'])==expected_generation_files
         and all(pin==report['outputs']['reference/'+name]['sha256']
                 for name,pin in generation['files'].items())
         and oracle['corpus_sha256']==report['outputs']['reference/'+segment['name']+'.txt']['sha256'],
         'SOAK_CROSS_COMPLETE_REFERENCE_FILE_BINDINGS')
    for label,key in (('oracle',segment['name']+'.json'),('generation','generation.json'),
                      ('generation-admission','auxiliary-runtime-admission.json')):
        row=report['outputs']['reference/'+key]
        need(row['sha256']==digest(assets[label]) and row['bytes']==len(assets[label].encode()),
             'SOAK_CROSS_RETAINED_GENERATION_BYTES')
    need(generation['case_id']==plan['case_id'] and generation['generator_sha256']==sha(ROOT/ref.SELF)
         and generation['files'][segment['name']+'.json']==digest(assets['oracle'])
         and generation['oracle']==oracle['oracle']
         and generation['parent_source_sha256']==oracle['parent_source_sha256']==ref.parent_sources()[1]
         and admission['status']=='passed_exact_auxiliary_reference_runtime'
         and admission['adapter_sha256']==ADAPTER_SHA
         and admission['runtime_manifest_sha256']==GENERATION_RUNTIME_SHA
         and admission['reference_generation_sha256']==digest(assets['generation']),
         'SOAK_CROSS_SOURCE_ORACLE_ADMISSION_BINDING')
    return original,target,oracle


def validate(stdout,stderr,returncode,config,assets):
    original,target,oracle=binding(assets)
    adapter=load(ADAPTER,ADAPTER_SHA)
    admitted=adapter.admit_runtime(assets['runtime'])  # Actual target closure BEFORE GMP import/work.
    module=adapter.reference()
    # Reuse the frozen function unchanged except for its formerly same-host
    # identity assertion. Every boundary array check remains before this call.
    raw_bytes=(ROOT/'reference/core27_crtmont_soak_v1.py').read_bytes()
    need(hashlib.sha256(raw_bytes).hexdigest()=='8075e2033a01b09b9bbc344b72f23df4ebbc90b8489caadfbd0546e6f3bcfe3a',
         'SOAK_CROSS_FROZEN_INTEGER_FUNCTION')
    raw=raw_bytes.decode()
    begin=raw.index('def validate(stdout, stderr, returncode, config, assets):')
    end=raw.index('\ndef combine_chunks(',begin)
    code=raw[begin:end]
    old="    require(provenance == oracle['oracle'], 'SOAK_EXACT_REFERENCE_TOOL_IDENTITY')"
    need(code.count(old)==1,'SOAK_CROSS_UNIQUE_TOOL_IDENTITY_ASSERTION')
    code=code.replace(old,"    verify_cross_pair(provenance, oracle['oracle'])\n    record_cross_provenance(provenance)",1)
    replay=[]
    module.verify_cross_pair=lambda current,generated:verify_pair(current,generated,original,target)
    module.record_cross_provenance=lambda current:replay.append(current)
    exec(compile(code,str(ROOT/SELF)+'[explicit-two-runtime-identity]','exec'),module.__dict__)
    result=module.validate(stdout,stderr,returncode,config,{'oracle':assets['oracle']})
    result.update(lineage='promoted-t5b',generation_host=original['host'],replay_host=target['host'],
        generation_oracle_provenance=oracle['oracle'],replay_oracle_provenance=replay[0],
        generation_runtime_manifest_sha256=GENERATION_RUNTIME_SHA,
        replay_runtime_manifest_sha256=digest(assets['runtime']),
        auxiliary_reference_runtime=admitted,original_generation_not_rehosted=True)
    return result


def stage(references,segment,output,target_runtime_file,generation_runtime_file,reference_ticket,
          host,remote_root,controls=False):
    """Source/data staging only; no target import, arithmetic or dispatch."""
    output=Path(output).resolve()
    adapter=load(ADAPTER,ADAPTER_SHA)
    adapter.stage(references,segment,output,generation_runtime_file,'gfn16-pilot-c4d',remote_root,controls)
    manifest=json.loads((output/'serial-manifest.json').read_text());source=output/'source/fpga'
    ticket=json.loads(Path(reference_ticket).read_text())
    report=Path(ticket['result']['evidence'])/'output/command-report.json'
    inputs={'generation-runtime':generation_runtime_file,'runtime':target_runtime_file,
        'generation':Path(references)/'generation.json',
        'generation-admission':Path(references)/'auxiliary-runtime-admission.json',
        'reference-config':ticket['package']['config'],'reference-report':report,
        'reference-execution':reference_ticket}
    # Original runtime remains retained rather than rewritten to target fields.
    for key,path in inputs.items():
        relative='soak/cross-'+key+'.json';target=source/relative
        shutil.copyfile(path,target);manifest['sources'][relative]=sha(target)
    for name in (SELF,COMMAND,'tools/native_reference_command_v1.py'):
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target);manifest['sources'][name]=sha(target)
    values={'oracle':(source/('soak/'+segment+'.json')).read_text(),
            **{key:(source/('soak/cross-'+key+'.json')).read_text() for key in inputs}}
    _,actual_target,_=binding(values)
    need(actual_target['host']==host,'SOAK_CROSS_EXPLICIT_TARGET_HOST')
    manifest['host']=host;manifest['auxiliary_reference_runtime_manifest_sha256']=digest(values['runtime'])
    manifest['cross_runtime_reference']=dict(generation_runtime_sha256=GENERATION_RUNTIME_SHA,
        target_runtime_sha256=digest(values['runtime']),original_generation_not_rehosted=True)
    for step in manifest['steps']:
        step['validator']['source']=SELF
        step['validator']['assets']={'oracle':'soak/'+segment+'.json',
            **{key:'soak/cross-'+key+'.json' for key in inputs}}
    path=output/'cross-runtime-manifest.json'
    with path.open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    return dict(status='staged_explicit_cross_runtime_not_dispatched',manifest=str(path),
        manifest_sha256=sha(path),source_root=str(source),generation_host='gfn16-pilot-c4d',replay_host=host)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('references','output','target-runtime-file','generation-runtime-file','reference-ticket'):
        parser.add_argument('--'+name,type=Path,required=True)
    for name in ('segment','host','remote-root'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--controls',action='store_true');args=parser.parse_args()
    print(json.dumps(stage(args.references,args.segment,args.output,args.target_runtime_file,
        args.generation_runtime_file,args.reference_ticket,args.host,args.remote_root,args.controls),indent=2))
