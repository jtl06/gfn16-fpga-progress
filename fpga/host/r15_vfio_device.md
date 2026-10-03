# R15 VFIO foundation (offline only)

`VfioDevice` accepts an explicit `DeviceIdentity`, injected backend and denied-by-default
`HardwareIOGate`. Import, construction and `plan()` do no I/O. Pure mock tests exercise
container/group/device ownership, raw bounded BAR bytes and page-aligned DMA lifetimes.
Callers choose BAR index, byte order and actual register/session protocol; none is guessed.

DMA leases use `begin_dma`/`end_dma`; release/unmap/close refuse active buffers. An explicit
`quiesced=True` is a caller-provided protocol proof, never inferred from reset, exception
or link recovery. Failed/partial unmap retains backing memory until the exclusive IOMMU
context is actually detached. Failed detach retains resources for explicit cleanup retry.

The real backend supports only documented legacy Type1v2 on Linux LE64 x86_64/aarch64;
unknown group/API/aperture fails closed. No bind, programming, reset, IRQ or BAR mmap is
provided. Hardware remains UNBOUND: no actual VFIO/PCIe/DMA/board/BOINC qualification.

Provenance: [Linux VFIO lifecycle](https://docs.kernel.org/driver-api/vfio.html),
[v6.12 VFIO UAPI](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/vfio.h),
[v6.12 ioctl encoding](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/ioctl.h).
These ABI definitions do not change upstream notices or project licensing.

Pure tests: `python3 -m unittest discover -s fpga/tests -p test_r15_vfio_device.py -v`.
