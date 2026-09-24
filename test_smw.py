import numpy as np

def cayley_smw_exact(Y, U, V, alpha):
    D = len(Y)
    W = np.outer(U, V) - np.outer(V, U)
    beta = alpha / 2.0
    I = np.eye(D)
    # Exact matrix inversion (O(D^3))
    inv_mat = np.linalg.inv(I - beta * W)
    Z = (I + beta * W) @ Y
    Y_new = inv_mat @ Z
    return Y_new

def cayley_smw_fast(Y, U, V, alpha):
    beta = alpha / 2.0
    u_u = np.dot(U, U)
    v_v = np.dot(V, V)
    u_v = np.dot(U, V)
    u_y = np.dot(U, Y)
    v_y = np.dot(V, Y)

    v_z = v_y + beta * v_y * u_v - beta * u_y * v_v
    u_z = u_y + beta * v_y * u_u - beta * u_y * u_v

    det = 1.0 - beta**2 * u_v**2 + beta**2 * u_u * v_v
    
    invC11 = (1.0 + beta * u_v) / det
    invC12 = (-beta * v_v) / det
    invC21 = (beta * u_u) / det
    invC22 = (1.0 - beta * u_v) / det

    w1 = -beta * v_z
    w2 = -beta * u_z

    x1 = invC11 * w1 + invC12 * w2
    x2 = invC21 * w1 + invC22 * w2

    c_u = beta * v_y - x1
    c_v = x2 - beta * u_y

    Y_new = Y + c_u * U + c_v * V
    return Y_new

D = 100
Y = np.random.randn(D)
U = np.random.randn(D)
V = np.random.randn(D)
alpha = 0.1

Y1 = cayley_smw_exact(Y, U, V, alpha)
Y2 = cayley_smw_fast(Y, U, V, alpha)

print(f"Max diff: {np.max(np.abs(Y1 - Y2))}")
assert np.allclose(Y1, Y2)
print("Math is correct!")
