"""Source-preserving Azure refresh with the qualified r49 meter-v3 worker."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='fc3efb305ec26505b1108a5361622910aeaabdf6d836442821a8e1405b22a3e4'
PACKAGE_SHA='9ca500ca811740232017de9f3f852bc8e838e5384769e26c401ab891d3295564'
VARIANTS_SHA='575a31c4a06d44139a406623f939bc38a591edc42304527dab2af5efe6fb4727'

def module():
    raw=(HERE/'native_azure_variant_refresh_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen refresh source')
    text=raw.decode().replace('native_class_package_v3.py','native_class_package_v4.py').replace('a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd',PACKAGE_SHA)
    text=text.replace('native_profile_variants_v2.py','native_profile_variants_v3.py').replace('064b9948606f1b008de2cb73a63a250ed0029f50ab3b2713483941bebf2f7d5e',VARIANTS_SHA)
    result=types.ModuleType('_meter_v3_refresh');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_azure_variant_refresh_v1.py')+'[r49]','exec'),result.__dict__)
    return result

def repackage_variant(*args,**kwargs):return module().repackage_variant(*args,**kwargs)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('existing-package-dir','provider-path','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--profile',required=True);parser.add_argument('--id',required=True);parser.add_argument('--provider-sha256',required=True)
    args=parser.parse_args();print(json.dumps(repackage_variant(args.existing_package_dir.resolve(),args.profile,args.id,
        args.provider_path.resolve(),args.provider_sha256,args.output.resolve()),indent=2))
