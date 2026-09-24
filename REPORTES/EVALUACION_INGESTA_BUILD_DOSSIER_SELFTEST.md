# 🔬 EVALUACIÓN ANALÍTICA DE INGESTA: ESPECIFICACIÓN Y SELF-TEST DE `build_dossier.py`
**Fecha:** 2026-09-20 | **Módulo:** Empaquetador Criptográfico y Generador Determinista de Dossiers de Auditoría
**Protocolo Activo:** Regla 19 (Ingesta y Evaluación Progresiva / Veto de Código)

---

## 🧭 1. Resumen y Propósito del Bloque Ingestado

El material recibido es el harness de pruebas unitarias (`test_build_dossier.py` / `self-test`) que define por contrato el comportamiento esperado del generador y verificador de dossiers `build_dossier.py`.

Este componente automatiza la construcción, verificación y sanitización del dossier de entrega en `ENTREGA_2026_09_19_V762/auditoria_externa/`.

---

## 🔍 2. Desglose de Requisitos Contractuales Auditados en el Test

El test evalúa 14 invariantes estrictos sobre un árbol sintético aislado en `tempfile.TemporaryDirectory()`:

1. **Detección de Links Rotos (`--rewrite-links`):**
   - Si un enlace Markdown apunta a un archivo inexistente (ej: `nope/missing.rs`), el compilador de dossier debe reportar `BROKEN` y salir con código `rc = 1`.
2. **Inclusión Exhaustiva en el Monolito (`02_ALL_SOURCE_SCRIPTS_MONOLITH.md`):**
   - Embebe automáticamente todos los fuentes (`include/polydim.h`, `src/polydim_kernel.cpp`, `rust/src/lib.rs`, `dart/polydim_ffi.dart`, `polydim_v762_monolito.py`, `tests/test_suite.cpp`, etc.).
   - Excluye explícitamente directorios efímeros o de compilación (`build/`, `junk.cpp`).
3. **Protección Anti-Colisión de Fences Markdown:**
   - Si el código fuente contiene bloques ` ``` `, el generador de Markdown escala dinámicamente el fence a 4 backticks (` ````cpp `) para prevenir la rotura sintáctica del documento.
4. **Hashes SHA-256 Deterministas (CRLF/LF Resilientes):**
   - El hash del archivo embebido en el Markdown coincide byte a byte con el hash real del archivo en disco (`read_bytes()`).
5. **Advertencia de Codificación (Non-UTF-8 Warning):**
   - Archivos con codificaciones alternativas (ej: `latin-1` con caracteres como `cañón`) son leídos y señalizados explícitamente (`NOT valid UTF-8`).
6. **Generación de Manifiesto Criptográfico (`MANIFEST.sha256`):**
   - Registra el hash SHA-256 de cada archivo fuente, binario compilado (`libpolydim.so`/`.dll`), log de ejecución (`logs/run1.log`) y documento de auditoría.
7. **Captura de Entorno de Silicio (`ENVIRONMENT.txt`):**
   - Vuelca automáticamente la telemetría del host (`cpu_model`, arquitectura, compilador).
8. **Reescritura de Enlaces Absolutos a Relativos:**
   - Transforma enlaces del tipo `file:///E:/POLYDIM_EINSOF/...` a rutas relativas portables (`../src/polydim_kernel.cpp`), asegurando que el dossier sea navegable en cualquier máquina externa sin depender de la unidad `E:\`.
9. **Detección de Stubs Residuales:**
   - Identifica y alerta si algún archivo del dossier conserva textos placeholder como `*(Ver código fuente completo en...)*` en lugar del código real embebido.
10. **Modo Verificación (`--verify`):**
    - Valida que el árbol de archivos no haya sido alterado respecto a `MANIFEST.sha256` (`VERIFY OK`).
    - Detecta fuentes modificadas (`MISMATCH`) y fuentes eliminadas (`MISSING`).
11. **Detección de Duplicados Divergentes (`--assert-same`):**
    - Compara archivos con doble extensión semántica (ej: `kernel_cpp_v762.cpp.txt` vs `src/polydim_kernel.cpp`).
    - Reporta `DUPLICATE DIVERGED` si no son idénticos (insensible a terminaciones de línea CRLF vs LF) y valida con `duplicate ok` si son idénticos.

---

## ⚖️ 3. Evaluación de Valor SOTA y Erradicación de Errores

* **Causa Raíz que Resuelve:** En la auditoría V761, Claude y Perplexity señalaron que el dossier contenía referencias a archivos que no estaban en el zip, enlaces absolutos `file:///E:/...` rotos para terceros, y stubs vacíos.
* **Impacto Arquitectónico:** `build_dossier.py` actúa como una compuerta CI/CD determinista que impide emitir cualquier entrega que no esté 100% autocontenida, verificada criptográficamente y libre de links rotos.
