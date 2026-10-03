"""Read generated clock configuration; this is not fitted clock qualification."""
import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from fractions import Fraction


def proof(base,system):
    base=Path(base).resolve()
    if system not in ('r15_pcie_system_v1','r15_pcie_system_v2'):
        raise ValueError('R15_CLOCK_SYSTEM')
    sopc=base/system/(system+'.sopcinfo')
    root=ET.fromstring(sopc.read_bytes())
    rates=[]
    for value in root.findall(".//parameter[@name='componentDefinition']/value"):
        if not value.text:continue
        component=ET.fromstring(value.text)
        for interface in component.findall('.//interface'):
            if interface.findtext('name')=='coreclkout_hip':
                entries={e.findtext('key'):e.findtext('value') for e in interface.findall('.//entry')}
                if entries.get('clockRateKnown')!='true':raise ValueError('R15_HIP_RATE_UNKNOWN')
                rates.append(int(entries['clockRate']))
    if not rates or set(rates)!={250000000}:raise ValueError('R15_HIP_NOT250MHZ')
    plls=list((base/'ip'/system/(system+'_core_pll')/'altera_iopll_2110/synth').glob('*.v'))
    if len(plls)!=1:raise ValueError('R15_PLL_SOURCE_CARDINALITY')
    raw=plls[0].read_bytes();text=raw.decode()
    def parameter(name):
        matches=re.findall(r'\.'+re.escape(name)+r'\(([^)]+)\)',text)
        if len(matches)!=1:raise ValueError('R15_PLL_PARAMETER '+name)
        return matches[0].strip().strip('"')
    if parameter('reference_clock_frequency')!='100.0 MHz' or parameter('m_cnt_bypass_en')!='false' or parameter('c_cnt_bypass_en0')!='false' or parameter('n_cnt_bypass_en')!='true':
        raise ValueError('R15_PLL_CONFIGURATION')
    m=int(parameter('m_cnt_hi_div'))+int(parameter('m_cnt_lo_div'))
    c=int(parameter('c_cnt_hi_div0'))+int(parameter('c_cnt_lo_div0'))
    hz=Fraction(100000000*m,c)
    if hz!=Fraction(250000000,3):raise ValueError('R15_PLL_NOT_EXACT_12NS')
    return {'schema':'r15-generated-clock-source-proof-v1',
      'status':'GENERATED_CONFIGURATION_NOT_STA',
      'sources':{str(sopc.relative_to(base)):hashlib.sha256(sopc.read_bytes()).hexdigest(),
                 str(plls[0].relative_to(base)):hashlib.sha256(raw).hexdigest()},
      'board_input_hz':100000000,'pcie_reference_hz':100000000,
      'hip_application_hz':250000000,'core_hz_numerator':hz.numerator,
      'core_hz_denominator':hz.denominator,'core_period_ns':12,
      'pll_m':m,'pll_n':1,'pll_c':c,'fitted_clock_claim':False}
