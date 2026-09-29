#ifndef POLYDIM_SOLVER_ABI_H
#define POLYDIM_SOLVER_ABI_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PMTP_MAX_READERS_PER_BANK 32
#define PMTP_NUM_RCU_SLOTS 3

/* Estados de los Leases de Lectura */
#define PMTP_LEASE_FREE      0
#define PMTP_LEASE_ACTIVE    1
#define PMTP_LEASE_CLOSED    2
#define PMTP_LEASE_RECLAIMED 3

/* Códigos de Error Normalizados V808 */
#define POLYDIM_STATUS_OK                        0
#define POLYDIM_STATUS_CONVERGED_GRADIENT        1
#define POLYDIM_STATUS_CONVERGED_STEP            2
#define POLYDIM_STATUS_MAX_ITERATIONS            3
#define POLYDIM_STATUS_ERR_NULL_PTR             -1
#define POLYDIM_STATUS_ERR_INVALID_DIM          -2
#define POLYDIM_STATUS_ERR_ALLOC                -3
#define POLYDIM_STATUS_ERR_NUMERICAL_NAN        -4
#define POLYDIM_STATUS_ERR_ORTHO_VIOLATION      -5
#define POLYDIM_STATUS_ERR_RING_FULL            -6
#define POLYDIM_STATUS_ERR_RING_EMPTY           -7
#define POLYDIM_STATUS_ERR_ABI_MISMATCH         -8
#define POLYDIM_STATUS_ERR_RANK_DEFICIENT       -9
#define POLYDIM_STATUS_ERR_WRITER_BUSY          -10
#define POLYDIM_STATUS_ERR_NO_FREE_SLOT         -11
#define POLYDIM_STATUS_ERR_DRAIN_TIMEOUT        -12

/* Tipos de Retracción Stiefel */
#define POLYDIM_RETRACTION_CHOLQR2              0
#define POLYDIM_RETRACTION_CAYLEY_SMW           1

#pragma pack(push, 8)

/* Descriptor de Lease con contador de generación monotónica (Anti-ABA) */
typedef struct {
    uint32_t state;                  /* 0: Free, 1: Active, 2: Closed, 3: Reclaimed */
    uint32_t pid;                    /* PID del proceso lector */
    uint64_t process_start_time_ns;  /* Identificador temporal contra PID recycling */
    uint64_t generation;             /* Versión monotónica para prevenir ABA */
    uint32_t epoch;                  /* Época exacta de asignación */
    uint32_t pad;                    /* Alineación a 32 bytes */
} PmtpReaderLease;

/* Cabecera Banked RCU de 3 Épocas (Alineación Estricta a 128 Bytes) */
typedef struct {
    uint32_t global_epoch;           /* Época global monotónica */
    uint32_t active_bank;            /* Índice del banco actualmente legible (0, 1, 2) */
    uint32_t writer_active;          /* Mutex atómico para el escritor único */
    uint32_t owner_pid;              /* PID del proceso escritor */
    uint64_t sequence;               /* Número de secuencia de publicación */
    uint64_t owner_start_time_ns;    /* Timestamp de inicio del escritor */
    uint32_t num_reclaimed_orphans;  /* Contador de procesos zombis purgados */
    uint32_t pad0;                   /* Relleno de 32 bits */
    uint8_t  header_padding[88];     /* Desplaza el inicio de leases exactamente a offset 128 */
    PmtpReaderLease leases_bank0[PMTP_MAX_READERS_PER_BANK];
    PmtpReaderLease leases_bank1[PMTP_MAX_READERS_PER_BANK];
    PmtpReaderLease leases_bank2[PMTP_MAX_READERS_PER_BANK];
} PmtpBankedSlotHeader;

/* Estructura de Opciones del Optimizador */
typedef struct {
    uint64_t max_iterations;
    double   gradient_tolerance;
    double   step_tolerance;
    double   ortho_tolerance;
    double   learning_rate;
    uint32_t sampling_period;
    uint32_t num_threads;
    int32_t  retraction_type;
    double   shift_regularization;
} PolydimSolverOptions;

/* Resultados de la Optimización */
typedef struct {
    int32_t  status;
    uint64_t iterations_executed;
    double   final_objective;
    double   final_grad_norm;
    double   final_ortho_error;
    uint64_t total_time_ns;
    char     status_message[256];
} PolydimSolverResult;

/* Punto de Telemetría */
typedef struct {
    uint64_t iteration;
    double   objective_value;
    double   gradient_norm;
    double   step_size;
    double   ortho_error;
    uint64_t elapsed_time_ns;
} PolydimTelemetryPoint;

/* Búfer de Telemetría */
typedef struct {
    PolydimTelemetryPoint* points;
    size_t capacity;
    size_t recorded_count;
} PolydimTelemetryBuffer;

/* Evento de Telemetría para el Anillo SPSC (Alineado a 128B) */
typedef struct {
    uint64_t timestamp_ns;
    uint32_t event_type;
    uint32_t thread_id;
    double   metrics[14];
} PolydimTelemetryEvent;

/* Anillo SPSC Wait-Free con Aislamiento de Línea de Caché */
typedef struct {
    uint64_t write_index;
    uint8_t  pad_write[120];
    uint64_t read_index;
    uint8_t  pad_read[120];
    size_t   capacity;
    size_t   capacity_mask;
    PolydimTelemetryEvent* ring_buffer;
} PolydimSpscRing;

/* Handle con Conteo de Referencia */
typedef struct {
    void*    data;
    size_t   bytes;
    int32_t  refcount;
    uint32_t flags;
    uint64_t allocation_id;
} PolydimHandle;

#pragma pack(pop)

#ifdef __cplusplus
static_assert(sizeof(PmtpReaderLease) == 32, "PmtpReaderLease must be exactly 32 bytes");
static_assert(offsetof(PmtpBankedSlotHeader, leases_bank0) == 128, "leases_bank0 must start at byte 128");
#endif

#ifdef __cplusplus
}
#endif

#endif /* POLYDIM_SOLVER_ABI_H */
