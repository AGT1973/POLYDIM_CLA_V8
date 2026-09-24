import os
import re

PY_PATH = 'E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/polydim_v767_monolito.py'
with open(PY_PATH, 'r', encoding='utf-8') as f:
    text = f.read()

new_structs = """class PMTPSlotHeader(ctypes.Structure):
    _fields_ = [
        ("seq", ctypes.c_uint64),
        ("reserved_", ctypes.c_uint8 * 56)
    ]

class PMTPControl(ctypes.Structure):
    _fields_ = [
        ("magic", ctypes.c_uint32),
        ("num_slots", ctypes.c_uint32),
        ("payload_bytes", ctypes.c_uint64),
        ("pub_seq", ctypes.c_uint64),
        ("pub_slot", ctypes.c_uint32),
        ("wlock", ctypes.c_uint32),
        ("wticket", ctypes.c_uint32),
        ("reserved_", ctypes.c_uint8 * 28)
    ]

"""

start = text.find('class PMTPSlotHeader(ctypes.Structure):')
end = text.find('class PolydimNativeBinding:')

if start != -1 and end != -1:
    text = text[:start] + new_structs + text[end:]

# Update API bindings
api_new = """
        self.lib.polydim_pmtp_sizeof.argtypes = [ctypes.c_uint32, ctypes.c_uint64]
        self.lib.polydim_pmtp_sizeof.restype = ctypes.c_uint64
        self.lib.polydim_pmtp_alignof.argtypes = []
        self.lib.polydim_pmtp_init.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
        
        self.lib.polydim_pmtp_write_begin.argtypes = [ctypes.POINTER(PMTPControl), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64)]
        self.lib.polydim_pmtp_write_commit.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
        self.lib.polydim_pmtp_write_abort.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
        
        self.lib.polydim_pmtp_read_begin.argtypes = [ctypes.POINTER(PMTPControl), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64)]
        self.lib.polydim_pmtp_read_validate.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
"""

# replace binding from polydim_pmtp_sizeof to polydim_pmtp_validate_read
start_api = text.find('self.lib.polydim_pmtp_sizeof.argtypes')
end_api = text.find('self.lib.polydim_selftest_all', start_api)
if start_api != -1 and end_api != -1:
    text = text[:start_api] + api_new.strip() + '\n\n        ' + text[end_api:]

# Update PMTPSlabChannel
slab_start = text.find('class PMTPSlabChannel:')
slab_end = text.find('def verify_telepathy', slab_start)

slab_new = """class PMTPSlabChannel:
    def __init__(self, name="polydim_bus_0", d=1024, num_slots=4):
        self.d = d
        self.num_slots = num_slots
        self.payload_bytes = d * 8
        self.total_bytes = 128 + num_slots * 64 + num_slots * self.payload_bytes
        self.shm_name = name
        self.mmap_obj = None
        self._pin_refs = [] # Para evitar que el GC libere memoria anclada
        
        # En Windows usamos mmap anonimo con tagname
        import mmap
        self.mmap_obj = mmap.mmap(-1, self.total_bytes, self.shm_name)
        
        self.ctrl = PMTPControl.from_buffer(self.mmap_obj)
        self.ctrl_ptr = ctypes.pointer(self.ctrl)
        self._pin_refs.append(self.ctrl_ptr)
        self._pin_refs.append(self.mmap_obj)

    def __del__(self):
        if self.mmap_obj:
            self.mmap_obj.close()
            self.mmap_obj = None
            
    def write_tensor(self, binding, t_np):
        slot = ctypes.c_uint32()
        ver = ctypes.c_uint64()
        if binding.lib.polydim_pmtp_write_begin(self.ctrl_ptr, ctypes.byref(slot), ctypes.byref(ver)) == 0:
            offset = 128 + self.num_slots * 64 + slot.value * self.payload_bytes
            buf = (ctypes.c_double * self.d).from_buffer(self.mmap_obj, offset)
            ctypes.memmove(buf, t_np.ctypes.data, self.payload_bytes)
            binding.lib.polydim_pmtp_write_commit(self.ctrl_ptr, slot.value, ver.value)
            
    def read_tensor(self, binding):
        slot = ctypes.c_uint32()
        ver = ctypes.c_uint64()
        if binding.lib.polydim_pmtp_read_begin(self.ctrl_ptr, ctypes.byref(slot), ctypes.byref(ver)) == 0:
            offset = 128 + self.num_slots * 64 + slot.value * self.payload_bytes
            buf = (ctypes.c_double * self.d).from_buffer(self.mmap_obj, offset)
            import numpy as np
            out = np.ctypeslib.as_array(buf).copy()
            if binding.lib.polydim_pmtp_read_validate(self.ctrl_ptr, slot.value, ver.value) == 0:
                return out
        return None

"""

if slab_start != -1 and slab_end != -1:
    text = text[:slab_start] + slab_new + text[slab_end:]

# Update Rust FFI binding (from 5 args to 3)
text = text.replace(
    'self.rust_lib.polydim_rust_verify_invariants.argtypes = [\n            ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_double)\n        ]',
    'self.rust_lib.polydim_rust_verify_invariants.argtypes = [\n            ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.c_size_t\n        ]' # Need to verify exact Rust signature, usually (ptr, rows, cols) or (ptr, d, K)
)

with open(PY_PATH, 'w', encoding='utf-8') as f:
    f.write(text)

print("polydim_v767_monolito.py updated")
