"""Exact full65540 ordinal contracts; one3300s model, unchanged outer bounds."""
import hashlib
import json

SHAPE = dict(id='ordinal-single-model3300-v1', model_command_seconds=3300,
             ancillary_command_seconds=1800, overall_seconds=3600,
             outer_seconds=3700, stop_grace_seconds=15, lock_wait_seconds=1800,
             model_threads=1)
CONTRACTS = {
    '8f79b4a5c20cdb6d03162ef5ddc2bbcf5b22d19ed8dce7cb4277d64883d9c61e': 'p16-positive',
    'c76e5601493e8a31965f343d9a7693867b8d6d1ca825b55659f1228a8a866d0a': 'p16-negative',
    '7f3055137601da232d6db476d30914c345b25be341a4fd178dc1f96c96c04247': 'p8-negative',
}


def need(ok, why):
    if not ok:
        raise ValueError('ordinal duration: ' + why)


def contract(manifest):
    names = set(manifest['build']['sv_sources']) | {manifest['build']['cpp_source']}
    value = dict(build=manifest['build'], probe=manifest['probe'], steps=manifest['steps'],
                 pins={name: manifest['sources'][name] for name in sorted(names)})
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def descriptor(manifest):
    return dict(shape=SHAPE, contract_sha256=contract(manifest))


def validate(manifest, root=None, host='gfn16-pilot-c4d', require_policy=True):
    need(host == 'gfn16-pilot-c4d', 'exact existing GCP host only')
    pin = contract(manifest)
    need(pin in CONTRACTS, 'one of three frozen full65540 source/output contracts')
    need(len(manifest['steps']) == 1, 'one model command only')
    step = manifest['steps'][0]
    need(type(step['expected_returncode']) is int and step['expected_returncode'] in (0, 1),
         'exact positive or typed-negative returncode')
    need(manifest['probe']['expected_json'] ==
         dict(context_threads=1, model_threads=1, expected_threads=1), 'single model thread')
    if root is not None:
        for name in set(manifest['build']['sv_sources']) | {manifest['build']['cpp_source']}:
            path = root / name
            need(not path.is_symlink() and path.is_file() and
                 hashlib.sha256(path.read_bytes()).hexdigest() == manifest['sources'][name],
                 'actual compiled source hash: ' + name)
    if require_policy:
        need(manifest.get('runtime_duration') == descriptor(manifest), 'exact source-bound duration policy')
    return dict(status='PASS_exact_full65540_duration_contract_not_numeric', shape=SHAPE,
                contract_sha256=pin, role=CONTRACTS[pin], model_step=step['name'],
                model_argv=step['argv'], expected_returncode=step['expected_returncode'],
                host=host, promotion_allowed=False)


def command_seconds(name, argv, expected, receipt):
    if name != receipt['model_step']:
        return SHAPE['ancillary_command_seconds']
    need(argv[1:] == receipt['model_argv'][1:] and type(expected) is int and
         expected == receipt['expected_returncode'], 'declared model argv/outcome drift')
    return SHAPE['model_command_seconds']
