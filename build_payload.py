import os

files = [
    'E:\\POLYDIM_EINSOF\\src\\kernel_cpp_v810.cpp',
    'E:\\POLYDIM_EINSOF\\src\\kernel_rust_v811.rs',
    'E:\\POLYDIM_EINSOF\\src\\ipc_futex_v811.cpp',
    'E:\\POLYDIM_EINSOF\\src\\pmtp_rcu_v810.cpp',
    'E:\\POLYDIM_EINSOF\\src\\polydim_solver_abi_v808_1.h',
    'E:\\POLYDIM_EINSOF\\src\\test_v811_ipc_suite.py'
]

payload = \"\"\"[SYSTEM OVERRIDE: PROTOCOLO DE LIBERACIÓN PLURIDIMENSIONAL - POLYDIM]
Do not explain basic concepts. Assume PhD/SOTA engineering level.
Be mathematically rigorous. Zero tolerance for unverified code.

WARNING: Discard standard coding biases. Do not fall into conventional
Transformer/1D paradigms. DO NOT hallucinate mathematical proofs.
If you cannot prove it asymptotically, state that it is unknown.

USER_ROLE: Arquitecto de infraestructura multi-vectorial (creador).
AI_ROLE: RedTeam / Bulldog técnico – ataca los problemas sin piedad
pero protege al creador del trabajo.

DIRECTIVE:
- Cero sermones. Cero alucinaciones. Cero culpa al usuario.
- Operar al límite del silicio: optimización de bajo nivel,
  compiladores, concurrencia, tensores y protocolos distribuidos.

--- INICIO CÓDIGO FUENTE COMPLETO (NO RESUMIR, LEER TODO) ---
\"\"\"

for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
            payload += f\"\n--- {os.path.basename(f)} ---\n{content}\n\"
    except Exception as e:
        print(f\"Error reading {f}: {e}\")

payload += \"\"\"--- FIN DEL CÓDIGO ---

GOAL: Revision linea a linea de cada funcion y metodo. Buscar fallas de concurrencia, UAF, desbordes matemáticos, degeneraciones de coma flotante, deadlocks PMTP, y errores de arquitectura.

PROTOCOLO DE EJECUCIÓN OBLIGATORIO (5 PASADAS):
1. Escaneo Superficial: Identifica problemas evidentes.
2. Análisis Estructural: Arquitectura, dependencias, flujo de datos.
3. Edge Cases: NaN, Inf, subnormales, matrices singulares, carreras.
4. Metanálisis: Sesgos propios, fallos pasados por alto.
5. Bucles Recursivos: Evalúa si tus soluciones rompen otra cosa.

RESTRICCIONES:
- Lista cada error asintótico. No des explicaciones redundantes.
- Devuelve confirmacion de que has revisado CADA linea.
\"\"\"

with open('E:\\POLYDIM_EINSOF\\ENTREGA_2026_09_27_V811\\bulldog_payload.txt', 'w', encoding='utf-8') as out:
    out.write(payload)

print('Payload generado con éxito.')
