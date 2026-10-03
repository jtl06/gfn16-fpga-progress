# SPDX-License-Identifier: Apache-2.0
"""Default-OFF private checkpoint file/verified-window controller.

Same-directory replace follows fsync of a mode0600 temporary file, then fsync
of the directory. This is a software POSIX recovery contract, not a guarantee
for arbitrary filesystems/power failures or the genefer .ctx format. The digest
detects accidental corruption; it does not authenticate a hostile host.
"""
import os
from pathlib import Path
import tempfile

from .r15_arithmetic import Checkpoint, need, run_verified_window


class CheckpointStore:
    def __init__(self, directory, *, source, owner, context, enabled=False):
        need(enabled is True, 'CHECKPOINT_STORE_OFF')
        requested = Path(directory)
        need(requested.is_absolute() and requested.is_dir() and
             not requested.is_symlink(), 'CHECKPOINT_PRIVATE_DIRECTORY')
        self.directory = requested.resolve()
        self.path = self.directory / 'checkpoint.r15'
        self.identity = dict(expected_source=source, expected_owner=owner,
                             expected_context=context)

    def _decode(self, raw):
        return Checkpoint.decode(raw, **self.identity)

    def load(self):
        # No link following and bound before reading, even for corrupted input.
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            need(os.fstat(stream.fileno()).st_size <= 4 * 1024 * 1024,
                 'CHECKPOINT_FILE_BOUND')
            raw = stream.read(4 * 1024 * 1024 + 1)
        return self._decode(raw)

    def commit(self, checkpoint):
        need(type(checkpoint) is Checkpoint, 'CHECKPOINT_TYPED_COMMIT')
        raw = checkpoint.encode()
        need(self._decode(raw) == checkpoint, 'CHECKPOINT_VALIDATE_BEFORE_WRITE')
        if self.path.exists() or self.path.is_symlink():
            old = self.load()
            need((old.base, old.n) == (checkpoint.base, checkpoint.n) and
                 checkpoint.completed >= old.completed, 'CHECKPOINT_MONOTONIC_PROFILE')
            need(checkpoint.completed > old.completed or checkpoint == old,
                 'CHECKPOINT_SAME_POSITION_IDENTICAL')
        fd, temporary = tempfile.mkstemp(prefix='.checkpoint-r15-', dir=self.directory)
        temporary = Path(temporary)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # This is the only publication edge; a pre-replace failure keeps
            # the prior verified file intact. Never overwrite in-place.
            os.replace(temporary, self.path)
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary.exists():
                temporary.unlink()
        return checkpoint


class VerifiedSession:
    """Restores descriptor position as well as residue after a failed window."""
    def __init__(self, backend, store, *, enabled=False):
        need(enabled is True and type(store) is CheckpointStore, 'VERIFIED_SESSION_OFF')
        self.backend, self.store = backend, store
        self.verified = store.load()
        need((self.verified.base, self.verified.n) == (backend.base, backend.n),
             'SESSION_CHECKPOINT_PROFILE')
        self._restore()

    def _restore(self):
        self.backend.load(self.verified.value)
        self.backend.steps = self.verified.completed

    def window(self, bits, width, *, inject=None):
        try:
            fresh = run_verified_window(self.backend, bits, width, self.verified,
                                        enabled=True, inject=inject)
        except BaseException:
            self._restore()
            raise
        if fresh is None:
            self._restore()
            return False
        try:
            self.store.commit(fresh)
        except BaseException:
            # A replace may have succeeded before a directory-fsync exception.
            # Re-read the sole file: either complete verified checkpoint is safe.
            self.verified = self.store.load()
            self._restore()
            raise
        self.verified = fresh
        self._restore()
        return True
