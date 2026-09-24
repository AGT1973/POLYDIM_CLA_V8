use pyo3::prelude::*;
use numpy::{PyArray1, PyArray2, IntoPyArray};

/// Representa el Handle emparejado (Strict Allocator Pairing) en Rust FFI
#[repr(C)]
pub struct PolydimHandle {
    pub data: *mut std::ffi::c_void,
    pub bytes: usize,
    pub refcount: i32,
    pub flags: u32,
    pub allocation_id: u64,
}

/// Zero-Copy Tensor Wrapper. Implementa un safe memoryview a los datos C++
#[pyclass(unsendable)]
pub struct ZeroCopyTensor {
    ptr: *mut f64,
    dim: usize,
    capacity: usize,
}

#[pymethods]
impl ZeroCopyTensor {
    #[new]
    fn new(dim: usize) -> PyResult<Self> {
        // En un caso real, esto llamaría a polydim_alloc_aligned
        let capacity = dim * std::mem::size_of::<f64>();
        let mut vec = Vec::with_capacity(dim);
        let ptr = vec.as_mut_ptr();
        std::mem::forget(vec); // Cedemos control manual
        
        Ok(ZeroCopyTensor {
            ptr,
            dim,
            capacity,
        })
    }

    /// Implementación estricta de `item_count()` solicitada en P0-05
    fn item_count(&self) -> usize {
        self.dim
    }
    
    /// Devuelve el tamaño en bytes
    fn size_bytes(&self) -> usize {
        self.capacity
    }

    /// Exposición al espacio de Python vía PyArray sin copia
    fn as_numpy<'py>(&self, py: Python<'py>) -> &'py PyArray1<f64> {
        // SAFETY: The pointer is valid and sized by `dim`.
        unsafe { PyArray1::borrow_from_array(self.ptr, self.dim, py) }
    }
}

impl Drop for ZeroCopyTensor {
    fn drop(&mut self) {
        // En un caso real, esto llamaría a polydim_free_aligned
        unsafe {
            let _ = Vec::from_raw_parts(self.ptr, 0, self.dim);
        }
    }
}

/// Módulo de Extensión PyO3 V774
#[pymodule]
fn polydim_pyo3_v774(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<ZeroCopyTensor>()?;
    Ok(())
}
