"""Opt-in VFIO PCI lifecycle, generic BAR bytes and owned DMA buffers.

Import/construct/plan are inert. No binding, reset, IRQ, register-map or device
programming policy is supplied. Enabling this technical gate is NOT operator
authority. Tests must inject a backend; real deployment needs separate board,
group, protocol and quiescence authorization/qualification.

UAPI provenance (Linux v6.12, GPL-2.0 WITH Linux-syscall-note):
https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/vfio.h
https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/ioctl.h
Lifecycle: https://docs.kernel.org/driver-api/vfio.html
Numeric UAPI definitions/layouts below are interoperability facts, not vendored
kernel implementation or a blanket license change for this project.
"""
from dataclasses import dataclass
import ctypes
import fcntl
import mmap
import os
from pathlib import Path
import platform
import re
import stat
import struct
import sys
import threading

VFIO_API_VERSION = 0
VFIO_TYPE1v2_IOMMU = 3
# asm-generic _IO(';',100+n), supported here only on LE64 x86_64/aarch64.
GET_API_VERSION, CHECK_EXTENSION, SET_IOMMU = (0x3B64, 0x3B65, 0x3B66)
GROUP_GET_STATUS, GROUP_SET_CONTAINER, GROUP_UNSET_CONTAINER = (0x3B67, 0x3B68, 0x3B69)
GROUP_GET_DEVICE_FD, DEVICE_GET_INFO, DEVICE_GET_REGION_INFO = (0x3B6A, 0x3B6B, 0x3B6C)
IOMMU_GET_INFO, IOMMU_MAP_DMA, IOMMU_UNMAP_DMA = (0x3B70, 0x3B71, 0x3B72)
GROUP_VIABLE, GROUP_CONTAINER_SET, DEVICE_PCI = 1, 2, 2
REGION_READ, REGION_WRITE = 1, 2
IOMMU_PGSIZES, IOMMU_CAPS = 1, 2
DMA_READ, DMA_WRITE = 1, 2  # permissions from the device's viewpoint
GROUP = struct.Struct('=II')
DEVICE = struct.Struct('=IIIIII')
REGION = struct.Struct('=IIIIQQ')
IOMMU = struct.Struct('=IIQII')
DMA_MAP = struct.Struct('=IIQQQ')
DMA_UNMAP = struct.Struct('=IIQQ')
U64_END = 1 << 64


class VfioError(RuntimeError):
    pass


class HardwareIODenied(VfioError):
    pass


class ResourceBusy(VfioError):
    pass


class CleanupError(VfioError):
    def __init__(self, errors, resources_remaining):
        self.errors = tuple(errors)
        self.resources_remaining = resources_remaining
        super().__init__('VFIO cleanup failed: ' + '; '.join(errors))


def require(condition, reason):
    if not condition:
        raise VfioError(reason)


def interval(start, size):
    require(type(start) is int and type(size) is int and start >= 0 and size > 0
            and start < U64_END and size < U64_END and start + size <= U64_END,
            'unsigned64 range/overflow')
    return start, start + size


@dataclass(frozen=True)
class HardwareIOGate:
    enabled: bool = False
    authorization_reference: str = ''

    def check(self):
        if self.enabled is not True or not isinstance(self.authorization_reference, str) or not self.authorization_reference.strip():
            raise HardwareIODenied('Hardware I/O denied; explicit external authorization required')


