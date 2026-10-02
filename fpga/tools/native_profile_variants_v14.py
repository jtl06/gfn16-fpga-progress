"""Historical user75 accounting identity; never grants fresh admission."""
import copy
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = '4ff6af64cd6101e8697bfc8d0d173e5914be2a59005b4b480d12b3630d00a761'
METER_SHA = '9c3d902e3da0969145c4148f06a51ec9ca22a322513068074f7b338cb8ddf137'
METERS = {METER_SHA: 'cloud/host_hours_azure_signed_v1.py',
          '4f5a066527f5531c480d6c8ccb3d6c213b57bdf26e18e2b14cfb55e5958a2ced': 'cloud/host_hours_azure_v5.py'}
CONTROL_PINS = {'4adfd234e8b7d5f20f73d6e275cfee666fca9cce6ad031e93380e3a8a55ca461','e1c8549616cf89c9aa40805203b336bd8bad0e1276fd6701037506108b3906e5',
                '231c1b9edc6bcf65a071cf5333e30041ca7af66efb6ae95cc1ec822ad2dcf960'}
LONG_CONTROLS = {'tools/native_long_class_v2.py':'74cceea991c2fb87480ede8601d22958af33fe3ddcdf1266c87bf8ccaefb5104',
    'tools/native_long_package_v3.py':'7be6a6bb48fc351bd8c1e1a0686753ea9da35998361d6b301d378fb1c54926a0',
    'reference/stream27_s4_continuous_duration_v1.py':'9959897f37a10505ca4ff235647bfb70b0a607b8fc0dc911500ef93daca1d16e'}
LONG_FAMILIES={(LONG_CONTROLS['tools/native_long_class_v2.py'],LONG_CONTROLS['tools/native_long_package_v3.py']),
    ('2a4c18b48f6cfe3a4110462cbf6684831f21b083a0aa680fe77a5c0a84c94ab1',
     'ad8bee2202ae7047269071a204d272910091284ae2634f48b8ef6efe9664ef01')}
LONG_PHASES={family:LONG_CONTROLS['reference/stream27_s4_continuous_duration_v1.py'] for family in LONG_FAMILIES}
PREVIOUS_LONGS={('13ef2c50fb1b2a842f415d0ac06af5d19acce6cc9b5eaab9e8ab52aa62c766d1',pin)
    for pin in ('a6cb4b62dd2a245c2ffbfada6378e1c3707eedc2c3e1d1b454f3899a0a83ae02',
                'a15ef62834addc1686023f9ad6390116ecca240dca5ec779edf02d1a1ab2e95c')}
PRE_PARENT_LONG=('1653b016466b83334a3de79442e40903039c24ff0526af54f33da3cdd894a7d7',
                 '38cc526c4ea2c3359366d6c1d3d6104ca7b47d064e8e6c246dff49b144b5ebb3')
PRE_RESOURCE_LONG=('f26afc8adf4dccd3cafecdd5a867c7a12a26dcac19c12dd458c5ed4eba821d10',
                   '3dc48554a8f3610aaa826ee828ed8ca81be4a1b929ff3613e5bc1060a568a41b')
PRE_COMPILE_LONG=('3be4a113048b9ad59c2c53549e7fffe5ea68b57b7493a07cfcb92a0c8fd6f141',
                  'a9378c8ce9974e75978e3ccb185b1d213c7581a1bee33a5335948b832a39c526')
PRE_C2_LONG=('287cc48026659be8d21ca53f957c962954e959a1885aef8ee4214d1a39686150',
             '3a8f06382de48ff2e1c4937d0621c06360c3d9ef3af2e38757b0c2f9282ff645')
PRE_TIMING_C2_LONG=('d59ed9ab392525bc9767adbaf1b8fb81e0fcdfb98ba5b369be48499f22348ad5',
                   'ca920e76f9246690ff64b5b5abeb2324aab9959f584a61f21563f90d96728ae4')
CURRENT_LONG=('0c0cfe425bf4b6b67ea35954b3d5fef7f43059ee7718ce25f4cd862728aa0ea5',
              'c4fc46b3ce4515d9c763e0828a2ec60d41522378baa6d0ba17581cfb116b3cd5')
LONG_FAMILIES.update(PREVIOUS_LONGS|{PRE_PARENT_LONG,PRE_RESOURCE_LONG,PRE_COMPILE_LONG,PRE_C2_LONG,PRE_TIMING_C2_LONG,CURRENT_LONG})
LONG_PHASES.update({family:'87fd2011f7312216ad3a8d00dfe637698068e8670fd09c597fe8ae553f4981d9' for family in PREVIOUS_LONGS})
LONG_PHASES.update({family:'5baef385edd5ae02e1b3ae24d735d525d1e700df9a62fba817e0d683d7f2ac97' for family in (PRE_PARENT_LONG,PRE_RESOURCE_LONG,PRE_COMPILE_LONG,PRE_C2_LONG)})
LONG_PHASES[CURRENT_LONG]='d9a42c646cd43100e3ba2ded39fcf17fc32f87835b715234393df2ba26534ade'
LONG_PHASES[PRE_TIMING_C2_LONG]=LONG_PHASES[CURRENT_LONG]
WIDE_CONTROLS={'tools/native_threaded_wide_v3.py':'71924875229a549fbcfb8cd52252406a8610d40946597e1d8b2470ae843466d7',
               'tools/native_threaded_wide_package_v3.py':'8d8585935a42241b85813a8db6204b02ce5aa2a23559e91a4911489a8de410e6'}
