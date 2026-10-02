"""Pure typed SIGABRT/pretruncation evidence; never hardware admission."""
import hashlib
from pathlib import PurePosixPath
import re


def need(ok, why):
    if not ok:
        raise ValueError(why)


def validate(stdout, stderr, returncode, config, assets):
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int, 'raw typed streams/signal')
    need(returncode == -6, 'actual direct SIGABRT required; do not relabel as rc1/134')
    need(type(config) is dict and set(config) == {'kind','aw','field','engine_sha256','ram_sha256'}, 'exact fault config')
    kind = config['kind']
    need(kind in ('--high-bit','--bit27','--vector-high-bit') and type(config['aw']) is int and config['aw'] == 5
         and type(config['field']) is int and config['field'] == 104857601, 'bounded explicit fault role')
    need(type(assets) is dict and set(assets) == {'engine','ram'} and all(type(v) is str for v in assets.values()), 'exact source assets')
    for name in ('engine','ram'):
        need(hashlib.sha256(assets[name].encode()).hexdigest() == config[name+'_sha256'], 'fault source hash')
    need('data_w[bank]>=P' in assets['engine'] and 'write_data[31:27]!=0' in assets['ram'], 'full-word pretruncation checks retained')
    word = 0x08000001 if kind == '--bit27' else 0x80000001
    marker = f'AA_DATA27_HIGHBIT kind={kind} word={word} aw=5 field=104857601\n'
    need(stdout.startswith(marker) and len(stdout)+len(stderr) < 16384, 'exact injected high-word marker and bounded logs')
    lines = (stdout[len(marker):] + stderr).splitlines()
    need(len(lines) == 3 and lines[-1] == 'Aborting...', 'only exact assertion/stop/abort diagnostics')
    first = re.fullmatch(r'\[0\] %(?:Error|Fatal): (.+?):([0-9]+): Assertion failed in (\S+): (.+)', lines[0])
    second = re.fullmatch(r'%Error: (.+?):([0-9]+): Verilog \$stop', lines[1])
    need(first is not None and second is not None, 'explicit SV assertion and stop, not incidental crash')
    reason, top = first[4], 'TOP.genefer_a10_banked27_host16_engine_v1.child.memories[0]'
    if reason == 'A10_NONCANONICAL_WRITE':
        name, basename, token, scope = 'engine', 'genefer_a10_pointdata27_v1.sv', 'A10_NONCANONICAL_WRITE', top
    elif reason == 'RAM residue write exceeds27 bits':
        name, basename, token, scope = 'ram', 'genefer_sdp_ram27_residue.sv', 'RAM residue write exceeds27 bits', top+'.data_ram'
    else:
        raise ValueError('wrong fatal reason; reset/profile/collision failures do not qualify')
    sites = [i for i,line in enumerate(assets[name].splitlines(),1) if token in line]
    need(len(sites) == 1 and int(first[2]) == int(second[2]) == sites[0] and first[3] == scope
         and PurePosixPath(first[1]).name == PurePosixPath(second[1]).name == basename,
         'exact pinned assertion location and bank0 scope')
    return dict(status='PASS_actual_SIGABRT_pretruncation_simulation_assertion', actual_returncode=-6,
                kind=kind, word=word, reason=reason, source=basename, line=sites[0],
                synthesized_hardware_admission_proved=False, whole_core_rejection_or_atomicity_claim=False)
