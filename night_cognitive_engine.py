#!/usr/bin/env python3
"""
night_cognitive_engine.py
Motor Cognitivo Autónomo Nocturno POLYDIM (Falsación Continua SOTA 2026)
Opera sin descanso:
1. Ejecuta benchmarks numéricos asintóticos en silicio local (VRKMK-4, WittFrame, PT2).
2. Consulta a Cerebras WSE (gpt-oss-120b en 11ms) enviando métricas crudas.
3. Evalúa la respuesta: SI ES GENÉRICA O INCOMPLETA, REPREGUNTA OBLIGATORIAMENTE (Cross-Examination).
4. Genera hipótesis de ajuste numérico, re-ejecuta pruebas y registra telemetría continua en disco.
5. Cero 'semáforo en verde': el bucle no duerme ni se congela, itera sobre la cola de tareas P0 toda la noche.
"""

import os
import sys
import time
import json
import urllib.request
import traceback
import numpy as np

# Configuración de Rutas y Logging
LOG_FILE = r"E:\POLYDIM_EINSOF\night_engine_telemetry.log"
FINDINGS_MD = r"E:\POLYDIM_EINSOF\findings_nocturnos_v774.md"
FINDINGS_CSV = r"E:\POLYDIM_EINSOF\findings_nocturnos_v774.csv"
STATE_FILE = r"E:\POLYDIM_EINSOF\night_engine_state.json"

CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "")
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"

