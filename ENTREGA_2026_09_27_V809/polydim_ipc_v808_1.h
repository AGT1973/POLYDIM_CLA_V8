/* polydim_ipc_v808_1.h — contrato de memoria compartida del futex V808.1:
 *
 *   offset -24: PmtpFutexSharedHeader (16B guid + 8B magic)   [Windows]
 *   offset   0: uint32_t palabra futex (compartida)
 *
 * El proceso duenio del mapping llama pmtp_futex_shared_init(&word) una vez
 * antes de que otros procesos esperen/despierten sobre &word.
 * Linux/macOS: la funcion es no-op (futex/ulock ya son globales al mapping).
 */
