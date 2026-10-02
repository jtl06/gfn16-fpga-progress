"""Capture read-only help on the existing AWS worker. Never opens a project."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

SSH = ['ssh', '-F', '/private/tmp/gfn16-aws.nxtVrY/ssh_config', 'gfn16-aws']
BIN = '/home/ubuntu/gfn16-worker/altera_pro/26.1/quartus/bin/'


def capture(destination):
    destination.mkdir(parents=True, exist_ok=False)
    receipts = {}
    for name in ('version', 'plan', 'place', 'route', 'finalize', 'early_place', 'flow'):
        if name == 'flow':
            argv = SSH + [BIN+'quartus_sh', '-s']
            stdin = 'load_package flow\nhelp -cmd execute_module\nexit\n'
        else:
            argv = SSH + [BIN+'quartus_fit', '--help' if name == 'version' else '--help='+name]
            stdin = None
        result = subprocess.run(argv, input=stdin, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=45)
        raw = result.stdout.encode()
        (destination/(name+'.log')).write_bytes(raw)
        receipts[name] = dict(command=argv, stdin=stdin, returncode=result.returncode,
                              sha256=hashlib.sha256(raw).hexdigest())
        if result.returncode:
            raise RuntimeError('native help failed: '+name)
    read = lambda name: (destination/(name+'.log')).read_text()
    if 'Version 26.1.0 Build 110' not in read('version') or 'Pro Edition' not in read('version'):
        raise RuntimeError('tool version changed')
    for name in ('plan','place','route','finalize'):
        if 'Option: --'+name not in read(name):
            raise RuntimeError('unrecognized stage help: '+name)
    if 'Help unavailable' not in read('early_place'):
        raise RuntimeError('early_place capability changed; review before proceeding')
    if '-args <arguments>' not in read('flow') or 'execute_module -tool map -args' not in read('flow'):
        raise RuntimeError('flow args documentation changed')
    capabilities = dict(tool_version='26.1.0 Build 110 Pro Edition',
                        execute_module_fit_args_reviewed=True,
                        flow_help_sha256=receipts['flow']['sha256'],
                        fit_flags={name:dict(flag='--'+name,help_sha256=receipts[name]['sha256'])
                                   for name in ('plan','place','route','finalize')},
                        scope='Native installed help only; no project or staged compilation executed',
                        early_place_supported=False)
    (destination/'capture.json').write_text(json.dumps(receipts,indent=2)+'\n')
    (destination/'capabilities.json').write_text(json.dumps(capabilities,indent=2)+'\n')
    print(json.dumps(capabilities,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    capture(parser.parse_args().destination)