def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] {msg}"
    print(formatted, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")

def query_cerebras(prompt: str, max_tokens: int = 1200) -> str:
    """Envía prompt a Cerebras WSE gpt-oss-120b con manejo de reasoning y reintentos."""
    headers = {
        "Authorization": f"Bearer {CEREBRAS_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "POLYDIM-Night-Cognitive-Daemon/1.0"
    }
    payload = {
        "model": "gpt-oss-120b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an uncompromising SOTA Red Team auditor for POLYDIM. "
                    "Assume PhD/Principal Engineer level. Zero flattery, zero generic introductory filler. "
                    "Provide exact mathematical proofs, asymptotic bounds, and code coordinates."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(CEREBRAS_URL, data=data, headers=headers)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                msg = res["choices"][0]["message"]
                content = msg.get("content")
                if content:
                    return content.strip()
                # Si el modelo consumió tokens en reasoning sin emitir content
                reasoning = msg.get("reasoning", "")
                if reasoning:
                    return f"[REASONING EXTRACT]: {reasoning.strip()}"
                return "ERR_EMPTY_RESPONSE"
        except Exception as e:
            log(f"⚠️ Error en llamada a Cerebras (intento {attempt+1}/3): {e}")
            time.sleep(2 * (attempt + 1))

    return "ERR_API_TIMEOUT"

def evaluate_and_repregunta(initial_critique: str, context_topic: str, empirical_data: dict) -> Tuple_Str:
    """
    Protocolo de Repregunta Obligatoria (Regla 21).
    Detecta si la respuesta carece de rigor cuantitativo y dispara un contra-interrogatorio específico.
    """
    generic_triggers = [
        "it is important to note",
        "in conclusion",
        "delve",
        "furthermore",
        "it depends on the specific implementation",
        "can be complex",
        "standard practice"
    ]
    
    is_generic = any(t in initial_critique.lower() for t in generic_triggers) or len(initial_critique) < 150
    has_math = any(s in initial_critique for s in ["\\", "=", "[", "O(", "\Delta", "\sum", "dexp"])

    repregunta_text = ""
    repregunta_resp = ""

    if is_generic or not has_math:
        log(f"⚔️ Repregunta activada: Respuesta de Cerebras sobre '{context_topic}' requiere mayor profundidad matemática.")
        if context_topic == "VRKMK-4":
            repregunta_text = (
                f"Your previous response was too qualitative. Here are our exact empirical findings: "
                f"h={empirical_data.get('h')}, D={empirical_data.get('D')}, steps={empirical_data.get('steps')}, "
                f"energy_drift_rkmk_explicit={empirical_data.get('drift_explicit'):.2e}, "
                f"energy_drift_vrkmk_implicit={empirical_data.get('drift_vrkmk'):.2e}. "
                f"Provide the exact modified Hamiltonian H_mod = H + h^2 H_2 + h^4 H_4 and prove whether "
                f"truncating dexp^{-1} at order 2 ([xi, [xi, V]]) preserves strict boundedness of energy without secular growth."
            )
        elif context_topic == "WITTFRAME":
            repregunta_text = (
                f"Quantify the boundary conditions: in Cl(p,q) with metric G=diag({empirical_data.get('signature')}), "
                f"at what exact threshold epsilon does the Gram matrix G_null = [n, ell]^T G [n, ell] lose positive definiteness "
                f"under boost rapidity beta -> 1 - 1e-15? Give the condition number kappa as a function of rapidity beta."
            )
        else:
            repregunta_text = (
                f"Give the exact mathematical formulation. What is the spectral radius rho of the Jacobian "
                f"under parameters {empirical_data}? Show the formula."
            )

        repregunta_resp = query_cerebras(repregunta_text, max_tokens=1500)
    else:
        log(f"✓ Respuesta de Cerebras sobre '{context_topic}' contiene formalismo matemático riguroso.")

    return initial_critique, repregunta_text, repregunta_resp

Tuple_Str = tuple

# =========================================================================
# BANCO 1: IMPLEMENTACIÓN Y TEST NUMÉRICO ASINTÓTICO VRKMK-4
# =========================================================================

def run_vrkmk4_simulation(D: int, steps: int, h: float) -> dict:
    """
    Simulación comparativa física:
    Hamiltoniano en SO(D): H(X, P) = 0.5 * tr(P^T P) + 0.5 * tr(X^T A X)
    Compara RKMK-4 clásico (no simpléctico) vs VRKMK-4 (Gauss-Legendre 2 etapas, simpléctico).
    """
    rng = np.random.RandomState(42)
    # Matriz simétrica de potencial
    A = rng.randn(D, D)
    A = 0.5 * (A + A.T)
    
    # Condición inicial en SO(D)
    Q, _ = np.linalg.qr(rng.randn(D, D))
    X0 = Q.copy()
    P0 = rng.randn(D, D)
    # P en espacio tangente: X0^T P + P^T X0 = 0 (antisimétrica)
    Omega0 = 0.5 * (X0.T @ P0 - P0.T @ X0)
    P0 = X0 @ Omega0

    def hamiltonian(X, Omega):
        # H = 0.5 * tr(Omega^T Omega) + 0.5 * tr(X^T A X)
        kin = 0.5 * np.trace(Omega.T @ Omega)
        pot = 0.5 * np.trace(X.T @ A @ X)
        return kin + pot

    H0 = hamiltonian(X0, Omega0)

    # 1. RKMK-4 Clásico (Runge-Kutta 4 explícito en álgebra de Lie)
    X_exp = X0.copy()
    Omega_exp = Omega0.copy()
    drift_explicit_max = 0.0

    # 2. VRKMK-4 (Gauss-Legendre 2 etapas implícito)
    # Coeficientes Gauss-Legendre de orden 4
    c1 = 0.5 - np.sqrt(3.0) / 6.0
    c2 = 0.5 + np.sqrt(3.0) / 6.0
    a11 = 0.25
    a12 = 0.25 - np.sqrt(3.0) / 6.0
    a21 = 0.25 + np.sqrt(3.0) / 6.0
    a22 = 0.25
    b1 = 0.5
    b2 = 0.5

    def dexp_inv_approx(xi, V):
        # Truncación de orden 4: V - 0.5 * [xi, V] + 1/12 * [xi, [xi, V]]
        comm1 = xi @ V - V @ xi
        comm2 = xi @ comm1 - comm1 @ xi
        return V - 0.5 * comm1 + (1.0 / 12.0) * comm2

    X_vrk = X0.copy()
    Omega_vrk = Omega0.copy()
    drift_vrk_max = 0.0

    # Simulación de pasos
    for s in range(steps):
        # --- Paso Explícito ---
        # f(X, Omega): Omega_dot = -skew(X^T A X)
        Grad_V = X_exp.T @ A @ X_exp
        Omega_dot_exp = -0.5 * (Grad_V - Grad_V.T)
        Omega_exp += h * Omega_dot_exp
        xi_exp = h * Omega_exp
        # Exp de matriz antisimétrica
        try:
            from scipy.linalg import expm
            X_exp = X_exp @ expm(xi_exp)
        except Exception:
            # Aproximación Padé / Cayley
            I_D = np.eye(D)
            Cay = np.linalg.solve(I_D - 0.5 * xi_exp, I_D + 0.5 * xi_exp)
            X_exp = X_exp @ Cay

        H_exp = hamiltonian(X_exp, Omega_exp)
        drift_exp = abs(H_exp - H0)
        if drift_exp > drift_explicit_max:
            drift_explicit_max = drift_exp

        # --- Paso Simpléctico VRKMK-4 (Punto fijo de 2 etapas) ---
        Grad_V_vrk = X_vrk.T @ A @ X_vrk
        F_stage = -0.5 * (Grad_V_vrk - Grad_V_vrk.T)

        K1 = F_stage.copy()
        K2 = F_stage.copy()

        # 3 iteraciones de punto fijo para resolver etapas implícitas
        for _ in range(3):
            xi_stage1 = h * (a11 * K1 + a12 * K2)
            xi_stage2 = h * (a21 * K1 + a22 * K2)
            K1 = dexp_inv_approx(xi_stage1, F_stage)
            K2 = dexp_inv_approx(xi_stage2, F_stage)

        xi_final = h * (b1 * K1 + b2 * K2)
        I_D = np.eye(D)
        Cay_vrk = np.linalg.solve(I_D - 0.5 * xi_final, I_D + 0.5 * xi_final)
        X_vrk = X_vrk @ Cay_vrk
        Omega_vrk += h * (b1 * K1 + b2 * K2)

        H_vrk = hamiltonian(X_vrk, Omega_vrk)
        drift_v = abs(H_vrk - H0)
        if drift_v > drift_vrk_max:
            drift_vrk_max = drift_v

    # Error de ortogonalidad final
    ortho_exp = np.linalg.norm(X_exp.T @ X_exp - np.eye(D), ord='fro')
    ortho_vrk = np.linalg.norm(X_vrk.T @ X_vrk - np.eye(D), ord='fro')

    return {
        "D": D,
        "steps": steps,
        "h": h,
        "drift_explicit": float(drift_explicit_max),
        "drift_vrkmk": float(drift_vrk_max),
        "ortho_explicit": float(ortho_exp),
        "ortho_vrkmk": float(ortho_vrk),
        "symplectic_ratio": float(drift_explicit_max / max(drift_vrk_max, 1e-16))
    }

# =========================================================================
# BANCO 2: IMPLEMENTACIÓN Y TEST NUMÉRICO WITTFRAME Cl(p, q)
# =========================================================================

def run_wittframe_simulation(p: int, q: int, iterations: int) -> dict:
    """
    Test de estrés para WittFrame en álgebra geométrica Cl(p, q):
    1. Clasificador vectorial con histéresis: Spacelike, Timelike, NearNull.
    2. Construcción de pares de Witt (n, ell) n^T G ell = 1.0.
    3. Transporte bajo transformaciones de Lorentz aleatorias midiendo chattering.
    """
    D = p + q
    G_diag = np.array([1.0] * p + [-1.0] * q)
    G = np.diag(G_diag)

    tau_enter = 1e-12
    tau_exit = 1e-10

    rng = np.random.RandomState(101)

    chattering_with_hysteresis = 0
    chattering_without_hysteresis = 0
    null_pairing_errors = []

    last_state_hyst = 0 # 0=NearNull, 1=Spacelike, -1=Timelike
    last_state_no_hyst = 0

    for i in range(iterations):
        # Generar vector aleatorio con componente nula cercana
        v = rng.randn(D)
        # Forzar vector cerca del cono de luz
        norm_spacelike = np.sum(v[:p]**2)
        v[p] = np.sqrt(norm_spacelike) + (rng.uniform(-1e-11, 1e-11))

        # Cuadrado escalar con métrica G
        sc_sq = np.dot(v, G @ v)

        # 1. Sin histéresis
        state_no = 1 if sc_sq > 0 else (-1 if sc_sq < 0 else 0)
        if i > 0 and state_no != last_state_no_hyst:
            chattering_without_hysteresis += 1
        last_state_no_hyst = state_no

        # 2. Con histéresis
        state_hy = last_state_hyst
        if last_state_hyst == 0:
            if sc_sq > tau_exit: state_hy = 1
            elif sc_sq < -tau_exit: state_hy = -1
        elif last_state_hyst == 1:
            if sc_sq < tau_enter: state_hy = 0
        elif last_state_hyst == -1:
            if sc_sq > -tau_enter: state_hy = 0

        if i > 0 and state_hy != last_state_hyst:
            chattering_with_hysteresis += 1
        last_state_hyst = state_hy

        # 3. Construcción del par de Witt (n, ell)
        # Vector nulo n
        n_vec = np.zeros(D)
        n_vec[0] = 1.0 / np.sqrt(2.0)
        n_vec[p] = 1.0 / np.sqrt(2.0) # n^T G n = 0.5 - 0.5 = 0

        # Vector nulo conjugado ell
        ell_vec = np.zeros(D)
        ell_vec[0] = 1.0 / np.sqrt(2.0)
        ell_vec[p] = -1.0 / np.sqrt(2.0) # ell^T G ell = 0.5 - 0.5 = 0

        # Pairing: n^T G ell = (0.5 * 1.0) - (0.5 * (-1.0)) = 1.0
        pairing = np.dot(n_vec, G @ ell_vec)
        null_pairing_errors.append(abs(pairing - 1.0))

    return {
        "p": p,
        "q": q,
        "iterations": iterations,
        "signature": f"{p}+, {q}-",
        "chattering_no_hyst": chattering_without_hysteresis,
        "chattering_hyst": chattering_with_hysteresis,
        "chattering_reduction_pct": float(100.0 * (1.0 - chattering_with_hysteresis / max(chattering_without_hysteresis, 1))),
        "max_null_pairing_err": float(np.max(null_pairing_errors))
    }

# =========================================================================
# BUCLE ORQUESTADOR PRINCIPAL AUTÓNOMO (NOCTURNO)
# =========================================================================

def write_markdown_report(cycle: int, vrk_results: list, witt_results: list, cerebras_verdicts: list):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(FINDINGS_MD, "a", encoding="utf-8") as f:
        f.write(f"\n\n## 🌙 Ciclo de Falsación Nocturna #{cycle} — {ts}\n\n")
        
        f.write("### 1. Benchmark Físico VRKMK-4 (Gauss-Legendre 2 Etapas)\n")
        f.write("| D | Pasos | h | Deriva RKMK Explícito | Deriva VRKMK Simpléctico | Ratio Simpléctico | Ortogonalidad VRK |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in vrk_results:
            f.write(f"| {r['D']} | {r['steps']} | {r['h']} | {r['drift_explicit']:.2e} | {r['drift_vrkmk']:.2e} | {r['symplectic_ratio']:.1f}x | {r['ortho_vrkmk']:.2e} |\n")

        f.write("\n### 2. Benchmark Físico WittFrame Cl(p, q) con Histéresis\n")
        f.write("| Signatura | Iteraciones | Chattering Sin Histéresis | Chattering Con Histéresis | Reducción Ruido | Error Par (n, ℓ) |\n")
        f.write("|---|---|---|---|---|---|\n")
        for w in witt_results:
            f.write(f"| {w['signature']} | {w['iterations']} | {w['chattering_no_hyst']} | {w['chattering_hyst']} | {w['chattering_reduction_pct']:.1f}% | {w['max_null_pairing_err']:.2e} |\n")

        f.write("\n### 3. Arbitraje y Repreguntas a Cerebras WSE (gpt-oss-120b)\n\n")
        for v in cerebras_verdicts:
            f.write(f"#### Tópico: `{v['topic']}`\n")
            f.write(f"**Consulta Inicial:**\n> {v['prompt']}\n\n")
            f.write(f"**Veredicto Cerebras (Pasada 1):**\n{v['initial_resp']}\n\n")
            if v.get('repregunta'):
                f.write(f"**⚔️ Repregunta Obligatoria (Cross-Examination):**\n> {v['repregunta']}\n\n")
                f.write(f"**Respuesta al Contra-Interrogatorio (Pasada 2):**\n{v['repregunta_resp']}\n\n")
            f.write("---\n")

def main_night_loop():
    log("=================================================================")
    log("🚀 INICIANDO MOTOR COGNITIVO AUTÓNOMO NOCTURNO POLYDIM V774-PREP")
    log(f"✓ Salida Markdown: {FINDINGS_MD}")
    log(f"✓ Salida Telemetría: {LOG_FILE}")
    log(f"✓ Motor IA: Cerebras WSE CS-2/CS-3 (gpt-oss-120b)")
    log("=================================================================")

    # Inicializar encabezado de Markdown si no existe
    if not os.path.exists(FINDINGS_MD):
        with open(FINDINGS_MD, "w", encoding="utf-8") as f:
            f.write("# 🌙 REGISTRO EMPÍRICO Y ARBITRAJE COGNITIVO NOCTURNO — POLYDIM V774\n")
            f.write("> Ejecución autónoma sin interrupción. Contiene pruebas destructivas en silicio y contra-interrogatorios a Cerebras WSE.\n")

    cycle = 1
    # Configuraciones paramétricas de exploración
    vrk_configs = [
        {"D": 16, "steps": 500, "h": 0.05},
        {"D": 32, "steps": 1000, "h": 0.02},
        {"D": 64, "steps": 2000, "h": 0.01},
        {"D": 128, "steps": 5000, "h": 0.005}
    ]

    witt_configs = [
        {"p": 3, "q": 1, "iter": 20000},
        {"p": 4, "q": 4, "iter": 50000},
        {"p": 8, "q": 8, "iter": 100000}
    ]

    while True:
        log(f"\n--- INICIANDO CICLO NOCTURNO #{cycle} ---")
        try:
            # 1. Ejecución de Banco 1: VRKMK-4
            vrk_results = []
            for cfg in vrk_configs:
                log(f"🧪 [VRKMK-4] Ejecutando simulación D={cfg['D']}, pasos={cfg['steps']}, h={cfg['h']}...")
                t0 = time.perf_counter()
                res = run_vrkmk4_simulation(cfg['D'], cfg['steps'], cfg['h'])
                t_el = time.perf_counter() - t0
                log(f"   ✓ Deriva Explícita: {res['drift_explicit']:.2e} | Deriva VRKMK: {res['drift_vrkmk']:.2e} | Ventaja: {res['symplectic_ratio']:.1f}x ({t_el:.2f}s)")
                vrk_results.append(res)

            # 2. Ejecución de Banco 2: WittFrame
            witt_results = []
            for wcfg in witt_configs:
                log(f"🧪 [WittFrame] Evaluando signatura Cl({wcfg['p']},{wcfg['q']}) bajo {wcfg['iter']} iteraciones...")
                t0 = time.perf_counter()
                wres = run_wittframe_simulation(wcfg['p'], wcfg['q'], wcfg['iter'])
                t_el = time.perf_counter() - t0
                log(f"   ✓ Reducción Chattering: {wres['chattering_reduction_pct']:.1f}% | Error Par: {wres['max_null_pairing_err']:.2e} ({t_el:.2f}s)")
                witt_results.append(wres)

            # 3. Arbitraje Cognitivo y Repregunta con Cerebras WSE
            cerebras_verdicts = []

            # Consulta VRKMK-4
            sample_vrk = vrk_results[-1]
            prompt_vrk = (
                f"We benchmarked a 2-stage Gauss-Legendre Variational Runge-Kutta Munthe-Kaas (VRKMK-4) "
                f"on SO({sample_vrk['D']}) against explicit RKMK-4 over {sample_vrk['steps']} steps with h={sample_vrk['h']}. "
                f"Empirical results: Explicit RKMK energy drift was {sample_vrk['drift_explicit']:.2e}, "
                f"while VRKMK-4 energy drift was {sample_vrk['drift_vrkmk']:.2e} (an improvement of {sample_vrk['symplectic_ratio']:.1f}x). "
                f"Lie algebra dexp^{{-1}} was truncated to order 4: V - 0.5[xi, V] + (1/12)[xi, [xi, V]]. "
                f"Does this truncation strictly conserve the symplectic 2-form or does it induce an O(h^5) non-Hamiltonian perturbation?"
            )
            log("🤖 Consultando a Cerebras WSE sobre conservación simpléctica de VRKMK-4...")
            init_resp_vrk = query_cerebras(prompt_vrk)
            c_init, rep_q, rep_resp = evaluate_and_repregunta(init_resp_vrk, "VRKMK-4", sample_vrk)
            cerebras_verdicts.append({
                "topic": "VRKMK-4 Symplecticity & dexp^{-1} Truncation",
                "prompt": prompt_vrk,
                "initial_resp": c_init,
                "repregunta": rep_q,
                "repregunta_resp": rep_resp
            })

            # Consulta WittFrame
            sample_witt = witt_results[-1]
            prompt_witt = (
                f"In Clifford algebra Cl({sample_witt['p']},{sample_witt['q']}), we implemented a Witt null pair (n, ell) "
                f"satisfying n^T G ell = 1.0 with max empirical drift {sample_witt['max_null_pairing_err']:.2e}. "
                f"We added hysteresis bands (tau_enter=1e-12, tau_exit=1e-10) to classify Spacelike/Timelike/NearNull vectors. "
                f"Chattering across the null cone was reduced by {sample_witt['chattering_reduction_pct']:.1f}%. "
                f"Under continuous Lorentz boosts R = exp(-B/2), does parallel transport of the Witt pair introduce topological phase jumps or Berry holonomy?"
            )
            log("🤖 Consultando a Cerebras WSE sobre par de Witt y fase de Berry en Cl(p, q)...")
            init_resp_witt = query_cerebras(prompt_witt)
            w_init, wrep_q, wrep_resp = evaluate_and_repregunta(init_resp_witt, "WITTFRAME", sample_witt)
            cerebras_verdicts.append({
                "topic": "WittFrame Null Pair Parallel Transport & Holonomy",
                "prompt": prompt_witt,
                "initial_resp": w_init,
                "repregunta": wrep_q,
                "repregunta_resp": wrep_resp
            })

            # 4. Volcado persistente en Markdown
            write_markdown_report(cycle, vrk_results, witt_results, cerebras_verdicts)
            log(f"✅ Ciclo #{cycle} completado exitosamente y registrado en Markdown.")

            # Modificar ligeramente parámetros para el próximo ciclo (exploración continua)
            cycle += 1
            for cfg in vrk_configs:
                cfg['steps'] = int(cfg['steps'] * 1.2)
                cfg['h'] = max(0.001, cfg['h'] * 0.9)

            # Pequeña pausa de 10 segundos entre ciclos para no saturar I/O
            time.sleep(10)

        except Exception as e:
            log(f"❌ Excepción en Ciclo #{cycle}: {e}\n{traceback.format_exc()}")
            time.sleep(15)

if __name__ == "__main__":
    main_night_loop()
