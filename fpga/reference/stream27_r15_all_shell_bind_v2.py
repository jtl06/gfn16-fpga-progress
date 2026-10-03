"""Additive registered-credit real shell; original d9cc cohort is preserved.

Source closure is separate from native application/aperture and real physical
gates. The old SCC-bearing shell is not made admissible by this successor.
"""
import copy
from . import stream27_r15_all_shell_bind as previous
from . import stream27_r15_pcie_shell_bind_v2 as repaired

ROOT = previous.ROOT
SELF = 'reference/stream27_r15_all_shell_bind_v2.py'
PREVIOUS_PIN = 'd9cc0e3d2bfe9ab6678c683c2008256fb8f48e417b4fa63082a055374928c852'
SHELL = 'reference/stream27_r15_pcie_shell_bind_v2.py'
SHELL_PIN = 'ebd64e7908453c49388d6485cb5a244bb78731496f23c098da9b1420e03bb0d9'
SOURCE_FREEZE = '2026-10-03T13:21:49Z'
sha, need = previous.sha, previous.need


def bind(bundle, *, fixed_schedule=0, lean_build=0, progress_watchdog=0,
         storage_to_ram=0, direct_cold=0, pcie_shell=0):
    values = (fixed_schedule, lean_build, progress_watchdog,
              storage_to_ram, direct_cold, pcie_shell)
    need(all(type(v) is int and v in (0, 1) for v in values),
         'SHELL_V2_BOOLEAN_SWITCHES')
    if not any(values):
        return copy.deepcopy(bundle)
    need(sha((ROOT / previous.SELF).read_bytes()) == PREVIOUS_PIN,
         'SHELL_V2_FROZEN_PREDECESSOR')
    core = previous.bind(bundle, fixed_schedule=fixed_schedule,
        lean_build=lean_build, progress_watchdog=progress_watchdog,
        storage_to_ram=storage_to_ram, direct_cold=direct_cold, pcie_shell=0)
    if not pcie_shell:
        return core
    need(direct_cold == 1, 'REAL_SHELL_REQUIRES_DIRECT_COLD')
    need(sha((ROOT / SHELL).read_bytes()) == SHELL_PIN,
         'SHELL_V2_FROZEN_REGISTERED_CREDIT_SOURCE')
    out = repaired.bind(core, pcie_shell=1)
    chosen = dict(zip(previous.io.compute.FLAGS, values))
    real, effective = previous._validate_shell(core, out, chosen)
    need(real['aperture_wiring'].get('registered_response_credit_only') is True
         and real['aperture_wiring'].get('minimum_downstream_response_edges') == 1,
         'SHELL_V2_REGISTERED_CREDIT_CONTRACT')
    deps = list(dict.fromkeys(out['source_dependencies'] +
                            [previous.SELF, SHELL, SELF]))
    out.update(source_dependencies=deps,
        source_sha256={p: sha((ROOT/p).read_bytes()) for p in deps},
        generated_sha256={n: sha(t) for n, t in out['files'].items()})
    out['r15_all_shell'] = dict(source_ready=True, source_freeze=SOURCE_FREEZE,
        revision=2, flags=chosen, disabled_literal_parent=True,
        literal_direct_component_top=core['top'],
        predecessor_source_preserved=True, predecessor_SCC_not_admissible=True,
        parameter_binding=real['parameter_binding'],
        effective_parameters=copy.deepcopy(effective),
        internal_compute_calendar_unchanged=True,
        external_DMA_CDC_backpressure_retained=True,
        active_pipeline_stall_allowed=False,
        initial_export_format='canonical96-full56-v1',
        raw_export_available=False, final_materialization_removed=False,
        native_qualification_inherited=False,
        source_specific_clock_qualification_inherited=False,
        board_or_license_qualification_inherited=False,
        host_GL_implementation_qualification_inherited=False,
        promotion_allowed=False)
    return out


def prepare(n=256, *, p=16, contexts=2, **flags):
    need(p == 16 and contexts == 2, 'REAL_SHELL_CLOSED_GEOMETRY')
    return bind(previous.io.compute.fixed.capture(n), **flags)
