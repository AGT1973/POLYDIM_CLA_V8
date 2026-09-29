"""High-D CPU reference measurements, valid finite arrays and analytic oracle."""
import sys,pathlib,time,ctypes as C,json,platform
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'python'))
import numpy as np
from polydim import Kernel
k=Kernel();results=[]
for d in (10000,1000000,10000000):
    y=np.full(d,1/np.sqrt(float(d)));u=np.zeros(d);v=np.zeros(d);u[0]=1;v[1]=1;out=np.empty(d)
    start=time.perf_counter()
    k._call('pd_rotate',k.ptr(y),k.ptr(u),k.ptr(v),d,.7,k.ptr(out),d)
    elapsed=time.perf_counter()-start
    # Long-double accumulation is an independent higher precision norm oracle on this host.
    norm2=np.sum(out.astype(np.longdouble)**2,dtype=np.longdouble)
    expected=y.copy();expected[0]=y[0]*(np.cos(.7)-np.sin(.7));expected[1]=y[0]*(np.sin(.7)+np.cos(.7))
    error=float(np.max(np.abs(out-expected)));drift=float(abs(norm2-1))
    assert error<1e-14 and drift<1e-12
    results.append(dict(D=d,seconds=elapsed,norm_squared_error=drift,max_coordinate_error=error))
    del y,u,v,out,expected
print(json.dumps({'platform':platform.platform(),'numpy':np.__version__,'measurements':results,'scope':'new V807 CPU Rodrigues; dense y, sparse orthonormal basis; not universal bound'},indent=2))
