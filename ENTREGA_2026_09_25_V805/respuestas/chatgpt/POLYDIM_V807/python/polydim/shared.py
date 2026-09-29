"""Cooperating spawn-process shared tensor, conservative double-bank protocol.

No lock-free claim. One process-shared lock protects bank publication and each
read lease. Writing modifies only the inactive bank and commits on normal exit.
Crash while holding the lock requires whole-bus retirement, never forced reclaim.
This is trusted-process IPC: views must not escape their context; ACLs and hostile
process isolation are out of scope. No tensor serialization on publish/read.
"""
from contextlib import contextmanager
from multiprocessing import shared_memory
import multiprocessing as mp
import struct
import math
import os
import numpy as np

_HEADER=128
_MAGIC=b'PD807SHM'
class SharedTensor:
    @classmethod
    def create(cls, shape, *, context=None, timeout=5., max_bytes=512*1024*1024, space_id='unspecified'):
        shape=tuple(shape)
        if not shape or any(type(n) is not int or n<=0 for n in shape):raise ValueError('shape must be positive integers')
        size=math.prod(shape)*8
        if size>max_bytes or size>(2**63-_HEADER)//2:raise ValueError('memory budget exceeded')
        if not math.isfinite(timeout) or timeout<=0:raise ValueError('finite positive timeout required')
        ctx=context or mp.get_context('spawn')
        lock=ctx.Lock()
        shm=shared_memory.SharedMemory(create=True,size=_HEADER+2*size)
        try:
            shm.buf[:_HEADER]=bytes(_HEADER)
            shm.buf[:8]=_MAGIC
            for bank in range(2):np.ndarray(shape,dtype=np.float64,buffer=shm.buf,offset=_HEADER+bank*size).fill(0)
            return cls(shm.name,shape,lock,timeout,space_id,shm=shm,owner_pid=os.getpid())
        except BaseException:
            shm.close();shm.unlink();raise
    def __init__(self,name,shape,lock,timeout,space_id,*,shm=None,owner_pid=None):
        self.name=name;self.shape=tuple(shape);self.lock=lock;self.timeout=timeout
        self.space_id=space_id;self._bytes=math.prod(self.shape)*8
        self._shm=shm;self._owner_pid=owner_pid;self._active=False;self._closed=False
    def __getstate__(self):
        if self._active or self._closed:raise RuntimeError('cannot transfer active/closed bus')
        state=self.__dict__.copy();state['_shm']=None;state['_owner_pid']=None
        return state
    def _mapping(self):
        if self._closed:raise RuntimeError('bus closed')
        if self._shm is None:self._shm=shared_memory.SharedMemory(name=self.name)
        if self._shm.size!=_HEADER+2*self._bytes or bytes(self._shm.buf[:8])!=_MAGIC:raise RuntimeError('mapping contract mismatch')
        return self._shm
    @contextmanager
    def _lease(self,write):
        if self._active:raise RuntimeError('nested lease on same object')
        if not self.lock.acquire(timeout=self.timeout):raise TimeoutError('bus unavailable; do not force reclamation')
        view=None
        try:
            shm=self._mapping();self._active=True
            bank,seq=struct.unpack_from('<QQ',shm.buf,8)
            if bank>1:raise RuntimeError('invalid bank')
            if write and seq==2**64-1:raise OverflowError('generation exhausted: retire bus')
            chosen=1-bank if write else bank
            view=np.ndarray(self.shape,dtype=np.float64,buffer=shm.buf,offset=_HEADER+chosen*self._bytes)
            view.flags.writeable=write
            if write:view.fill(np.nan)  # incomplete writes cannot publish stale values
            yield view
            if write:
                if not np.isfinite(view).all():raise ValueError('nonfinite tensor: not published')
                struct.pack_into('<QQ',shm.buf,8,chosen,seq+1)
        finally:
            if view is not None:view.flags.writeable=False
            self._active=False
            self.lock.release()
    def read(self):return self._lease(False)
    def write(self):
        """Caller must overwrite the complete inactive tensor before commit."""
        return self._lease(True)
    def close(self):
        if self._active:raise RuntimeError('cannot close during lease')
        if self._shm is not None:self._shm.close();self._shm=None
        self._closed=True
    def unlink(self):
        """Owner only, after all children have joined and all views are discarded."""
        if os.getpid()!=self._owner_pid:raise RuntimeError('only creator may unlink')
        if self._active:raise RuntimeError('cannot unlink during lease')
        s=self._shm or shared_memory.SharedMemory(name=self.name)
        try:s.unlink()
        finally:
            if s is not self._shm:s.close()
