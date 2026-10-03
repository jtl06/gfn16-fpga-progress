"""Labeled lean normal output. Pure captured reference validator; no GL code."""
import ast
import hashlib
import json
import math
from pathlib import Path

LABEL = 'lean build; host GL assumed (unimplemented)'
ROOT = Path(__file__).resolve().parents[1]


def need(ok, why):
    if not ok:
        raise ValueError('C2_LEAN_OUTPUT_' + why)


def validate(stdout, stderr, rc, config, assets):
    need(type(config) is dict and set(config) == {'parent_config', 'parent_source_sha256'} and assets == {}, 'CONFIG')
    need(stdout.startswith(LABEL+'\n') and stdout.count(LABEL) == 1, 'EXPLICIT_LEAN_UNIMPLEMENTED_LABEL')
    path = ROOT/'reference/stream27_p16_two_context_full_native.py'
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == config['parent_source_sha256'], 'CAPTURED_REFERENCE_PIN')
    tree = ast.parse(raw.decode())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('need', 'config', 'validate')]
    need(len(functions) == 3, 'ONLY_THREE_METADATA_FUNCTIONS')
    namespace = {'json': json, 'math': math, 'BASES': [604832956, 999999937]}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    result = namespace['validate'](stdout.removeprefix(LABEL+'\n'), stderr, rc, config['parent_config'], {})
    result.update(build_label=LABEL, host_gl_implemented=False, rollback_implemented=False,
                  verification_twin_fault_immunity_inherited=False, promotion_allowed=False,
                  scope='Fresh lean healthy words/cycles against identical captured independent reference; '+LABEL+
                  '; no malformed/fault, physical clock or full-PRP/board claim.')
    return result
