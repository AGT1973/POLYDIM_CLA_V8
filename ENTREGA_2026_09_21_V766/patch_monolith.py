import sys, re

with open('polydim_v764_monolito.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_pmtp_class = re.search(r'class PMTPSlabChannel:.*?def close\(self\):.*?try:.*?self\.mmap_obj\.close\(\)', text, re.DOTALL).group(0)

new_pmtp_class = '''class PMTPSlabChannel:
    def __init__(self, tag: str, dimension: int, cpp_dll_path: str, create: bool = True):
        self.tag = tag
        self.D = dimension
        self.tensor_bytes = dimension * 8
        self.total_bytes = 64 + 3 * self.tensor_bytes
        self.shm_name = f"polydim_pmtp_{tag}"
        self.create = create
        
        if sys.platform == "win32":
            self.mmap_obj = mmap.mmap(-1, self.total_bytes, tagname=self.shm_name, access=mmap.ACCESS_WRITE)
        else:
            import posix_ipc
            flags = posix_ipc.O_CREAT if create else 0
            self.posix_shm = posix_ipc.SharedMemory(f"/{self.shm_name}", flags, size=self.total_bytes)
            self.mmap_obj = mmap.mmap(self.posix_shm.fd, self.total_bytes)

        # FFI Bridge to avoid TSO/Weak-Ordering data races on ARM/Apple Silicon
        self.lib = ctypes.CDLL(cpp_dll_path)
        self.lib.polydim_pmtp_init.argtypes = [ctypes.c_void_p]
        self.lib.polydim_pmtp_init.restype = None
        self.lib.polydim_pmtp_begin_write.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
        self.lib.polydim_pmtp_begin_write.restype = ctypes.c_int32
        self.lib.polydim_pmtp_commit_write.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        self.lib.polydim_pmtp_commit_write.restype = ctypes.c_int32
        self.lib.polydim_pmtp_acquire_read.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)]
        self.lib.polydim_pmtp_acquire_read.restype = ctypes.c_int32

        # Obtenemos puntero void al mmap
        buffer_type = ctypes.c_uint8 * self.total_bytes
        self.mmap_ptr = ctypes.addressof(buffer_type.from_buffer(self.mmap_obj))

        if create:
            self.lib.polydim_pmtp_init(self.mmap_ptr)

    def write_tensor(self, tensor_f64: np.ndarray) -> int:
        assert tensor_f64.dtype == np.float64 and tensor_f64.size == self.D
        
        # 1. Acquire slot (memory_order_acquire barrier inside C++)
        slot = ctypes.c_uint64(0)
        self.lib.polydim_pmtp_begin_write(self.mmap_ptr, ctypes.byref(slot))
        s = slot.value
        
        # 2. Direct copy to the reserved slot
        offset = 64 + s * self.tensor_bytes
        dest_view = np.frombuffer(self.mmap_obj, dtype=np.float64, count=self.D, offset=offset)
        np.copyto(dest_view, tensor_f64)
        del dest_view
        
        # 3. Commit (memory_order_release barrier inside C++)
        self.lib.polydim_pmtp_commit_write(self.mmap_ptr, s)
        return s

    def read_tensor(self) -> Optional[np.ndarray]:
        observed_seq = ctypes.c_uint64(0)
        slot_out = ctypes.c_uint64(0)
        ticket_out = ctypes.c_uint64(0)
        
        # memory_order_acquire inside C++
        has_new = self.lib.polydim_pmtp_acquire_read(self.mmap_ptr, ctypes.byref(observed_seq), ctypes.byref(slot_out), ctypes.byref(ticket_out))
        if has_new == 0:
            return None
            
        s = slot_out.value
        offset = 64 + s * self.tensor_bytes
        src_view = np.frombuffer(self.mmap_obj, dtype=np.float64, count=self.D, offset=offset)
        tensor_copy = np.copy(src_view)
        del src_view
        return tensor_copy

    def close(self):
        gc.collect()
        if hasattr(self, 'mmap_obj') and self.mmap_obj:
            try:
                self.mmap_obj.close()'''

text = text.replace(old_pmtp_class, new_pmtp_class)

text = text.replace(
    'self.pmtp = PMTPSlabChannel(tag="A_to_B", dimension=D, create=True)',
    'self.pmtp = PMTPSlabChannel(tag="A_to_B", dimension=D, cpp_dll_path=cpp_dll_path, create=True)'
)

with open('polydim_v764_monolito.py', 'w', encoding='utf-8') as f:
    f.write(text)
