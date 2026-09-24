import os

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/auditoria_externa/kernel_cpp_v767.cpp', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('polydim_selftest_compensation(double* observed_err)')
# Need to include the extern "C" ... line above it
start = text.rfind('extern', 0, start)
end = text.find('polydim_cholqr2_f64(')
end = text.rfind('extern', 0, end)
extracted = text[start:end]

print('extracted length:', len(extracted))

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/kernel_cpp_v767.cpp', 'r', encoding='utf-8') as f:
    current = f.read()

insert_pos = current.find('polydim_cholqr2_f64(')
insert_pos = current.rfind('extern', 0, insert_pos)
print('insert_pos:', insert_pos)

if insert_pos != -1:
    new_current = current[:insert_pos] + extracted + current[insert_pos:]
    with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/kernel_cpp_v767.cpp', 'w', encoding='utf-8') as f:
        f.write(new_current)
    print("restored selftest functions")
else:
    print("could not find cholqr2")
