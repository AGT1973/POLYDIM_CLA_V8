import numpy as np

I2 = np.eye(2, dtype=complex)
H  = np.array([[1,1],[1,-1]], complex)/np.sqrt(2)
S  = np.diag([1, 1j]); T = np.diag([1, np.exp(1j*np.pi/4)])
TDAG = T.conj().T

# Kimi's SK sequence for residual = -pi/8 (residual < 0)
# gates.push(H); gates.push(TDAG); gates.push(H); gates.push(T)
# Remember: reversed product order.
# The array is: [H, TDAG, H, T].
# In product order, gates[0] is leftmost.
# U_SK = H @ TDAG @ H @ T
U_SK = H @ TDAG @ H @ T

U_base = H @ T @ H
U_total = U_SK @ U_base

theta = np.pi/8
target = np.cos(theta/2)*I2 - 1j*np.sin(theta/2)*np.array([[0,1],[1,0]],complex)
f = abs(np.trace(U_total @ target.conj().T)) / 2
print(f"Fidelity: {f}")
