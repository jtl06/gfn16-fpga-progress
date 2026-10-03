# SPDX-License-Identifier: Apache-2.0
"""Original R15 userspace abstractions, not an operating VFIO driver.

No file/device opens, binding, ioctls, DMA, or kernel modifications occur in
this module. MMIO is injectable; only a bounded bytearray test region exists.
Actual VFIO group viability/region/DMA/IRQ integration awaits board authority.
The direct cold protocol is owned by stream27_r15_host_link_model_v1.
"""
from collections import deque
from dataclasses import dataclass
import re
import struct
from xml.etree import ElementTree as ET

from fpga.reference.stream27_r15_host_link_model_v1 import Word, raw_word_ok
from .r15_arithmetic import HostFault, need


class MockBar:
    def __init__(self, size=4096):
        need(type(size) is int and size >= 256, 'BAR_SIZE')
        self.data = bytearray(size)

    def check(self, offset):
        need(type(offset) is int and offset >= 0 and offset % 4 == 0 and
             offset+4 <= len(self.data), 'MMIO_BOUNDS_ALIGNMENT')

    def read32(self, offset):
        self.check(offset)
        return struct.unpack_from('<I', self.data, offset)[0]

    def write32(self, offset, value):
        self.check(offset)
        need(type(value) is int and 0 <= value < 1 << 32, 'MMIO32')
        struct.pack_into('<I', self.data, offset, value)


@dataclass(frozen=True)
class VfioPlan:
    """Reviewable capability requirements; deliberately cannot execute."""
    device: str
    iommu_group: int
    bar: int
    bytes: int

    def requests(self, *, enabled=False):
        need(enabled is True, 'VFIO_OFF')
        need(re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', self.device)
             is not None and type(self.iommu_group) is int and self.iommu_group >= 0 and
             type(self.bar) is int and 0 <= self.bar <= 5 and type(self.bytes) is int and
             self.bytes > 0, 'VFIO_CAPABILITY')
        return ('GET_API_VERSION', 'CHECK_EXTENSION', 'GROUP_GET_STATUS_VIABLE',
                'GROUP_SET_CONTAINER', 'SET_IOMMU', 'GROUP_GET_DEVICE_FD',
                'DEVICE_GET_INFO', 'DEVICE_GET_REGION_INFO', 'REGION_SIZE_BOUNDS',
                'IOMMU_MAP_DMA_SCOPED_BUFFER', 'IRQ_EVENTFD_SETUP')

    def execute(self):
        raise HostFault('R15_HOST_REAL_DEVICE_UNIMPLEMENTED_UNAUTHORIZED')


def cold_words(n, base, digits, c0, c1):
    """Actual R15 body: block-major raw32 image, c0[16], c1[16]."""
    need(n in (32, 256, 65536) and len(digits) == n and len(c0) == len(c1) == 16,
         'COLD_LENGTH')
    words = tuple(digits)+tuple(c0)+tuple(c1)
    result = []
    for index, value in enumerate(words):
        need(type(value) is int and -(1 << 31) <= value < 1 << 32, 'COLD_FULL32')
        wire = value & 0xffffffff
        need(raw_word_ok(n, base, index, wire), 'COLD_DOMAIN')
        result.append(wire)
    return tuple(result)


class DirectColdClient:
    """Driver logic over the executable model, not PCIe transport evidence."""
    def __init__(self, endpoint, *, enabled=False):
        need(enabled is True, 'DIRECT_COLD_OFF')
        self.endpoint = endpoint

    def load(self, context, owner, profile, words, *, grant, idle, lease_safe,
             maximum_edges=1000000):
        need(len(words) == self.endpoint.words, 'COLD_LENGTH')
        session, lease = self.endpoint.begin(context, owner, profile,
            core_idle=idle(), lease_safe=lease_safe)
        accepted = 0
        try:
            for edge in range(maximum_edges):
                if accepted < len(words):
                    word = Word(session, lease, context, owner, accepted, words[accepted])
                    if self.endpoint.accept(word):
                        accepted += 1
                if self.endpoint.queue:
                    word = self.endpoint.queue[0]
                    target = self.endpoint.tx['route'][word.index]
                    permission, busy = grant(edge, session, lease, target)
                    self.endpoint.step(grant=permission, busy_ports=busy,
                                       context_still_idle=idle())
                need(self.endpoint.tx is not None and self.endpoint.tx['fault'] is None,
                     'COLD_ABORT')
                if accepted == self.endpoint.tx['applied'] == len(words):
                    return self.endpoint.commit(session=session, lease=lease, context=context,
                        owner=owner, core_idle=idle(), profile_ok=True)
            raise HostFault('R15_HOST_COLD_SERVICE_TIMEOUT')
        except Exception:
            # No undo of applied destination words. Full reload required.
            self.endpoint.cancel()
            raise


class DescriptorStream:
    """Host-side model: idle stalls legal; launch underflow is typed abort."""
    def __init__(self, depth=8, *, enabled=False):
        need(enabled is True and type(depth) is int and 1 <= depth <= 1024,
             'DESCRIPTOR_OFF_OR_DEPTH')
        self.depth, self.queue, self.error = depth, deque(), None
        self.sequence = 0

    def push(self, owner, sequence, double):
        need(self.error is None and type(owner) is int and 0 <= owner < 1 << 56 and
             type(sequence) is int and sequence == self.sequence and type(double) is bool,
             'DESCRIPTOR_OWNER_ORDER')
        if len(self.queue) == self.depth:
            return False
        self.queue.append((owner, sequence, double))
        self.sequence += 1
        return True

    def launch(self, owner, *, due):
        if not due:
            return None
        if self.error is not None or not self.queue or self.queue[0][0] != owner:
            self.error = 'DESCRIPTOR_UNDERFLOW_OR_OWNER'
            raise HostFault('R15_HOST_'+self.error)
        return self.queue.popleft()


def anonymous_platform_xml(application, version, executable, *, enabled=False):
    """Return a scaffold string; never writes into a BOINC project/slot."""
    need(enabled is True, 'BOINC_WRAPPER_OFF')
    need(type(application) is str and re.fullmatch(r'[A-Za-z0-9_.-]+', application) and
         type(version) is int and version > 0 and type(executable) is str and
         re.fullmatch(r'[A-Za-z0-9_.-]+', executable) and executable not in ('.', '..'),
         'BOINC_MANIFEST_INPUT')
    root = ET.Element('app_info')
    app = ET.SubElement(root, 'app')
    ET.SubElement(app, 'name').text = application
    file_info = ET.SubElement(root, 'file_info')
    ET.SubElement(file_info, 'name').text = executable
    ET.SubElement(file_info, 'executable')
    app_version = ET.SubElement(root, 'app_version')
    ET.SubElement(app_version, 'app_name').text = application
    ET.SubElement(app_version, 'version_num').text = str(version)
    for key in ('avg_ncpus', 'max_ncpus'):
        ET.SubElement(app_version, key).text = '1'
    file_ref = ET.SubElement(app_version, 'file_ref')
    ET.SubElement(file_ref, 'file_name').text = executable
    ET.SubElement(file_ref, 'main_program')
    return ET.tostring(root, encoding='unicode')
