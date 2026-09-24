import os

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/polydim_v767_monolito.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    'self.lib.polydim_selftest_all.argtypes = []',
    'self.lib.polydim_selftest_all.argtypes = []\n        self.lib.polydim_check_ftz.argtypes = []\n        self.lib.polydim_check_ftz.restype = ctypes.c_int32'
)

text = text.replace(
    'assert rc_sub == 0, "Subnormal handling error"',
    'assert rc_sub == 0, "Subnormal handling error"\n    ftz = binding.lib.polydim_check_ftz()\n    assert ftz == 0, "FTZ/DAZ is enabled in hardware! Denormals will be lost!"'
)

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/polydim_v767_monolito.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Updated Python monolith with check_ftz')
