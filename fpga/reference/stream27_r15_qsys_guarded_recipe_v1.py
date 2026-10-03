"""Narrow source successor of the actually generated system recipe.

The new full64 ingress component precedes every application-address narrowing.
The HIP, PLL, part, BAR properties and installed-example DTS addresses remain
literal. No vendor output is edited in place.
"""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT='synthesis/r15_pcie_system_v1.tcl'
PIN='8c32d22fa609bd30e895573f090966e0e6c5396e1360412f759372dd95092757'


def recipe():
    raw=(ROOT/PARENT).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('R15_SYSTEM_RECIPE_PARENT')
    text=raw.decode()
    pairs=[('create_system r15_pcie_system_v1','create_system r15_pcie_system_v2'),
      ('add_instance app r15_application_v1 1.0',
       'add_instance app r15_application_v2 1.0\nadd_instance aperture r15_dma_aperture_v1 1.0'),
      ('add_connection core_pll.locked app.pll_status',
       'add_connection core_pll.locked app.pll_status\n'
       'add_connection pcie.coreclkout_hip aperture.clock\n'
       'add_connection pcie.app_nreset_status aperture.reset\n'
       'add_connection aperture.fault app.aperture_fault'),
      ('{pcie.dma_rd_master app.cold 0x00000000}',
       '{pcie.dma_rd_master aperture.write_in 0x00000000}\n'
       ' {aperture.write_out app.cold 0x00000000}'),
      ('{pcie.dma_wr_master app.export 0x00000000}',
       '{pcie.dma_wr_master aperture.read_in 0x00000000}\n'
       ' {aperture.read_out app.export 0x00000000}'),
      ('{pcie.dma_rd_master pcie.rd_dts_slave 0x01000000}',
       '{aperture.write_out pcie.rd_dts_slave 0x01000000}'),
      ('{pcie.dma_rd_master pcie.wr_dts_slave 0x01002000}',
       '{aperture.write_out pcie.wr_dts_slave 0x01002000}'),
      ('save_system r15_pcie_system_v1.qsys','save_system r15_pcie_system_v2.qsys')]
    for before,after in pairs:
        if text.count(before)!=1:raise ValueError('R15_SYSTEM_GUARDED_ANCHOR '+before)
        text=text.replace(before,after)
    reverse=text
    for before,after in reversed(pairs):reverse=reverse.replace(after,before)
    if reverse!=raw.decode():raise ValueError('R15_SYSTEM_GUARDED_REVERSE')
    return text
