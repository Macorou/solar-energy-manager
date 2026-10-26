import os


class InstanceLock:
    def __init__(self,path): self.path=path; self.file=None
    def acquire(self):
        self.file=open(self.path,'a+b')
        self.file.seek(0); self.file.write(b'0'); self.file.flush(); self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close(); self.file=None
            raise RuntimeError('Only one controller may use this data directory') from None
    def close(self):
        if self.file: self.file.close(); self.file=None
