import numpy as np

I2 = np.eye(2, dtype=complex)
H  = np.array([[1,1],[1,-1]], complex)/np.sqrt(2)
S  = np.diag([1, 1j]); T = np.diag([1, np.exp(1j*np.pi/4)])

# Angle pi/8
theta = np.pi/8
target = np.cos(theta/2)*I2 - 1j*np.sin(theta/2)*np.array([[0,1],[1,0]],complex)

# Kimi gives U = H @ T @ H  (for theta = pi/8, k=1)
U = H @ T @ H

# Fidelity
f = abs(np.trace(U @ target.conj().T)) / 2
print(f"Fidelity: {f}")
