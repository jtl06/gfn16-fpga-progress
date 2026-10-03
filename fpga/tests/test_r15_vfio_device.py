"""Pure fake-syscall tests; no Linux device, sysfs, mmap or native invocation."""
import struct
import unittest
from unittest.mock import patch
from fpga.host import r15_vfio_device as v


class FakeBackend:
    def __init__(self):
        self.events=[];self.owned=set();self.blocks={};self.failed=set()
        self.api=0;self.extension=1;self.group_flags=v.GROUP_VIABLE
        self.device_flags=v.DEVICE_PCI;self.region_flags=v.REGION_READ|v.REGION_WRITE
        self.region_size=4096;self.region_offset=0x200000;self.unmap_size=None
        self.aperture=True;self.bad_cap=False;self.identity_ok=True
        self.next_address=0x1000000;self.mem=bytearray(4096)
        self.short_read=False;self.short_write=False

    def verify_identity(self, identity):
        self.events.append(('identity',identity));return self.identity_ok

    def open(self,path):
        fd=10 if path.endswith('/vfio') else 11
        self.events.append(('open',path,fd))
        if ('open',fd) in self.failed:raise OSError('injected open failure')
        self.owned.add(fd);return fd

    def close(self,fd):
        self.events.append(('close',fd))
        if fd not in self.owned:raise AssertionError('closing unowned FD')
        self.owned.remove(fd)

    def ioctl(self,fd,request,arg=0):
        self.events.append(('ioctl',fd,request,bytes(arg) if isinstance(arg,bytearray) else arg))
        if request in self.failed:raise OSError('injected ioctl failure')
        if request==v.GET_API_VERSION:return self.api
        if request==v.CHECK_EXTENSION:return self.extension
        if request==v.GROUP_GET_STATUS:v.GROUP.pack_into(arg,0,8,self.group_flags)
        elif request==v.GROUP_GET_DEVICE_FD:self.owned.add(12);return 12
        elif request==v.DEVICE_GET_INFO:v.DEVICE.pack_into(arg,0,24,self.device_flags,9,5,0,0)
        elif request==v.IOMMU_GET_INFO:
            if not self.aperture:v.IOMMU.pack_into(arg,0,24,v.IOMMU_PGSIZES,4096,0,0)
            else:
                struct.pack_into('=I',arg,0,56)
                if len(arg)>=56:
                    v.IOMMU.pack_into(arg,0,56,v.IOMMU_PGSIZES|v.IOMMU_CAPS,4096,24,0)
                    struct.pack_into('=HHIIIQQ',arg,24,1,1,24 if self.bad_cap else 0,1,0,0x1000,0xfffff)
        elif request==v.DEVICE_GET_REGION_INFO:
            index=struct.unpack_from('=I',arg,8)[0]
            v.REGION.pack_into(arg,0,32,self.region_flags,index,0,self.region_size,self.region_offset)
        elif request==v.IOMMU_UNMAP_DMA:
            if self.unmap_size is not None:struct.pack_into('=Q',arg,16,self.unmap_size)
        return 0

    def page_size(self):return 4096
    def pread(self,fd,size,offset):
        self.events.append(('pread',fd,size,offset))
        data=bytes(self.mem[offset-self.region_offset:offset-self.region_offset+size])
        return data[:-1] if self.short_read else data
    def pwrite(self,fd,data,offset):
        self.events.append(('pwrite',fd,data,offset))
        self.mem[offset-self.region_offset:offset-self.region_offset+len(data)]=data
        return len(data)-1 if self.short_write else len(data)
    def allocate(self,size,alignment):
        self.events.append(('allocate',size,alignment))
        block=v.MemoryBlock(bytearray(size),self.next_address,size)
        self.next_address+=size;self.blocks[block.address]=block;return block
    def view(self,block):return memoryview(block.handle)
    def free(self,block):
        self.events.append(('free',block.address))
        if block.address not in self.blocks:raise AssertionError('free foreign block')
        del self.blocks[block.address]


