import os

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/polydim_v767_monolito.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_test = '''    # Allocate a raw buffer large enough
    total_sz = binding.lib.polydim_pmtp_sizeof(4, 10000 * 8)
    pmtp_buffer = ctypes.create_string_buffer(total_sz)
    pmtp_ctrl = ctypes.cast(pmtp_buffer, ctypes.POINTER(PMTPControl))
    binding.lib.polydim_pmtp_init(pmtp_ctrl, 4, 10000 * 8)'''

start = text.find('pmtp_ctrl = PMTPControl()')
end = text.find('binding.lib.polydim_pmtp_init(ctypes.byref(pmtp_ctrl), 4, 10000 * 8)') + len('binding.lib.polydim_pmtp_init(ctypes.byref(pmtp_ctrl), 4, 10000 * 8)')

if start != -1:
    text = text[:start] + new_test + text[end:]

text = text.replace('ctypes.byref(pmtp_ctrl)', 'pmtp_ctrl')

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/polydim_v767_monolito.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed buffer overflow')
