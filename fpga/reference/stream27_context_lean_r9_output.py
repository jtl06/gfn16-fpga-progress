"""Pure labeled own lean-R9 normal metadata; no arithmetic/generator imports."""
import ast
import hashlib
import json
import math
from pathlib import Path

LABEL = 'lean build; host GL assumed (unimplemented)'
ROOT = Path(__file__).resolve().parents[1]


def need(ok, why):
    if not ok:
        raise ValueError('C2_LEAN_R9_OUTPUT_'+why)


def validate(stdout, stderr, rc, config, assets):
    need(set(config) == {'parent_config', 'parent_source_sha256'} and assets == {}, 'CONFIG')
    need(stdout.startswith(LABEL+'\n') and stdout.count(LABEL) == 1, 'EXPLICIT_LEAN_LABEL')
    path = ROOT/'reference/stream27_context_storage_combo_registerederror_native.py'
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == config['parent_source_sha256'], 'EXACT_CAPTURED_VALIDATOR')
    tree = ast.parse(raw.decode())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in ('need', 'publication', 'validate')]
    need(len(functions) == 3, 'ONLY_PURE_METADATA_FUNCTIONS')
    namespace = {'json': json, 'math': math, 'PUBLICATION_FENCE': 1}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    result = namespace['validate'](stdout.removeprefix(LABEL+'\n'), stderr, rc,
                                   config['parent_config'], {})
    result.update(build_label=LABEL, host_gl_implemented=False, rollback_implemented=False,
        verification_twin_fault_immunity_inherited=False, promotion_allowed=False,
        scope='Fresh lean-R9 healthy words/cycles against identical protected-twin reference inputs; '+LABEL+
              '; retained R9 safety barrier/publication fence; no arbitrary fault, clock or PRP/board claim.')
    return result