class TestVfio(unittest.TestCase):
    def device(self,backend=None,**kwargs):
        backend=backend or FakeBackend()
        d=v.VfioDevice(v.DeviceIdentity('0000:03:00.0',17,'linux-vfio-pci'),backend=backend,
                       gate=v.HardwareIOGate(True,'mock-only test authorization'),**kwargs)
        return d,backend

    def connected(self,**kwargs):
        d,b=self.device(**kwargs);d.connect();return d,b

    def test_default_constructor_plan_and_denial_are_inert(self):
        b=FakeBackend()
        with patch.object(v.os,'open',side_effect=AssertionError('real open')),patch.object(v.fcntl,'ioctl',side_effect=AssertionError('real ioctl')),patch.object(v.mmap,'mmap',side_effect=AssertionError('real mmap')),patch.object(v.Path,'resolve',side_effect=AssertionError('real sysfs')):
            d=v.VfioDevice(backend=b);self.assertFalse(d.plan()['backend_io_performed'])
            with self.assertRaises(v.HardwareIODenied):d.connect()
            d.close();self.assertEqual(b.events,[])

    def test_missing_authorization_denies_even_enabled_gate(self):
        d,b=self.device();d.gate=v.HardwareIOGate(True,'')
        with self.assertRaises(v.HardwareIODenied):d.connect()
        self.assertEqual(b.events,[])

    def test_real_backend_is_denied_when_called_directly(self):
        b=v.LinuxSyscalls()
        with patch.object(v.os,'open',side_effect=AssertionError('real open')),patch.object(v.fcntl,'ioctl',side_effect=AssertionError('real ioctl')),patch.object(v.Path,'resolve',side_effect=AssertionError('real sysfs')),patch.object(v.mmap,'mmap',side_effect=AssertionError('real mmap')):
            for call in [lambda:b.open('/dev/vfio/vfio'),lambda:b.verify_identity(v.DeviceIdentity('0000:03:00.0',17,'linux-vfio-pci')),lambda:b.ioctl(10,v.GET_API_VERSION),lambda:b.pread(10,4,0),lambda:b.pwrite(10,b'1234',0),lambda:b.close(10),lambda:b.allocate(4096,4096)]:
                with self.assertRaises(v.HardwareIODenied):call()

    def test_real_backend_refuses_foreign_fd_and_arbitrary_nodes(self):
        b=v.LinuxSyscalls(v.HardwareIOGate(True,'mock-only'))
        with patch.object(v.os,'open',side_effect=AssertionError('real open')),patch.object(v.fcntl,'ioctl',side_effect=AssertionError('real ioctl')),patch.object(v.os,'close',side_effect=AssertionError('real close')):
            with self.assertRaises(v.VfioError):b.open('/dev/mem')
            with self.assertRaises(v.VfioError):b.ioctl(10,v.GET_API_VERSION)
            with self.assertRaises(v.VfioError):b.close(10)

    def test_buffer_free_failure_retains_allocation_for_retry(self):
        d,b=self.connected();buf=d.allocate_dma(4096)
        original=b.free
        def fail(block):raise BufferError('exported view')
        b.free=fail
        with self.assertRaises(v.CleanupError) as caught:d.close()
        self.assertTrue(caught.exception.resources_remaining);self.assertIn(buf.address,b.blocks)
        self.assertFalse(b.owned);b.free=original;d.close();self.assertFalse(b.blocks)

    def test_unknown_provider_group_and_bdf_fail_before_backend(self):
        for identity in [None,v.DeviceIdentity('0000:03:00.0',17,'unknown'),v.DeviceIdentity('0000:03:00.0',None,'linux-vfio-pci'),v.DeviceIdentity('0000:03:20.0',17,'linux-vfio-pci')]:
            with self.subTest(identity=identity):
                d,b=self.device();d.identity=identity
                with self.assertRaises(v.VfioError):d.connect()
                self.assertEqual(b.events,[])

    def test_actual_identity_mismatch_never_opens(self):
        d,b=self.device();b.identity_ok=False
        with self.assertRaises(v.VfioError):d.connect()
        self.assertEqual(len(b.events),1);self.assertFalse(b.owned)

    def test_happy_lifecycle_and_ownership_cleanup_order(self):
        d,b=self.connected();self.assertTrue(d.plan()['backend_io_performed'])
        d.close();self.assertFalse(b.owned)
        close_index=b.events.index(('close',12))
        unset_index=next(i for i,e in enumerate(b.events) if e[:3]==('ioctl',11,v.GROUP_UNSET_CONTAINER))
        self.assertLess(close_index,unset_index);self.assertLess(unset_index,b.events.index(('close',11)))
        before=len(b.events);d.close();self.assertEqual(before,len(b.events))

    def test_unsupported_api_extension_or_group_close_only_owned_fds(self):
        for attr,value in [('api',1),('extension',0),('group_flags',0),('group_flags',v.GROUP_VIABLE|v.GROUP_CONTAINER_SET),('device_flags',0)]:
            with self.subTest(attr=attr,value=value):
                d,b=self.device();setattr(b,attr,value)
                with self.assertRaises(v.VfioError):d.connect()
                self.assertFalse(b.owned)

    def test_partial_open_cleanup_at_each_stage(self):
        for failure in [('open',11),v.GROUP_SET_CONTAINER,v.SET_IOMMU,v.GROUP_GET_DEVICE_FD,v.DEVICE_GET_INFO,v.IOMMU_GET_INFO]:
            with self.subTest(failure=failure):
                d,b=self.device();b.failed.add(failure)
                with self.assertRaises(OSError):d.connect()
                self.assertFalse(b.owned);self.assertFalse(b.blocks)

    def test_invalid_backend_fd_is_not_treated_as_owned(self):
        d,b=self.device();b.open=lambda path:-1
        with self.assertRaises(v.VfioError):d.connect()
        self.assertFalse(any(e[0]=='close' for e in b.events))

    def test_bar_roundtrip_raw_bytes_without_endian_guess(self):
        d,b=self.connected();d.write_bar(2,8,b'\x12\x34\x56\x78')
        self.assertEqual(d.read_bar(2,8,4),b'\x12\x34\x56\x78')
        self.assertIn(('pwrite',12,b'\x12\x34\x56\x78',0x200008),b.events);d.close()

    def test_bar_bounds_alignment_width_and_index(self):
        d,b=self.connected()
        for index,offset,size in [(6,0,4),(True,0,4),(2,-4,4),(2,1,4),(2,4096,4),(2,0,3),(2,0,True),(2,2**64,4)]:
            with self.subTest(index=index,offset=offset,size=size):
                with self.assertRaises(v.VfioError):d.read_bar(index,offset,size)
        self.assertFalse(any(e[0]=='pread' for e in b.events));d.close()

    def test_bar_permission_short_io_and_file_offset_overflow(self):
        for kind in ('read_permission','write_permission','short_read','short_write','overflow'):
            with self.subTest(kind=kind):
                d,b=self.connected()
                if kind=='read_permission':b.region_flags=v.REGION_WRITE
                if kind=='write_permission':b.region_flags=v.REGION_READ
                if kind=='short_read':b.short_read=True
                if kind=='short_write':b.short_write=True
                if kind=='overflow':b.region_offset=2**63-2
                with self.assertRaises(v.VfioError):
                    if kind in ('write_permission','short_write'):d.write_bar(2,0,b'abcd')
                    else:d.read_bar(2,0,4)
                if kind=='short_write':self.assertEqual(sum(e[0]=='pwrite' for e in b.events),1)
                d.close()

    def test_dma_map_layout_view_unmap_and_release(self):
        d,b=self.connected();buf=d.allocate_dma(4096);view=d.buffer_view(buf);view[:4]=b'test';view.release()
        mapping=d.map_dma(buf,0x4000,read=True,write=False)
        packed=next(e[3] for e in b.events if e[:3]==('ioctl',10,v.IOMMU_MAP_DMA))
        self.assertEqual(v.DMA_MAP.unpack(packed),(32,v.DMA_READ,buf.address,0x4000,4096))
        with self.assertRaises(v.ResourceBusy):d.unmap_dma(mapping)
        with self.assertRaises(v.ResourceBusy):d.release_buffer(buf)
        d.unmap_dma(mapping,quiesced=True);d.release_buffer(buf);d.close();self.assertFalse(b.blocks)

    def test_active_dma_refuses_unmap_close_and_free(self):
        d,b=self.connected();buf=d.allocate_dma(4096);m=d.map_dma(buf,0x4000,read=True,write=True);d.begin_dma(m)
        before=len(b.events)
        for call in [lambda:d.unmap_dma(m,quiesced=True),lambda:d.close(quiesced=True),lambda:d.release_buffer(buf),lambda:d.end_dma(m)]:
            with self.assertRaises(v.ResourceBusy):call()
        self.assertEqual(len(b.events),before)
        d.end_dma(m,quiesced=True);d.close(quiesced=True);self.assertFalse(b.blocks)

    def test_dma_lease_count_requires_all_users_quiesced(self):
        d,b=self.connected();buf=d.allocate_dma(4096);m=d.map_dma(buf,0x4000,read=True,write=False)
        d.begin_dma(m);d.begin_dma(m);d.end_dma(m,quiesced=True)
        with self.assertRaises(v.ResourceBusy):d.close(quiesced=True)
        d.end_dma(m,quiesced=True);d.close(quiesced=True)

    def test_alignment_budget_overflow_aperture_and_overlap(self):
        d,b=self.connected(max_dma_bytes=8192)
        for size in (0,1,4097,True,12288):
            with self.assertRaises(v.VfioError):d.allocate_dma(size)
        a=d.allocate_dma(4096);c=d.allocate_dma(4096)
        for iova in (0,1,2**64,2**64-4096,0x100000):
            with self.assertRaises(v.VfioError):d.map_dma(a,iova,read=True,write=False)
        m=d.map_dma(a,0x4000,read=True,write=False)
        with self.assertRaises(v.VfioError):d.map_dma(c,0x4000,read=True,write=False)
        with self.assertRaises(v.VfioError):d.map_dma(a,0x8000,read=True,write=False)
        with self.assertRaises(v.VfioError):d.map_dma(c,0x8000,read=False,write=False)
        d.close(quiesced=True)

    def test_foreign_buffer_and_mapping_are_rejected(self):
        d,b=self.connected();e,c=self.connected();buf=e.allocate_dma(4096);m=e.map_dma(buf,0x4000,read=True,write=False)
        for call in [lambda:d.map_dma(buf,0x8000,read=True,write=True),lambda:d.buffer_view(buf),lambda:d.release_buffer(buf),lambda:d.begin_dma(m),lambda:d.unmap_dma(m,quiesced=True)]:
            with self.assertRaises(v.VfioError):call()
        d.close();e.close(quiesced=True)

    def test_partial_unmap_retains_memory_until_context_detached(self):
        d,b=self.connected();buf=d.allocate_dma(4096);m=d.map_dma(buf,0x4000,read=True,write=True);b.unmap_size=2048
        with self.assertRaises(v.VfioError):d.unmap_dma(m,quiesced=True)
        self.assertIn(buf.address,b.blocks)
        with self.assertRaises(v.VfioError):d.begin_dma(m)
        with self.assertRaises(v.ResourceBusy):d.release_buffer(buf)
        with self.assertRaises(v.CleanupError) as caught:d.close(quiesced=True)
        self.assertFalse(caught.exception.resources_remaining);self.assertFalse(b.blocks);self.assertFalse(b.owned)

    def test_detach_error_retains_context_memory_and_allows_retry(self):
        d,b=self.connected();buf=d.allocate_dma(4096);d.map_dma(buf,0x4000,read=True,write=True)
        b.failed.update((v.IOMMU_UNMAP_DMA,v.GROUP_UNSET_CONTAINER))
        with self.assertRaises(v.CleanupError) as caught:d.close(quiesced=True)
        self.assertTrue(caught.exception.resources_remaining);self.assertIn(buf.address,b.blocks);self.assertEqual(b.owned,{10,11})
        b.failed.clear();d.close(quiesced=True);self.assertFalse(b.blocks);self.assertFalse(b.owned)

    def test_uncertain_map_failure_retains_backing_memory(self):
        d,b=self.connected();buf=d.allocate_dma(4096);b.failed.add(v.IOMMU_MAP_DMA)
        with self.assertRaises(OSError):d.map_dma(buf,0x4000,read=True,write=False)
        other=d.allocate_dma(4096)
        with self.assertRaises(v.VfioError):d.map_dma(other,0x8000,read=True,write=False)
        with self.assertRaises(v.ResourceBusy):d.release_buffer(buf)
        with self.assertRaises(v.ResourceBusy):d.close()
        d.close(quiesced=True);self.assertFalse(b.blocks)

    def test_unknown_aperture_fails_dma_not_bar(self):
        b=FakeBackend();b.aperture=False;d,b=self.connected(backend=b);buf=d.allocate_dma(4096)
        with self.assertRaises(v.VfioError):d.map_dma(buf,0x4000,read=True,write=True)
        self.assertEqual(d.read_bar(2,0,4),bytes(4));d.close()

    def test_cyclic_capability_fails_closed_and_cleans(self):
        d,b=self.device();b.bad_cap=True
        with self.assertRaises(v.VfioError):d.connect()
        self.assertFalse(b.owned)

    def test_context_failure_preserves_primary_and_quiescence_guard(self):
        d,b=self.device()
        with self.assertRaisesRegex(ValueError,'primary') as caught:
            with d:
                buf=d.allocate_dma(4096);d.map_dma(buf,0x4000,read=True,write=False)
                raise ValueError('primary')
        self.assertTrue(any('unknown-quiescence' in note for note in caught.exception.__notes__))
        self.assertTrue(b.blocks);d.close(quiesced=True)

    def test_uapi_struct_sizes_and_uint64_ranges(self):
        self.assertEqual([x.size for x in [v.GROUP,v.DEVICE,v.REGION,v.IOMMU,v.DMA_MAP,v.DMA_UNMAP]],[8,24,32,24,32,24])
        for start,size in [(True,4096),(0,True),(-1,1),(2**64,1),(2**64-1,2)]:
            with self.assertRaises(v.VfioError):v.interval(start,size)
        self.assertEqual(v.interval(2**64-4096,4096),(2**64-4096,2**64))


if __name__=='__main__':unittest.main()
