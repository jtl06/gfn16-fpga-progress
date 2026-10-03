"""Strict small application/GMP transcript; no native execution here."""
from fpga.reference.stream27_r15_host_window_gmp_output import values


def expected(mode='normal'):
    a,b=values(2)
    normal=(f'R15_APP_WINDOW_NORMAL_PASS n=256 p=16 jobs=4 squares=16 raw=1152 '
        f'signed96_reads=1024 gl_checks=2 ordinal=8/8 generations=2/2 owner_bits=56 '
        f'value0={a:x} value1={b:x} actual_application_core_cdc=1 vendor_hip=0 '
        'vfio=0 board=0 full_prp=0\n')
    if mode=='normal':return normal
    if mode!='rollback':raise ValueError('R15_APP_WINDOW_LITERAL_MODE')
    a,b=values(3)
    return normal+(f'R15_APP_WINDOW_ROLLBACK_PASS checkpoints=2 restored_ordinal=8/8 '
        f'peer_discard=8/8 common_simulated_reset=1 fullreload=1 signed96_reads=2560 '
        f'value0={a:x} value1={b:x} hardware_reset_delivery=0 board=0\n')


def validate(stdout,stderr,returncode,*,mode='normal'):
    if mode not in ('normal','rollback','oracle-negative'):raise ValueError('R15_APP_WINDOW_MODE')
    rc=1 if mode=='oracle-negative' else 0
    err='R15_APP_WINDOW_SIGNED96_ORACLE_WITNESS\n' if rc else ''
    if type(returncode) is not int or returncode!=rc or stderr!=err or \
            stdout!=expected('rollback' if mode=='rollback' else 'normal'):
        raise ValueError('R15_APP_WINDOW_EXACT_TRANSCRIPT')
    return dict(status='PASS_native_application_core_CDC_host_GMP_finite_fixture',mode=mode,
        n=256,vendor_HIP=False,VFIO=False,board=False,hardware_reset_delivery=False,
        full_N_PRP=False,promotion=False)
