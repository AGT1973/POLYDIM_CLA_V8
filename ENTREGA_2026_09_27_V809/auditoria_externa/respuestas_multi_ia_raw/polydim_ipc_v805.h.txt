#ifndef POLYDIM_IPC_V805_H
#define POLYDIM_IPC_V805_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Wait on the address `addr`. If its value is `expected_val`, block until awakened or timeout_ms elapses.
 * 
 * @param addr Address to wait on.
 * @param expected_val The value expected to be at addr.
 * @param timeout_ms Timeout in milliseconds. Use 0xFFFFFFFF for infinite.
 * @return 0 on success (awakened), or non-zero on error/timeout.
 */
int32_t polydim_futex_wait_v805(volatile uint32_t* addr, uint32_t expected_val, uint32_t timeout_ms);

/**
 * @brief Wake one or all threads waiting on `addr`.
 * 
 * @param addr Address to wake on.
 * @param wake_all True to wake all waiting threads, false to wake a single thread.
 * @return 0 on success.
 */
int32_t polydim_futex_wake_v805(volatile uint32_t* addr, bool wake_all);

#ifdef __cplusplus
}
#endif

#endif // POLYDIM_IPC_V805_H
