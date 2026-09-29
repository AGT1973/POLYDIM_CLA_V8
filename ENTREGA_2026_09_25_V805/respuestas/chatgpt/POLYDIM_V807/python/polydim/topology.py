"""Optional Rust adapter; explicit layout handshake before any data operation."""
import ctypes as C
import numpy as np
from .native import host_array, NativeError
class Edge(C.Structure):_fields_=[('u',C.c_uint32),('v',C.c_uint32)]
class Graph(C.Structure):_fields_=[('vertices',C.c_uint32),('components',C.c_uint32),('edges',C.c_uint64),('cycles',C.c_int64)]
class Cluster(C.Structure):_fields_=[('candidates',C.c_uint32),('dimension',C.c_uint32),('component_size',C.c_uint32),('medoid_index',C.c_uint32),('components',C.c_uint32),('reserved',C.c_uint32),('cycles',C.c_int64),('mean_distance',C.c_double)]
class Topology:
    def __init__(self,path):
        self.lib=C.CDLL(str(path));l=self.lib;l.pd_rust_abi_version.argtypes=[];l.pd_rust_abi_version.restype=C.c_uint32
        if l.pd_rust_abi_version()!=807:raise RuntimeError('Rust ABI mismatch')
        for name,typ in [('graph',Graph),('cluster',Cluster)]:
            for prop,expected in [('size',C.sizeof(typ)),('alignment',C.alignment(typ))]:
                f=getattr(l,f'pd_{name}_{prop}');f.argtypes=[];f.restype=C.c_size_t
                if f()!=expected:raise RuntimeError('Rust layout mismatch')
        l.pd_graph.argtypes=[C.POINTER(Edge),C.c_size_t,C.c_uint32,C.POINTER(Graph)];l.pd_graph.restype=C.c_int32
        l.pd_cluster.argtypes=[C.POINTER(C.c_double),C.c_size_t,C.c_uint32,C.c_uint32,C.c_double,C.POINTER(C.c_double),C.c_size_t,C.POINTER(Cluster)];l.pd_cluster.restype=C.c_int32
    def graph(self,edges,vertices):
        if type(vertices)is not int or not 1<=vertices<=10000000:raise ValueError('vertex budget')
        pairs=list(edges)
        for u,v in pairs:
            if not isinstance(u,(int,np.integer)) or not isinstance(v,(int,np.integer)) or not (0<=u<vertices and 0<=v<vertices):raise ValueError('invalid edge')
        e=(Edge*len(pairs))(*(Edge(u,v) for u,v in pairs));r=Graph()
        code=self.lib.pd_graph(e,len(e),vertices,C.byref(r))
        if code:raise NativeError('graph',code)
        return {name:getattr(r,name) for name,_ in Graph._fields_}
    def cluster(self,candidates,threshold):
        a=host_array(candidates,ndim=2);n,d=a.shape
        if n>10000 or d>10000000 or n*n*d>2000000000:raise ValueError('work budget')
        out=np.empty(d);r=Cluster()
        code=self.lib.pd_cluster(a.ctypes.data_as(C.POINTER(C.c_double)),a.size,n,d,threshold,out.ctypes.data_as(C.POINTER(C.c_double)),out.size,C.byref(r))
        if code:raise NativeError('cluster',code)
        return out,{name:getattr(r,name) for name,_ in Cluster._fields_}
