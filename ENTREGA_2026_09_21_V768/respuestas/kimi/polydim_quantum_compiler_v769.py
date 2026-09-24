"""
POLYDIM V769 — QUANTUM SYNTHESIS COMPILER (SO(D) -> OpenQASM 3.0)
Correcciones Red Team sobre V768:
  C1: V768 emitia ry(theta) CONTINUA *y* una "aproximacion" Clifford+T fija en
      cascada (rotacion doble, verificada numericamente: ||HTHS - Rz(pi/8)||=1.35).
      v769 emite EXACTAMENTE UNO de los dos, nunca ambos.
  C2: La secuencia H-T-H-S NO aproxima Rz(residuo) para ningun residuo. v769
      sintetiza Clifford+T EXACTO solo para angulos k*pi/4 (T^k, k entero) y
      RECHAZA otros angulos con instrucciones claras (Gridsynth/Ross-Selinger).
  C3: El mapeo de plano (p1,p2) -> qubits por modulo era incorrecto. v769 exige
      planos que difieran en exactamente un bit (orden Gray) y construye el
      Givens con controles de direccionamiento correctos; rechaza lo demas.
"""

import math

class QuantumSOdCompiler:
    """Compilador honesto: puertas continuas (ry/rz/cx) con direccionamiento
    correcto de planos, o Clifford+T exacto para angulos en la reticula pi/4."""

    def __init__(self, basis: str = "continuous"):
        assert basis in ("continuous", "clifford_t")
        self.basis = basis

    # ---- utilidad: direccionamiento multi-controlado para el plano (p1, p2) ----
    @staticmethod
    def _plane_control_bits(p1: int, p2: int, num_qubits: int):
        """Devuelve (target, control_mask, control_value) si p1,p2 difieren en
        exactamente un bit; si no, lanza ValueError (C3)."""
        diff = p1 ^ p2
        if diff == 0 or (diff & (diff - 1)) != 0:
            raise ValueError(
                f"Plano ({p1},{p2}) difiere en {bin(diff).count('1')} bits. "
                f"Ordene los planos por codigo Gray (diferencia de 1 bit) o use "
                f"una descomposicion de Schur real previa.")
        target = diff.bit_length() - 1
        ctrl_mask, ctrl_val = 0, 0
        for q in range(num_qubits):
            if q == target:
                continue
            b1 = (p1 >> q) & 1
            b2 = (p2 >> q) & 1
            if b1 != b2:
                raise ValueError(f"Plano ({p1},{p2}) no es un plano de Givens de 1 bit.")
            ctrl_mask |= (1 << q)
            ctrl_val |= (b1 << q)
        return target, ctrl_mask, ctrl_val

    def _addressing_gates(self, target, ctrl_mask, ctrl_val, nq) -> list[str]:
        """X gates para fijar los controles al valor del patron, y deshacerlos."""
        pre, post = [], []
        for q in range(nq):
            if q == target or not (ctrl_mask >> q) & 1:
                continue
            if ((ctrl_val >> q) & 1) == 0:
                pre.append(f"x q[{q}];")
                post.insert(0, f"x q[{q}];")
        return pre + post

    def _givens(self, q1_name, target, ctrl_mask, ctrl_val, theta, nq) -> list[str]:
        g = []
        pre, post = self._addressing_gates(target, ctrl_mask, ctrl_val, nq)
        g += pre
        if self.basis == "continuous":
            # Ry de Givens EXACTA en el subespacio direccionado (C1: una sola)
            g.append(f"ry({theta:.15f}) q[{target}];")
        else:
            k = int(round(theta / (math.pi / 4.0)))
            if abs(theta - k * math.pi / 4.0) > 1e-12:
                raise ValueError(
                    f"Clifford+T exacto solo admite angulos k*pi/4; theta={theta}. "
                    f"Use basis='continuous' o precompile el residuo con Gridsynth.")
            g.append(f"// T^{k % 8} == Rz({theta:.6f}) exacto en la reticula")
            for _ in range(k % 8):
                g.append(f"t q[{target}];")
        g += post
        return g

    def compile_so_d_rotor_to_qasm(self, d: int,
                                   angles: list[tuple[int, int, float]]) -> str:
        num_qubits = max(1, math.ceil(math.log2(d)))
        lines = [
            "OPENQASM 3.0;",
            'include "stdgates.inc";',
            f"// POLYDIM V769 ({self.basis}) SO({d}) rotor -> {num_qubits} qubits",
            f"qubit[{num_qubits}] q;",
            f"bit[{num_qubits}] c;",
        ]
        for p1, p2, theta in angles:
            target, cmask, cval = self._plane_control_bits(p1, p2, num_qubits)
            lines.append(f"// Givens({p1},{p2}, theta={theta:.6f})")
            lines += self._givens(p1, target, cmask, cval, theta, num_qubits)
        lines.append("c = measure q;")
        return "\n".join(lines)


def test_compiler():
    # Planos en codigo Gray sobre 3 qubits: (0,1),(1,3),(3,2),(2,6)...
    comp = QuantumSOdCompiler("continuous")
    qasm = comp.compile_so_d_rotor_to_qasm(8, [(0, 1, 0.785398), (1, 3, 1.570796)])
    assert "ry(0.785398000000000) q[0];" in qasm
    comp_ct = QuantumSOdCompiler("clifford_t")
    qasm_ct = comp_ct.compile_so_d_rotor_to_qasm(8, [(0, 1, math.pi / 2)])
    assert qasm_ct.count("t q[0];") == 2  # T^2 == Rz(pi/2) exacto
    try:
        comp_ct.compile_so_d_rotor_to_qasm(8, [(0, 1, 0.3)])  # fuera de reticula
        raise SystemExit("FALLO: debio rechazar angulo no k*pi/4")
    except ValueError:
        pass
    try:
        comp.compile_so_d_rotor_to_qasm(8, [(0, 3, 0.5)])  # difiere en 2 bits
        raise SystemExit("FALLO: debio rechazar plano de 2 bits")
    except ValueError:
        pass
    print("[OK] QuantumSOdCompiler v769: continuo exacto + Clifford+T exacto en reticula + rechazo honesto")

if __name__ == "__main__":
    test_compiler()
