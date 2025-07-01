import os
import sys

if os.name == 'nt':
    import msvcrt
else:
    import fcntl

class FileLock:
    def __init__(self, path):
        self.path = path
        self.handle = None

    def acquire(self):
        self.handle = open(self.path, "a+b")
        try:
            if os.name == 'nt':
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, IOError):
            self.handle.close()
            self.handle = None
            return False

    def release(self):
        if self.handle:
            try:
                if os.name == 'nt':
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()
                self.handle = None

    def __enter__(self):
        acquired = self.acquire()
        if not acquired:
            raise RuntimeError(f"File {self.path} is locked by another process")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
