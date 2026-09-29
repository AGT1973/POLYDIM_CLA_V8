"""Checked CPU adapter for ABI 807. Explicit copies preserve ownership.

Public methods own their outputs. No external GPU pointer reaches CPU native code.
The low-level C API still requires valid, live caller-owned memory.
"""
from __future__ import annotations
import ctypes as C
from pathlib import Path
import sys
import numpy as np

class NativeError(RuntimeError):
    def __init__(self, operation, code):
        self.code = code
        super().__init__(f'{operation}: native status {code}')

class Result(C.Structure):
    _fields_ = [('iterations', C.c_uint64), ('objective', C.c_double),
                ('gradient_norm', C.c_double), ('orthogonality', C.c_double),
                ('converged', C.c_int32), ('status', C.c_int32)]

def host_array(value, *, ndim=None):
    """Return an owned C-order float64 host array. Device transfer is intentional."""
    if type(value).__module__.startswith('torch'):
        value = value.detach().to(device='cpu', dtype=__import__('torch').float64).contiguous().numpy()
    a = np.array(value, dtype=np.float64, order='C', copy=True)
    if ndim is not None and a.ndim != ndim:
        raise ValueError(f'expected {ndim} dimensions, got {a.ndim}')
    if not a.size or not np.isfinite(a).all():
        raise ValueError('empty or nonfinite input')
    return a

class Kernel:
    def __init__(self, path=None):
        root = Path(__file__).resolve().parents[2]
        name = 'polydim807.dll' if sys.platform=='win32' else ('libpolydim807.dylib' if sys.platform=='darwin' else 'libpolydim807.so')
        path = Path(path) if path else root/'build'/name
        self.lib = C.CDLL(str(path.resolve()))
        L=self.lib; size=C.c_size_t; p=C.POINTER(C.c_double); i=C.c_int32
        for name, restype in [('pd_abi_version', C.c_uint32),('pd_result_size',size),('pd_result_alignment',size)]:
            fn=getattr(L,name);fn.argtypes=[];fn.restype=restype
        if L.pd_abi_version()!=807 or L.pd_result_size()!=C.sizeof(Result) or L.pd_result_alignment()!=C.alignment(Result):
            raise RuntimeError('ABI mismatch: refusing native calls')
        signatures={
            'pd_gram':[p,size,size,size,p,size], 'pd_qr':[p,size,size,size,p,size],
            'pd_normalize':[p,size,p,size], 'pd_rotate':[p,p,p,size,C.c_double,p,size],
            'pd_optimize':[p,p,size,size,size,C.c_uint64,C.c_double,C.c_double,p,size,C.POINTER(Result)],
            'pd_lsm':[p,p,C.POINTER(C.c_int8),C.POINTER(C.c_uint32),size,C.c_double,C.c_double,p,size],
        }
        for name,args in signatures.items():
            fn=getattr(L,name);fn.argtypes=args;fn.restype=i
    @staticmethod
    def ptr(a): return a.ctypes.data_as(C.POINTER(C.c_double))
    def _call(self,name,*args):
        code=getattr(self.lib,name)(*args)
        if code: raise NativeError(name,code)
    def qr(self,value):
        a=host_array(value,ndim=2);d,k=a.shape;out=np.empty_like(a)
        self._call('pd_qr',self.ptr(a),d,k,a.size,self.ptr(out),out.size)
        return out
    def gram(self,value):
        a=host_array(value,ndim=2);d,k=a.shape;out=np.empty((k,k))
        self._call('pd_gram',self.ptr(a),d,k,a.size,self.ptr(out),out.size)
        return out
    def normalize(self,value):
        a=host_array(value,ndim=1);out=np.empty_like(a)
        self._call('pd_normalize',self.ptr(a),a.size,self.ptr(out),out.size)
        return out
    def rotate(self,y,u,v,theta):
        y,u,v=[host_array(a,ndim=1) for a in (y,u,v)]
        if y.shape!=u.shape or y.shape!=v.shape: raise ValueError('shape mismatch')
        out=np.empty_like(y)
        self._call('pd_rotate',self.ptr(y),self.ptr(u),self.ptr(v),y.size,theta,self.ptr(out),out.size)
        return out
    def optimize(self,target,initial,*,max_iterations=500,learning_rate=1.,tolerance=1e-8):
        a=host_array(initial,ndim=2);t=host_array(target,ndim=2)
        if a.shape!=t.shape: raise ValueError('shape mismatch')
        if not isinstance(max_iterations,int) or not 1<=max_iterations<=1000000: raise ValueError('iteration budget')
        out=np.empty_like(a);r=Result();d,k=a.shape
        self._call('pd_optimize',self.ptr(t),self.ptr(a),d,k,a.size,max_iterations,learning_rate,tolerance,self.ptr(out),out.size,C.byref(r))
        return out, {name:getattr(r,name) for name,_ in Result._fields_}
    def lsm(self,state,signs,permutation,*,input=None,leak=.8,input_scale=1.):
        s=host_array(state,ndim=1);p=np.asarray(permutation);v=np.asarray(signs)
        if p.shape!=s.shape or v.shape!=s.shape or not np.issubdtype(p.dtype,np.integer):raise ValueError('invalid permutation/signs')
        if np.any(p<0) or np.any(p>=s.size) or not np.all((v==1)|(v==-1)):raise ValueError('invalid permutation/signs')
        p=np.array(p,dtype=np.uint32,order='C',copy=True);v=np.array(v,dtype=np.int8,order='C',copy=True)
        a=None if input is None else host_array(input,ndim=1)
        if a is not None and a.shape!=s.shape:raise ValueError('input shape')
        out=np.empty_like(s)
        self._call('pd_lsm',self.ptr(s),None if a is None else self.ptr(a),v.ctypes.data_as(C.POINTER(C.c_int8)),p.ctypes.data_as(C.POINTER(C.c_uint32)),s.size,leak,input_scale,self.ptr(out),out.size)
        return out
