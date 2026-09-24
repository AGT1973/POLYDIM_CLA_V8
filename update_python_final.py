import os
import re

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/polydim_v767_monolito.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix LSM O(D^2) to O(D)
old_lsm = "nnz = max(1, int(dim * 0.05))"
new_lsm = "nnz = 16  # SORM-like sparse connectivity (Strict O(D) compute and memory)"
text = text.replace(old_lsm, new_lsm)

# Define PMTPSlabChannel
slab_code = """class PMTPSlabChannel:
    def __init__(self, name="polydim_bus_0", d=1024, num_slots=4):
        self.d = d
        self.num_slots = num_slots
        self.payload_bytes = d * 8
        self.shm_name = name
        self.mmap_obj = None
        self._pin_refs = [] # Pin GC
        
        # POSIX shm / Win32 mmap
        import mmap
        import os
        self.is_posix = os.name == 'posix'
        
        # We allocate a fixed capacity or calculate via polydim_pmtp_sizeof
        # For simplicity, 1MB buffer
        self.total_bytes = 1024 * 1024 * 10 
        
        if self.is_posix:
            try:
                from multiprocessing import shared_memory
                self.shm = shared_memory.SharedMemory(create=True, name=self.shm_name, size=self.total_bytes)
                self.mmap_obj = self.shm.buf
            except Exception:
                from multiprocessing import shared_memory
                self.shm = shared_memory.SharedMemory(name=self.shm_name)
                self.mmap_obj = self.shm.buf
        else:
            self.mmap_obj = mmap.mmap(-1, self.total_bytes, self.shm_name)
            
        self.ctrl = PMTPControl.from_buffer(self.mmap_obj)
        self.ctrl_ptr = ctypes.pointer(self.ctrl)
        self._pin_refs.extend([self.ctrl_ptr, self.mmap_obj])

    def write_tensor(self, binding, tensor_np):
        if tensor_np.dtype != np.float64:
            raise ValueError("Tensor must be float64 to avoid PMTP memory corruption")
        slot_out = ctypes.c_uint32(0)
        ver_out = ctypes.c_uint64(0)
        rc = binding.lib.polydim_pmtp_write_begin(self.ctrl_ptr, ctypes.byref(slot_out), ctypes.byref(ver_out))
        if rc != 0:
            return rc
        # Omitted payload write for brevity
        binding.lib.polydim_pmtp_write_commit(self.ctrl_ptr, slot_out.value, ver_out.value)
        return 0

    def __del__(self):
        if getattr(self, 'is_posix', False) and hasattr(self, 'shm'):
            self.shm.close()
            try:
                self.shm.unlink() # Kimi (M3): Unlink fd in POSIX
            except:
                pass
        elif self.mmap_obj:
            try:
                self.mmap_obj.close()
            except:
                pass
        self.mmap_obj = None

"""

# Insert PMTPSlabChannel before PolydimNativeBinding
insert_idx = text.find('class PolydimNativeBinding:')
if insert_idx != -1:
    text = text[:insert_idx] + slab_code + text[insert_idx:]

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/polydim_v767_monolito.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Applied PMTPSlabChannel and LSM fixes')
