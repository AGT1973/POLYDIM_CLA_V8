import os
import re

cpp_file = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_19_V764\src\polydim_kernel.cpp"
with open(cpp_file, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Remover el Parche B viejo
old_patch_b = r'''    /\* B. Retracción Tangente en Cayley-SMW: Z_2 <- Z_2 - 0.5 \* X\^T G Z_1 \*/.*?/\* Y = X \+ tau \* U Z,  U = \[G X\].'''
c = re.sub(old_patch_b, r'    /* Y = X + tau * U Z,  U = [G X].', c, flags=re.DOTALL)

# 2. Insertar Gram projection justo despues de auto GtG = ...
gram_anchor = r'auto GtG = \[\&\]\(uint32_t r, uint32_t c\) \{ return S\[static_cast<size_t>\(K \+ r\) \* K2 \+ \(K \+ c\)\]; \};'

gram_patch = '''
    /* PROYECCION AL ESPACIO TANGENTE ANTES DEL SOLVER SMW */
    std::vector<double> S_sym(K * K), S_skew(K * K);
    for (uint32_t r = 0; r < K; ++r) {
        for (uint32_t c = 0; c < K; ++c) {
            double xtg = XtG(r, c);
            double gtx = S[static_cast<size_t>(K + r) * K2 + c];
            S_sym[r * K + c] = 0.5 * (xtg + gtx);
            S_skew[r * K + c] = 0.5 * (xtg - gtx);
        }
    }
    std::vector<double> GtG_new(K * K, 0.0);
    for (uint32_t r = 0; r < K; ++r) {
        for (uint32_t c = 0; c < K; ++c) {
            double gtg = GtG(r, c);
            double t1 = 0.0, t2 = 0.0, t3 = 0.0;
            for (uint32_t q = 0; q < K; ++q) {
                t1 += S[static_cast<size_t>(K + r) * K2 + q] * S_sym[q * K + c];
                t2 += S_sym[r * K + q] * XtG(q, c);
                t3 += S_sym[r * K + q] * S_sym[q * K + c];
            }
            GtG_new[r * K + c] = gtg - t1 - t2 + t3;
        }
    }
    for (uint32_t r = 0; r < K; ++r) {
        for (uint32_t c = 0; c < K; ++c) {
            S[static_cast<size_t>(r) * K2 + (K + c)] = S_skew[r * K + c];
            S[static_cast<size_t>(K + r) * K2 + c] = -S_skew[c * K + r];
            S[static_cast<size_t>(K + r) * K2 + (K + c)] = GtG_new[r * K + c];
        }
    }
    /* ---------------------------------------------------- */'''

c = c.replace(gram_anchor, gram_anchor + gram_patch)

# 3. Insertar Z correction justo antes de Y = X + tau * U * Z
z_anchor = r'    /* Y = X + tau * U Z,  U = [G X].'
z_patch = '''    /* Z_2 <- Z_2 - S_sym * Z_1 */
    for (uint32_t r = 0; r < K; ++r) {
        for (uint32_t c = 0; c < K; ++c) {
            double s = 0.0;
            for (uint32_t q = 0; q < K; ++q) {
                s += S_sym[r * K + q] * Z[static_cast<size_t>(q) * K + c];
            }
            Z[static_cast<size_t>(K + r) * K + c] -= s;
        }
    }
'''
c = c.replace(z_anchor, z_patch + z_anchor)

with open(cpp_file, 'w', encoding='utf-8') as f:
    f.write(c)
print("Rollback de B y aplicacion de Tangent Space finalizada.")
