"""Additive real-PCIe successor; existing R15 60/65 cohorts stay literal.

Enabled mode encloses the actual source-locked guarded AW16 vendor system.
Custom-application native gates and whole-system physical qualification remain
separate. No vendor-IP black box or functional surrogate is substituted here.
"""
import copy
import importlib
from . import stream27_r15_all_io_bind as io

ROOT = io.ROOT
SELF = 'reference/stream27_r15_all_shell_bind.py'
IO_PIN = '60b270f21ee4f0b93a8a2089af14d5a61e181e25d09c76f35c63fbdac55513bb'
SHELL = 'reference/stream27_r15_pcie_shell_bind_v1.py'
SHELL_PIN = 'a8cb3325c11aff1df533068f6d536033edd94984d2488c91e3f35ff39f9849ef'
SOURCE_FROZEN = True
SOURCE_FREEZE = '2026-10-03T12:26:20Z'
sha, need = io.sha, io.need


def _validate_shell(core, out, chosen):
    """Validate source identity, not vendor/link/board qualification."""
    need(out.get('r15_host_link', {}).get('real_pcie_ip_ready') is True,
         'REAL_SHELL_IP_CDC_IO_CONSTRAINTS')
    need(out['top'] != core['top'], 'REAL_SHELL_SEPARATE_TOP')
    need(out['geometry'] == core['geometry'], 'REAL_SHELL_INTERNAL_CALENDAR')
    need(all(out['files'].get(name) == text for name, text in core['files'].items()),
         'REAL_SHELL_LITERAL_DIRECT_COMPONENT')
    real = out.get('r15_real_shell', {})
    effective = real.get('effective_parameters', out['parameters'])
    need(all(effective.get(key) == value for key, value in chosen.items()),
         'REAL_SHELL_EFFECTIVE_FLAG_FORWARDING')
    need(all(effective.get(key) == value for key, value in core['parameters'].items()
             if key != 'PCIE_SHELL'), 'REAL_SYSTEM_COMPONENT_PARAMETER_IDENTITY')
    if real.get('parameter_binding') == 'source-locked-qsys':
        need(out['parameters'] == {}, 'REAL_BOARD_TOP_NO_HDL_OVERRIDES')
        need(effective.get('EPOCH_SEED0') == 0 and effective.get('EPOCH_SEED1') == 0,
             'REAL_SYSTEM_PRODUCTION_EPOCH_IDENTITY')
    return real, effective


def bind(bundle, *, fixed_schedule=0, lean_build=0, progress_watchdog=0,
         storage_to_ram=0, direct_cold=0, pcie_shell=0):
    values = (fixed_schedule, lean_build, progress_watchdog,
              storage_to_ram, direct_cold, pcie_shell)
    need(all(type(v) is int and v in (0, 1) for v in values),
         'SHELL_BOOLEAN_SWITCHES')
    if not any(values):
        return copy.deepcopy(bundle)
    need(sha((ROOT / io.SELF).read_bytes()) == IO_PIN,
         'SHELL_DIRECT_INTEGRATION_PIN')
    # Disabling the new boundary reproduces the exact earlier source cohort,
    # not a renamed/requalified equivalent of it.
    core = io.bind(bundle, fixed_schedule=fixed_schedule, lean_build=lean_build,
                   progress_watchdog=progress_watchdog,
                   storage_to_ram=storage_to_ram, direct_cold=direct_cold,
                   pcie_shell=0)
    if not pcie_shell:
        return core
    need(direct_cold == 1, 'REAL_SHELL_REQUIRES_DIRECT_COLD')
    need(SOURCE_FROZEN and SHELL_PIN is not None, 'REAL_SHELL_NOT_FROZEN')
    need(sha((ROOT / SHELL).read_bytes()) == SHELL_PIN,
         'REAL_SHELL_FROZEN_SOURCE_PIN')
    shell = importlib.import_module(__package__ + '.stream27_r15_pcie_shell_bind_v1')
    # The private owner must enclose the literal DIRECT65 component. Its old
    # PCIE_SHELL=0 declaration is a component default. The board system may
    # lock the enclosing application's parameters through actual Qsys source
    # settings instead of exposing fictitious board-top HDL overrides.
    out = shell.bind(core, pcie_shell=1)
    chosen = dict(zip(io.compute.FLAGS, values))
    real, effective = _validate_shell(core, out, chosen)
    deps = list(dict.fromkeys(out['source_dependencies'] + [io.SELF, SHELL, SELF]))
    out.update(rtl_sources=list(out['files']),
               generated_sha256={name: sha(text) for name, text in out['files'].items()},
               source_dependencies=deps,
               source_sha256={path: sha((ROOT / path).read_bytes()) for path in deps})
    out['r15_all_shell'] = dict(
        source_ready=True, source_freeze=SOURCE_FREEZE, flags=chosen,
        literal_direct_component_top=core['top'],
        disabled_literal_parent=True,
        parameter_binding=real.get('parameter_binding', 'hdl-top-parameters'),
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
    return bind(io.compute.fixed.capture(n), **flags)
