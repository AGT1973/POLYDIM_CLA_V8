"""Functional and numerical regressions; no invalid pointers or corruption probes."""
import sys, pathlib, unittest, multiprocessing as mp
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'python'))
import numpy as np
import ctypes as C
from polydim import Kernel, NativeError, SharedTensor
from polydim.device import select_backend

def child_publish(bus):
    with bus.write() as a:a[:]=np.arange(a.size).reshape(a.shape)
    del a
    bus.close()

def child_timed_read(bus,connection):
    try:
        with bus.read() as a:value=float(a.flat[0])
        del a
        connection.send(('ok',value))
    except TimeoutError:connection.send(('timeout',None))
    finally:bus.close();connection.close()

class Regression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.k=Kernel();cls.rng=np.random.default_rng(807)
    def test_qr_orthogonality_and_span(self):
        a=self.rng.normal(size=(500,8));q=self.k.qr(a)
        self.assertLess(np.linalg.norm(q.T@q-np.eye(8)),1e-12)
        self.assertLess(np.linalg.norm(a-q@(q.T@a))/np.linalg.norm(a),1e-12)
    def test_rank_rejected(self):
        for a in (np.zeros((100,2)),np.ones((100,2))):
            with self.assertRaises(NativeError) as e:self.k.qr(a)
            self.assertEqual(e.exception.code,4)
    def test_scaled_qr(self):
        a=self.rng.normal(size=(100,4))
        for scale in (1e-250,1e250):
            q=self.k.qr(a*scale);self.assertLess(np.linalg.norm(q.T@q-np.eye(4)),1e-12)
    def test_fp32_precision_contract(self):
        f=self.k.lib.pd_qr_f32;p=C.POINTER(C.c_float)
        f.argtypes=[p,C.c_size_t,C.c_size_t,C.c_size_t,p,C.c_size_t];f.restype=C.c_int32
        a=np.ones((10000,1),dtype=np.float32);out=np.empty_like(a)
        self.assertEqual(f(a.ctypes.data_as(p),10000,1,a.size,out.ctypes.data_as(p),out.size),0)
        self.assertLess(abs(np.sum(out.astype(np.float64)**2)-1),2e-7)
        a.fill(0);self.assertEqual(f(a.ctypes.data_as(p),10000,1,a.size,out.ctypes.data_as(p),out.size),4)
    def test_dense_basis_rotation(self):
        q=self.k.qr(self.rng.normal(size=(10000,3)))
        y=.6*q[:,0]+.8*q[:,2];z=self.k.rotate(y,q[:,0],q[:,1],.2)
        expected=.6*np.cos(.2)*q[:,0]+.6*np.sin(.2)*q[:,1]+.8*q[:,2]
        self.assertLess(np.linalg.norm(z-expected),1e-13)
    def test_gram(self):
        a=self.rng.normal(size=(300,5));np.testing.assert_allclose(self.k.gram(a),a.T@a,rtol=1e-13,atol=1e-12)
    def test_normalize_large_dynamic_range(self):
        for a in ([1e308,1e308],[1e-300,1e-300]):self.assertAlmostEqual(np.linalg.norm(self.k.normalize(a)),1.,places=14)
    def test_rotation_analytic_and_inverse(self):
        d=10000;u=np.zeros(d);v=u.copy();u[0]=1;v[1]=1;y=.6*u+.8*v
        for theta in (0.,1e-12,.7,np.pi):
            z=self.k.rotate(y,u,v,theta)
            expected=(.6*np.cos(theta)-.8*np.sin(theta))*u+(.6*np.sin(theta)+.8*np.cos(theta))*v
            np.testing.assert_allclose(z,expected,atol=1e-14,rtol=1e-14)
            np.testing.assert_allclose(self.k.rotate(z,u,v,-theta),y,atol=1e-14,rtol=1e-14)
    def test_rotation_rejects_bad_basis(self):
        with self.assertRaises(NativeError):self.k.rotate([1,0],[1,0],[1,0],.1)
    def test_optimizer_vertical_motion(self):
        a=np.eye(2);theta=.3;t=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
        q,r=self.k.optimize(t,a,tolerance=1e-9)
        self.assertTrue(r['converged']);self.assertLess(np.linalg.norm(q-t),1e-8)
        self.assertAlmostEqual(r['objective'],.5*np.linalg.norm(q-t)**2,places=13)
    def test_optimizer_metrics_and_descent(self):
        a=self.k.qr(self.rng.normal(size=(200,4)));t=self.rng.normal(size=a.shape)
        q,r=self.k.optimize(t,a,max_iterations=20)
        self.assertLess(r['objective'],.5*np.linalg.norm(a-t)**2)
        g=q-t;g-=q@((q.T@g+g.T@q)/2)
        self.assertAlmostEqual(r['gradient_norm'],np.linalg.norm(g),places=11)
        self.assertLess(r['orthogonality'],1e-12)
    def test_optimizer_rejects_zero_initial(self):
        with self.assertRaises(NativeError):self.k.optimize(np.zeros((10,2)),np.zeros((10,2)))
    def test_lsm_contract(self):
        d=16;s=np.ones(d)/4;p=np.arange(d);v=np.ones(d)
        np.testing.assert_array_equal(self.k.lsm(s,v,p,leak=0,input_scale=0),s)
        with self.assertRaises(NativeError):self.k.lsm(s,v,np.zeros(d,dtype=int))
    def test_invalid_python_data(self):
        with self.assertRaises(ValueError):self.k.normalize([np.nan,1])
        with self.assertRaises(ValueError):self.k.rotate([1,0],[1],[0,1],.1)
        with self.assertRaises(NotImplementedError):select_backend('cuda')
    def test_shared_publication_spawn(self):
        ctx=mp.get_context('spawn');bus=SharedTensor.create((100,),context=ctx)
        p=ctx.Process(target=child_publish,args=(bus,));p.start();p.join(10)
        try:
            self.assertFalse(p.is_alive());self.assertEqual(p.exitcode,0)
            with bus.read() as a:np.testing.assert_array_equal(a,np.arange(100))
            del a
            with self.assertRaises(ValueError):
                with bus.write() as a:a[0]=123  # remaining entries deliberately unwritten
            del a
            with bus.read() as a:np.testing.assert_array_equal(a,np.arange(100))
            del a
        finally:
            if p.is_alive():p.terminate();p.join(5)
            bus.unlink();bus.close()
    def test_shared_timeout_preserves_active_bank(self):
        ctx=mp.get_context('spawn');bus=SharedTensor.create((8,),context=ctx,timeout=.2)
        parent,child=ctx.Pipe(False)
        with bus.write() as a:
            a[:]=2
        del a
        # Hold the shared lock directly only to verify bounded waiting in a child.
        bus.lock.acquire()
        try:
            p=ctx.Process(target=child_timed_read,args=(bus,child));p.start();child.close()
            self.assertTrue(parent.poll(10));self.assertEqual(parent.recv()[0],'timeout')
            p.join(10);self.assertEqual(p.exitcode,0)
        finally:
            bus.lock.release();parent.close()
            if p.is_alive():p.terminate();p.join(5)
            bus.unlink();bus.close()

if __name__=='__main__':unittest.main(verbosity=2)
