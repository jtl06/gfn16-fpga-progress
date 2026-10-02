"""Read-only source archive closure rejects missing/extra/mutated members."""
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from fpga.reference.stream27_threefield_carry_param_replay_v1 import archive_closure
from fpga.reference.stream27_threefield_carry_param_native_v1 import sha

class CarryReplay(unittest.TestCase):
    def test_exact_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.tar.gz'
            with tarfile.open(path,'w:gz') as archive:
                m=tarfile.TarInfo('one.cpp');m.size=3;archive.addfile(m,io.BytesIO(b'abc'))
            self.assertEqual(archive_closure(path,{'one.cpp':sha(b'abc')}),1)
            for pins in ({},{'one.cpp':sha(b'bad')},{'one.cpp':sha(b'abc'),'missing':sha(b'x')}):
                with self.assertRaises(ValueError):archive_closure(path,pins)

if __name__=='__main__':unittest.main()