WIDE_STAGE_SHA='de680fbef0b60f34c98b6278e7a0235fb169dc3272b20ecccc86ba10758c0cc3'


def need(ok, why):
    if not ok:
        raise ValueError('user75 identity: ' + why)


def load(path, pin):
    need(path.resolve() == path and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
         'exact trusted helper')
    spec = importlib.util.spec_from_file_location('_variant75_' + path.stem, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def legacy_parent():
    """Replay the frozen wide adapter even when its workspace file advances."""
    parent=load(HERE/'native_profile_variants_v13.py',PARENT_SHA)
    original=parent.load
    def load_parent(name,pin):
        result=original(name,pin)
        if name=='native_profile_variants_v12.py':
            factory=result.module
            def module():
                value=factory();old_load=value.load
                def frozen_load(name,pin):
                    if name!='native_threaded_wide_stage_v3.py':return old_load(name,pin)
                    need(pin=='9c9e67840871bcba9e71915fb704a8c0a051b2b352b51eab8cc177f09383e15f','known captured wide stage')
                    path=HERE/'native_threaded_wide_stage_v1.py';raw=path.read_bytes()
                    need(hashlib.sha256(raw).hexdigest()=='20581efa4daadb13ec986224ed5fc1c86df339e5508fd400a5f09340482a83f9','frozen data-only stage parent')
                    text=raw.decode().replace('native_threaded_wide_package_v1.py','native_threaded_wide_package_v3.py').replace('9632fc4f55038052add52cc8bdce1cdc2398093baf5d9561677637cdad9b2d56','8bcfd165b410a7d7b751e6ae81140c636ddf5e3754e5ae1d0df9c16c2584c28d')
                    text=text.replace('native_threaded_wide_v1.py','native_threaded_wide_v3.py').replace('75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1','5090b199e2a32463d05c38a51ff313f48b4ad210de15e047d19ced9322738419')
                    captured=types.ModuleType('_preserved_wide_data_stage');captured.__file__=str(path)
                    exec(compile(text,'[preserved exact data-only wide stage]','exec'),captured.__dict__)
                    return captured
                value.load=frozen_load;return value
            result.module=module
        return result
    parent.load=load_parent
    return parent


def functional_fingerprint(manifest, budget=None, source_root=None):
    parent = legacy_parent()
    family=tuple(manifest['sources'].get(name) for name in list(LONG_CONTROLS)[:2])
    current_long=family in LONG_FAMILIES
    adjusted=copy.deepcopy(manifest);long_ignored={};wide_ignored={};long_wide=False
    current_wide=all(manifest['sources'].get(k)==v for k,v in WIDE_CONTROLS.items())
    if current_wide:
        need(source_root is not None,'closed fixed-wide source')
        root=Path(source_root);stage=load(HERE/'native_threaded_wide_stage_v3.py',WIDE_STAGE_SHA)
        need(root.resolve()==root and root.is_dir(),'canonical fixed-wide closure')
        mandatory=set(manifest['build']['sv_sources'])|{manifest['build']['cpp_source']}
        for step in manifest['steps']:
            if 'validator' in step:mandatory.update([step['validator']['source'],*step['validator']['assets'].values()])
        for name,pin in WIDE_CONTROLS.items():
            need(name not in mandatory and manifest['sources'].get(name)==pin and hashlib.sha256((root/name).read_bytes()).hexdigest()==pin,'exact non-role wide control')
            adjusted['sources'].pop(name);wide_ignored[name]=pin
        payload={'manifest.json':json.dumps(manifest).encode()}
        for name in (stage.HARDWARE,stage.OVERLAY,'results/throughput-20260929/core27-t5b-thread-wide-topology-v1/observation-v2.json'):
            raw=(root/name).read_bytes();need(hashlib.sha256(raw).hexdigest()==manifest['sources'][name],'closed fixed physical/cache evidence')
            payload['capture/source/fpga/'+name]=raw
        contract=manifest['fixed_execution'];role=manifest['wide_thread_pilot'];count=manifest['build']['runtime_threads']
        stage.profile_from_payload(payload,dict(profile=manifest['cpu_profile'],placement=contract['placement'],fixed_execution=contract),manifest['sources'])
        runtime=load(root/'tools/native_threaded_wide_v3.py',WIDE_CONTROLS['tools/native_threaded_wide_v3.py'])
        need(runtime.validate_threaded(manifest)==count==role['thread_count'] and count in (1,4,8),'exact source-bound serial/four/eight contract')
        adjusted.pop('wide_thread_pilot');adjusted.pop('fixed_execution')
    if current_long:
        need(source_root is not None,'closed current serial long source')
        root=Path(source_root)
        need(root.resolve()==root and root.is_dir(),'canonical long closure')
        mandatory=set(manifest['build']['sv_sources'])|{manifest['build']['cpp_source']}
        for step in manifest['steps']:
            if 'validator' in step:mandatory.update([step['validator']['source'],*step['validator']['assets'].values()])
        for name,pin in LONG_CONTROLS.items():
            pin=manifest['sources'].get(name) if name in list(LONG_CONTROLS)[:2] else LONG_PHASES[family]
            need(name not in mandatory and name not in manifest.get('budget_source_members',{})
                 and manifest['sources'].get(name)==pin and hashlib.sha256((root/name).read_bytes()).hexdigest()==pin,
                 'exact non-role long control closure: '+name)
            adjusted['sources'].pop(name);long_ignored[name]=pin
        # Historical execution is bound to the immutable captured helpers, not
        # whatever the shared workspace happens to contain at collection.
        runtime=load(root/'tools/native_long_class_v2.py',family[0])
        count=manifest['probe']['expected_json']['model_threads']
        policy=runtime.duration_for(count) if hasattr(runtime,'duration_for') else runtime.duration
        need(manifest.get('phase')=='run' and manifest['runtime_duration']['shape']==policy.SHAPE,
             'unchanged exact measured long duration')
        policy.validate(manifest,root,manifest['host'])
        if count>1:
            long_wide=True
            adjusted.pop('wide_thread_pilot');adjusted.pop('fixed_execution')
    if not budget or budget.get('kind') != 'azure-host-hours-v5':
        value=parent.functional_fingerprint(adjusted,budget,source_root)
        value['ignored_exact_controls'].update(long_ignored)
        value['ignored_exact_controls'].update(wide_ignored)
        if current_wide or long_wide:finish_wide(value,manifest)
        return value
    meter_pin = budget.get('checker_sha256')
    need(meter_pin in METERS and budget.get('host') == manifest['host']
         and manifest['host'] == 'gfn16-azure-sim-f32'
         and budget['max_seconds'] == (10815 if current_long else 3715),
         'exact source-bound finite burst user75 descriptor')
    root = Path(source_root)
    need(root.resolve() == root and root.is_dir(), 'canonical accounting closure')
    checker = load(HERE.parent / METERS[meter_pin], meter_pin)
    checker.ROOT = root
    pins = checker.evidence_pins(budget)
    mandatory = set(manifest['build']['sv_sources']) | {manifest['build']['cpp_source']}
    for step in manifest['steps']:
        if 'validator' in step:
            mandatory.update([step['validator']['source'], *step['validator']['assets'].values()])
    role = manifest.get('budget_source_members')
    need(type(role) is dict and role and all(manifest['sources'].get(k) == v for k, v in role.items()),
         'unchanged original role source/config members')
    identity = {key: manifest[key] for key in ('build', 'probe', 'steps')}
    identity['sources'] = role
    source_pin = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    ignored = {}
    control_name = 'tools/native_class_package_azure75_v1.py'
    controls={}
    if not current_long and not current_wide:
        need(manifest['sources'].get(control_name) in CONTROL_PINS, 'known source-bound package control')
        controls = {control_name: manifest['sources'][control_name]}
    for name, pin in {**pins, **controls}.items():
        path = root / name
        need(not Path(name).is_absolute() and '..' not in Path(name).parts and path.resolve() == path
             and manifest['sources'].get(name) == pin and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
             'source-closed accounting/control evidence: ' + name)
        if name not in role and name not in mandatory:
            adjusted['sources'].pop(name)
            ignored[name] = pin
    need(budget['source_sha256']==source_pin,'exact source-bound role identity')
    value = parent.functional_fingerprint(adjusted, None, source_root)
    value['ignored_exact_controls'].update(long_ignored)
    value['ignored_exact_controls'].update(wide_ignored)
    if current_wide or long_wide:finish_wide(value,manifest)
    value['ignored_historical_accounting'] = ignored
    value['fresh_budget_admission_conferred'] = False
    return value


def finish_wide(value,manifest):
    value['identity'].update(fixed_execution=manifest['fixed_execution'],wide_thread_pilot=manifest['wide_thread_pilot'])
    if 'compile_allocation' in manifest:value['identity']['compile_allocation']=manifest['compile_allocation']
    value['sha256']=hashlib.sha256(json.dumps(value['identity'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def match_variants(variants):
    need(type(variants) is list and len(variants) >= 2, 'multiple immutable variants')
    values = [functional_fingerprint(v['manifest'], v.get('budget'), v.get('source_root')) for v in variants]
    need(len({v['sha256'] for v in values}) == 1, 'functional role/source/outcomes differ')
    return dict(status='MATCH_functional_role_only', functional_sha256=values[0]['sha256'],
                one_logical_claim_required=True, fresh_budget_admission_conferred=False, variants=values)
