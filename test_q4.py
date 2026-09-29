import numpy as np

I2 = np.eye(2, dtype=complex)
H  = np.array([[1,1],[1,-1]], complex)/np.sqrt(2)
S  = np.diag([1, 1j]); T = np.diag([1, np.exp(1j*np.pi/4)])
TDAG = T.conj().T
MAT = {1:H, 2:S, 3:T, 4:TDAG}
opcodes = [1, 3, 1, 4, 1, 3, 1, 4, 1, 3, 1]

U = I2.copy()
for op in reversed(opcodes):
    U = MAT[op] @ U

theta = np.pi/8
target = np.cos(theta/2)*I2 - 1j*np.sin(theta/2)*np.array([[0,1],[1,0]],complex)
f = abs(np.trace(U @ target.conj().T)) / 2
print(f"Fidelity: {f}")
