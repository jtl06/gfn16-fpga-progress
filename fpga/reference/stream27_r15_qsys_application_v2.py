"""Application-v4 component, only adds the aperture fault handshake conduit."""
from .stream27_r15_qsys_application_v1 import component as previous


def component(bundle):
    if bundle.get('r15_shell_application',{}).get('application_version') not in (3,4):
        raise ValueError('R15_QSYS_EXTERNAL_FAULT_APP_REQUIRED')
    text=previous(bundle)
    before='set_module_property NAME r15_application_v1'
    if text.count(before)!=1:raise ValueError('R15_QSYS_COMPONENT_NAME')
    text=text.replace(before,'set_module_property NAME r15_application_v2')
    text+='''add_interface aperture_fault conduit end
set_interface_property aperture_fault associatedClock pcie_clock
set_interface_property aperture_fault associatedReset hip_reset
add_interface_port aperture_fault external_fault_valid valid Input 1
add_interface_port aperture_fault external_fault_ready ready Output 1
'''
    return text
