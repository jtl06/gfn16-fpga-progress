"""Small independent Python case oracle/strict native window transcript.

Preparation evaluates N256 integer cases only, never full-N NTT or GMP on Mac.
Only actual source-bound DUT/GMP execution may produce native fixture PASS.
"""
BASES=(1009,2017)
BITS=((True,False,True,True),(False,True,True,False))


def values(rounds):
    result=[]
    for base,bits,initial in zip(BASES,BITS,(1,7),strict=True):
        modulus=base**256+1;value=initial
        for _ in range(rounds):
            for bit in bits:value=(value*value*(2 if bit else 1))%modulus
        result.append(value)
    return tuple(result)


def expected(mode='normal'):
    a,b=values(2)
    normal=(f'R15_HOST_WINDOW_NORMAL_PASS n=256 p=16 jobs=4 squares=16 raw=1152 '
        f'signed96_reads=1024 gl_checks=2 ordinal=8/8 session=7 owner_bits=56 value0={a:x} '
        f'value1={b:x} core_simulation=1 pcie=0 cdc=0 vfio=0 board=0 full_prp=0\n')
    if mode=='normal':return normal
    if mode!='rollback':raise ValueError('R15_HOST_WINDOW_LITERAL_MODE')
    a,b=values(3)
    return normal+(f'R15_HOST_WINDOW_ROLLBACK_PASS checkpoints=2 restored_ordinal=8/8 '
        f'peer_discard=8/8 common_core_reset=1 fullreload=1 recovery_squares=8 '
        f'signed96_reads=2560 session=8 value0={a:x} value1={b:x} '
        'actual_dma_drain=0 physical_reset_delivery=0 board=0\n')


def validate(stdout,stderr,returncode,*,mode='normal'):
    if mode not in ('normal','rollback','oracle-negative'):raise ValueError('R15_HOST_WINDOW_MODE')
    rc=1 if mode=='oracle-negative' else 0
    err='R15_WINDOW_SIGNED96_ORACLE_WITNESS\n' if rc else ''
    out=expected('rollback' if mode=='rollback' else 'normal')
    if type(returncode) is not int or returncode!=rc or stdout!=out or stderr!=err:
        raise ValueError('R15_HOST_WINDOW_EXACT_TRANSCRIPT')
    return dict(status='PASS_native_DUT_host_GMP_finite_fixture',mode=mode,n=256,
                PCIe=False,CDC=False,VFIO=False,board=False,full_N_PRP=False,promotion=False)
