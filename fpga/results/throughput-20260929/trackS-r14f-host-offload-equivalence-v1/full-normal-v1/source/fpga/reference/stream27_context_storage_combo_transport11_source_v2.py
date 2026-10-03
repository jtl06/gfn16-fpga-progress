"""R11 closure-only adapter; original 5375 recipe and RTL stay immutable.

The private watchdog recipe reads both captured R10 JSON bundles. Explicitly
capture those non-Python inputs for the existing provisional geometry guard.
This wrapper changes source dependency metadata only, not any production byte.
"""
from pathlib import Path

from . import stream27_context_storage_combo_transport11_bind as source
from . import stream27_context_lean_watchdog_bind as watchdog

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_storage_combo_transport11_source_v2.py'
BASE_PIN='5375b3fd76f78b342b2ee1a6a931629ae4e3883dcc2b8091e9157f9bc3ab9d3b'
SOURCE_READY=True


def prepare(n=256,*,p=16,contexts=2,enabled=0,lean_production=0,
            crt_transport_reg=0,inverse_ingress_reg=0,term_join_transport_reg=0,
            lean_progress_watchdog=0):
    source.need(source.sha((ROOT/source.SELF).read_bytes())==BASE_PIN,'IMMUTABLE_5375_RECIPE')
    out=source.prepare(n,p=p,contexts=contexts,enabled=enabled,lean_production=lean_production,
        crt_transport_reg=crt_transport_reg,inverse_ingress_reg=inverse_ingress_reg,
        term_join_transport_reg=term_join_transport_reg,lean_progress_watchdog=lean_progress_watchdog)
    if not enabled:return out
    original=dict(out['generated_sha256'])
    deps=[SELF]
    if lean_progress_watchdog:
        deps += [(watchdog.BASE/stage/'production-bundle.json').relative_to(ROOT).as_posix()
                 for stage,_ in watchdog.PINS.values()]
    out['source_dependencies']=list(dict.fromkeys(out['source_dependencies']+deps))
    out['source_sha256']={path:source.sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    source.need(out['generated_sha256']==original,'CLOSURE_ONLY_ALL_RTL_LITERAL')
    out['context_transport11']['captured_watchdog_json_dependencies_explicit']=bool(lean_progress_watchdog)
    return out
