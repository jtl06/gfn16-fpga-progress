"""Import-safe typed healthy validator for own fixed/compute R15 captures.

Loaded by the existing worker as _native_result_validator, not a package.
Only the unchanged healthy scalar assertions are imported; no source producer,
candidate binder, current generated RTL or ancestor outcome is imported.
"""
from fpga.reference import stream27_protected_field100_native_v2 as scalar

FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=0,PCIE_SHELL=0)


def validate_fixed(stdout,stderr,rc,config,assets):
    if config!=dict(scalar.config(),fixed_schedule=1) or assets!={}:
        raise ValueError('R15_FIXED_OWN_CONFIG')
    value=scalar.validate(stdout,stderr,rc,scalar.config(),{})
    value.update(scope='Own R15 fixed-schedule protected healthy arithmetic/calendar only; unchanged scalar assertions reused, no ancestor native/clock/fault credit.',
                 fixed_schedule=1,promotion_allowed=False)
    return value


def validate_compute(stdout,stderr,rc,config,assets):
    if config!=dict(scalar.config(),r15_flags=FLAGS) or assets!={}:
        raise ValueError('R15_COMPUTE_OWN_CONFIG')
    value=scalar.validate(stdout,stderr,rc,scalar.config(),{})
    value.update(scope='Own R15 compute healthy numeric/calendar only; lean build; host GL assumed (unimplemented); no protected-fault, PCIe/CDC or clock qualification.',
                 r15_flags=FLAGS,promotion_allowed=False)
    return value