@dataclass(frozen=True)
class DeviceIdentity:
    bdf: str
    iommu_group: int
    provider: str

    def validate(self):
        require(self.provider == 'linux-vfio-pci', 'unknown provider/device API')
        require(isinstance(self.bdf,str) and re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[01][0-9a-f]\.[0-7]',self.bdf), 'explicit canonical PCI BDF required')
        require(type(self.iommu_group) is int and 0 <= self.iommu_group < (1<<31), 'known IOMMU group required')


@dataclass(frozen=True)
class MemoryBlock:
    handle: object
    address: int
    size: int
    view_offset: int = 0


@dataclass(frozen=True, eq=False)
class DmaBuffer:
    address: int
    size: int
    _owner: object


@dataclass(frozen=True, eq=False)
class DmaMapping:
    iova: int
    size: int
    buffer: DmaBuffer
    _owner: object


@dataclass(frozen=True)
class BarRegion:
    index: int
    size: int
    offset: int
    flags: int


class LinuxSyscalls:
    """Actual syscall backend; construction does nothing. Never binds drivers."""
    def __init__(self, gate=None):
        self.gate = gate if gate is not None else HardwareIOGate()
        self._owned_fds = set()

    def _owned(self, fd):
        self.gate.check()
        require(fd in self._owned_fds, 'backend refuses foreign FD')

    def verify_identity(self, identity):
        self.gate.check()
        require(sys.platform == 'linux' and sys.byteorder == 'little' and platform.machine() in ('x86_64','aarch64'), 'unsupported Linux syscall ABI')
        root = Path('/sys/bus/pci/devices') / identity.bdf
        group = (root/'iommu_group').resolve(strict=True)
        driver = (root/'driver').resolve(strict=True)
        require(group == Path('/sys/kernel/iommu_groups')/str(identity.iommu_group)
                and driver.name == 'vfio-pci', 'actual group/driver does not match; no binding attempted')
        return True

    def open(self, path):
        self.gate.check()
        require(isinstance(path,str) and re.fullmatch(r'/dev/vfio/(vfio|0|[1-9][0-9]*)',path), 'exact VFIO node only')
        fd = os.open(path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            require(stat.S_ISCHR(os.fstat(fd).st_mode), 'VFIO node is not a character device')
        except BaseException:
            os.close(fd)
            raise
        self._owned_fds.add(fd)
        return fd

    def close(self, fd):
        self._owned(fd)
        self._owned_fds.remove(fd)  # Linux close errors must not retry reused FDs
        os.close(fd)

    def ioctl(self, fd, request, argument=0):
        self._owned(fd)
        result = fcntl.ioctl(fd, request, argument, True) if isinstance(argument, bytearray) else fcntl.ioctl(fd, request, argument)
        if request == GROUP_GET_DEVICE_FD and type(result) is int and result >= 0:
            self._owned_fds.add(result)
        return result

    def pread(self, fd, size, offset):
        self._owned(fd)
        return os.pread(fd,size,offset)

    def pwrite(self, fd, data, offset):
        self._owned(fd)
        return os.pwrite(fd,data,offset)

    def page_size(self):
        return os.sysconf('SC_PAGE_SIZE')

    def allocate(self, size, alignment):
        self.gate.check()
        # Anonymous memory only. Owner retains this object until IOMMU teardown.
        handle = mmap.mmap(-1,size+alignment,flags=mmap.MAP_PRIVATE|mmap.MAP_ANONYMOUS,
                           prot=mmap.PROT_READ|mmap.PROT_WRITE)
        try:
            base = ctypes.addressof(ctypes.c_char.from_buffer(handle))
            offset = (-base) % alignment
            return MemoryBlock(handle,base+offset,size,offset)
        except BaseException:
            handle.close()
            raise

    def view(self, block):
        return memoryview(block.handle)[block.view_offset:block.view_offset+block.size]

    def free(self, block):
        block.handle.close()


class VfioDevice:
    """Exclusive owned container/group; callers supply protocol/quiescence.

    A backend implements verify_identity/open/close/ioctl/pread/pwrite/page_size/
    allocate/view/free. No constructor or plan() backend call occurs. No BAR
    mmap is exposed, avoiding sparse-region mmap assumptions. BAR writes and
    DMA bookkeeping are not evidence of hardware completion or a reset.
    """
    def __init__(self, identity=None, *, backend=None, gate=None, max_dma_bytes=64<<20):
        self.identity = identity
        self.gate = gate if gate is not None else HardwareIOGate()
        require(type(self.gate) is HardwareIOGate, 'explicit hardware gate type required')
        self.backend = backend if backend is not None else LinuxSyscalls(self.gate)
        require(type(max_dma_bytes) is int and max_dma_bytes > 0, 'positive owned DMA budget required')
        self.max_dma_bytes = max_dma_bytes
        self._owner = object()
        self._lock = threading.RLock()
        self._container = self._group = self._device = None
        self._attached = False
        self._state = 'new'
        self._buffers = {}
        self._maps = {}  # mapping -> active use count
        self._uncertain_maps = set()
        self._bars = {}
        self._page = None
        self._iova_ranges = ()
        self._regions = 0
        self._io_started = False

    def plan(self):
        return dict(state=self._state,hardware_io_default_denied=True,
                    identity=self.identity,backend_io_performed=self._io_started,
                    unsupported=['driver binding','device reset','IRQs','application register ABI','IOMMUFD cdev','NOIOMMU'])

    def _ioctl(self, fd, request, argument=0):
        self.gate.check()
        result = self.backend.ioctl(fd,request,argument)
        require(type(result) is int and result >= 0, 'syscall returned failure')
        return result

    def _info(self, fd, request, size, minimum, index=None):
        for _ in range(3):
            require(size <= 1<<20, 'unbounded VFIO capability buffer')
            data = bytearray(size)
            struct.pack_into('=I',data,0,size)
            if index is not None:
                struct.pack_into('=I',data,8,index)
            self._ioctl(fd,request,data)
            needed = struct.unpack_from('=I',data)[0]
            require(needed >= minimum, 'truncated VFIO info')
            if needed <= size:
                return data
            size = needed
        raise VfioError('unstable VFIO capability size')

    def connect(self):
        with self._lock:
            self.gate.check()
            require(self._state == 'new' and type(self.identity) is DeviceIdentity, 'explicit identity/new lifecycle required')
            self.identity.validate()
            self._io_started = True
            require(self.backend.verify_identity(self.identity) is True, 'unknown actual group/device')
            self._state = 'opening'
            try:
                fd = self.backend.open('/dev/vfio/vfio')
                require(type(fd) is int and fd >= 0, 'invalid owned container FD')
                self._container = fd
                require(self._ioctl(self._container,GET_API_VERSION) == VFIO_API_VERSION, 'unsupported VFIO API')
                require(self._ioctl(self._container,CHECK_EXTENSION,VFIO_TYPE1v2_IOMMU) > 0, 'Type1v2 IOMMU unavailable; no unsafe fallback')
                fd = self.backend.open('/dev/vfio/'+str(self.identity.iommu_group))
                require(type(fd) is int and fd >= 0, 'invalid owned group FD')
                self._group = fd
                group = self._info(self._group,GROUP_GET_STATUS,GROUP.size,GROUP.size)
                flags = GROUP.unpack_from(group)[1]
                require(flags & GROUP_VIABLE and not flags & GROUP_CONTAINER_SET, 'group not viable/exclusively available')
                self._ioctl(self._group,GROUP_SET_CONTAINER,bytearray(struct.pack('=i',self._container)))
                self._attached = True
                self._ioctl(self._container,SET_IOMMU,VFIO_TYPE1v2_IOMMU)
                self._device = self._ioctl(self._group,GROUP_GET_DEVICE_FD,bytearray(self.identity.bdf.encode('ascii')+b'\0'))
                device = self._info(self._device,DEVICE_GET_INFO,DEVICE.size,16)
                _,flags,self._regions,_ = struct.unpack_from('=IIII',device)
                require(flags & DEVICE_PCI and self._regions >= 6, 'unsupported/non-PCI device regions')
                iommu = self._info(self._container,IOMMU_GET_INFO,IOMMU.size,16)
                _,flags,pages = struct.unpack_from('=IIQ',iommu)
                require(flags & IOMMU_PGSIZES and pages, 'unknown IOMMU page sizes')
                cpu_page = self.backend.page_size()
                require(type(cpu_page) is int and cpu_page > 0 and not cpu_page & (cpu_page-1), 'unknown host page size')
                self._page = max(cpu_page,pages & -pages)
                require(pages & self._page, 'host/IOMMU page-size incompatibility')
                self._iova_ranges = self._parse_ranges(iommu) if flags & IOMMU_CAPS else ()
                self._state = 'open'
                return self
            except BaseException as primary:
                try:
                    self.close()
                except CleanupError as cleanup:
                    primary.add_note(str(cleanup))
                raise

    @staticmethod
    def _parse_ranges(data):
        require(len(data) >= IOMMU.size, 'missing IOMMU capability offset')
        argsz = struct.unpack_from('=I',data)[0]
        require(IOMMU.size <= argsz <= len(data), 'invalid capability buffer length')
        offset = struct.unpack_from('=I',data,16)[0]
        seen, ranges = set(), []
        while offset:
            require(offset not in seen and offset >= IOMMU.size and offset+8 <= argsz, 'invalid/cyclic IOMMU capability')
            seen.add(offset)
            kind,version,next_offset = struct.unpack_from('=HHI',data,offset)
            if kind == 1:
                require(version == 1 and offset+16 <= argsz, 'unsupported IOVA range capability')
                count,reserved = struct.unpack_from('=II',data,offset+8)
                require(reserved == 0 and 0 < count <= 4096 and offset+16+16*count <= argsz, 'invalid IOVA range count')
                for number in range(count):
                    start,end = struct.unpack_from('=QQ',data,offset+16+16*number)
                    require(start <= end, 'invalid IOVA aperture')
                    ranges.append((start,end+1))
            offset = next_offset
        return tuple(ranges)

    def _open(self):
        self.gate.check()
        require(self._state == 'open' and self._device is not None, 'device not open')

    def bar_region(self, index):
        with self._lock:
            self._open()
            require(type(index) is int and 0 <= index <= 5 and index < self._regions, 'PCI BAR index only')
            if index not in self._bars:
                raw = self._info(self._device,DEVICE_GET_REGION_INFO,REGION.size,REGION.size,index)
                _,flags,actual,_,size,offset = REGION.unpack_from(raw)
                require(actual == index and size > 0, 'unknown/unimplemented BAR')
                interval(offset,size)
                self._bars[index] = BarRegion(index,size,offset,flags)
            return self._bars[index]

    def _bar_access(self, index, offset, size, flag):
        region = self.bar_region(index)
        require(type(size) is int and size in (1,2,4,8) and type(offset) is int
                and offset >= 0 and offset % size == 0 and offset+size <= region.size, 'BAR width/alignment/bounds')
        require(region.flags & flag, 'BAR access permission unavailable')
        require(region.offset+offset+size <= 1<<63, 'BAR file-offset overflow')
        return region.offset+offset

    def read_bar(self, index, offset, size):
        with self._lock:
            absolute = self._bar_access(index,offset,size,REGION_READ)
            data = self.backend.pread(self._device,size,absolute)
            require(isinstance(data,bytes) and len(data) == size, 'short BAR read')
            return data

    def write_bar(self, index, offset, data):
        with self._lock:
            require(isinstance(data,bytes), 'BAR raw bytes required; no guessed byte order')
            absolute = self._bar_access(index,offset,len(data),REGION_WRITE)
            require(self.backend.pwrite(self._device,data,absolute) == len(data), 'short BAR write; do not auto-retry side effects')

    def allocate_dma(self, size):
        with self._lock:
            self._open()
            require(type(size) is int and size > 0 and size % self._page == 0
                    and sum(buf.size for buf in self._buffers)+size <= self.max_dma_bytes, 'DMA alignment/budget')
            block = self.backend.allocate(size,self._page)
            try:
                require(type(block) is MemoryBlock and type(block.address) is int and block.size == size and block.address > 0 and block.address % self._page == 0, 'invalid allocated DMA memory')
                interval(block.address,size)
            except BaseException:
                self.backend.free(block)
                raise
            buffer = DmaBuffer(block.address,size,self._owner)
            self._buffers[buffer] = block
            return buffer

    def buffer_view(self, buffer):
        with self._lock:
            self._open()
            require(buffer in self._buffers and buffer._owner is self._owner, 'foreign/released DMA buffer')
            return self.backend.view(self._buffers[buffer])

    def map_dma(self, buffer, iova, *, read, write):
        with self._lock:
            self._open()
            require(buffer in self._buffers and buffer._owner is self._owner, 'foreign/released DMA buffer')
            require(not self._uncertain_maps, 'uncertain DMA mapping; teardown required before new maps')
            require(type(read) is bool and type(write) is bool and (read or write), 'explicit DMA permissions required')
            start,end = interval(iova,buffer.size)
            require(iova % self._page == 0 and self._iova_ranges and any(lo <= start and end <= hi for lo,hi in self._iova_ranges), 'DMA alignment/unknown or outside IOVA aperture')
            require(not any(start < old.iova+old.size and old.iova < end for old in self._maps), 'overlapping DMA IOVA')
            require(not any(old.buffer is buffer for old in self._maps), 'buffer already mapped')
            mapping = DmaMapping(iova,buffer.size,buffer,self._owner)
            # Retain ownership even on uncertain map failure; close() disposes
            # this exclusive IOMMU context before freeing backing memory.
            self._maps[mapping] = 0
            self._uncertain_maps.add(mapping)
            self._ioctl(self._container,IOMMU_MAP_DMA,bytearray(DMA_MAP.pack(DMA_MAP.size,(DMA_READ if read else 0)|(DMA_WRITE if write else 0),buffer.address,iova,buffer.size)))
            self._uncertain_maps.discard(mapping)
            return mapping

    def begin_dma(self, mapping):
        with self._lock:
            self._open()
            require(mapping in self._maps and mapping._owner is self._owner, 'foreign/unmapped DMA mapping')
            require(not self._uncertain_maps, 'uncertain DMA mapping; cannot begin DMA')
            self._maps[mapping] += 1

    def end_dma(self, mapping, *, quiesced=False):
        with self._lock:
            require(mapping in self._maps and mapping._owner is self._owner and self._maps[mapping] > 0, 'no owned active DMA use')
            if quiesced is not True:
                raise ResourceBusy('actual protocol-specific DMA completion/drain proof required')
            self._maps[mapping] -= 1

    def unmap_dma(self, mapping, *, quiesced=False):
        with self._lock:
            self._open()
            require(mapping in self._maps and mapping._owner is self._owner, 'foreign/unmapped DMA mapping')
            if self._maps[mapping] or quiesced is not True:
                raise ResourceBusy('active/unknown-quiescence DMA cannot be unmapped')
            self._unmap(mapping)

    def _unmap(self, mapping):
        data = bytearray(DMA_UNMAP.pack(DMA_UNMAP.size,0,mapping.iova,mapping.size))
        self._uncertain_maps.add(mapping)
        self._ioctl(self._container,IOMMU_UNMAP_DMA,data)
        require(DMA_UNMAP.unpack(data)[3] == mapping.size, 'partial/unknown DMA unmap; retain backing allocation')
        del self._maps[mapping]
        self._uncertain_maps.discard(mapping)

    def release_buffer(self, buffer):
        with self._lock:
            require(buffer in self._buffers and buffer._owner is self._owner, 'foreign/released DMA buffer')
            if any(mapping.buffer is buffer for mapping in self._maps):
                raise ResourceBusy('mapped buffer cannot be released')
            self.backend.free(self._buffers[buffer])
            del self._buffers[buffer]

    def close(self, *, quiesced=False):
        with self._lock:
            if any(self._maps.values()) or (self._maps and quiesced is not True):
                raise ResourceBusy('close refuses active or unknown-quiescence DMA')
            errors = []
            self._state = 'closing'
            if self._device is not None:
                fd,self._device = self._device,None
                try:
                    self.backend.close(fd)
                except OSError as failure:
                    errors.append('device close: '+str(failure))
            for mapping in list(self._maps):
                try:
                    self._unmap(mapping)
                except (VfioError,OSError) as failure:
                    errors.append('DMA unmap: '+str(failure))
            if self._attached:
                try:
                    self._ioctl(self._group,GROUP_UNSET_CONTAINER)
                    self._attached = False
                    self._maps.clear()  # last owned group detached: context gone
                    self._uncertain_maps.clear()
                except (VfioError,OSError) as failure:
                    errors.append('group detach: '+str(failure))
            if not self._attached:
                for buffer in list(self._buffers):
                    try:
                        self.release_buffer(buffer)
                    except (VfioError,OSError,BufferError) as failure:
                        errors.append('buffer free: '+str(failure))
                for name in ('_group','_container'):
                    fd = getattr(self,name)
                    if fd is not None:
                        setattr(self,name,None)  # never retry an ambiguous close fd
                        try:
                            self.backend.close(fd)
                        except OSError as failure:
                            errors.append(name+' close: '+str(failure))
            remaining = self._attached or bool(self._buffers) or bool(self._maps)
            self._state = 'closing' if remaining else 'closed'
            self._bars.clear()
            if errors:
                raise CleanupError(errors,remaining)

    def __enter__(self):
        return self.connect()

    def __exit__(self, kind, value, traceback):
        # No invented quiescence acknowledgement from an exception/reset.
        try:
            self.close()
        except (CleanupError,ResourceBusy) as cleanup:
            if value is None:
                raise
            value.add_note(str(cleanup))
