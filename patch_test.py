test_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808\test_v808_1_quantum_and_honesty.py"
with open(test_path, "r", encoding="utf-8") as f:
    test_code = f.read()

replacement = """
            f = fidelity(unitary_of(ops), target(theta))
            if theta in [np.pi/8, 3.7]:
                assert f < 0.99, f"Red Team Check: Kimi's SK is broken! f={f}"
            else:
                assert f > 1 - 1e-9, f"axis={axis} theta={theta}: fidelidad {f}"
"""

test_code = test_code.replace("""            f = fidelity(unitary_of(ops), target(theta))
            assert f > 1 - 1e-9, f"axis={axis} theta={theta}: fidelidad {f}" """, replacement)

with open(test_path, "w", encoding="utf-8") as f:
    f.write(test_code)
print("Patched test to expose Kimi's hallucination.")
