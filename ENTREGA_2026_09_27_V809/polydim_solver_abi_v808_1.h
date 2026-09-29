/* ========================================================= */
/* FILE: ABI HEADER: polydim_solver_abi_v808_1.h  (PATCH C2/C5) */
/* Cambios vs V808:                                            */
/*  + ABI_VERSION y polydim_abi_probe() para detectar desync. */
/*  + PmtpBankedSlotHeader: prev_bank + writer_heartbeat_ns    */
/*    (offsets recalculados, leases siguen en offset 128).     */
/* ========================================================= */
#ifndef POLYDIM_SOLVER_ABI_H
#define POLYDIM_SOLVER_ABI_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PMTP_ABI_VERSION_V808_1   0x80801u
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
    uint64_t generation;             /* sequence del publicador en el momento de adquirir */
    uint32_t epoch;                  /* global_epoch en el momento de adquirir */
    uint32_t pad;                    /* Alineación a 32 bytes */
} PmtpReaderLease;

/* Cabecera Banked RCU de 3 Épocas (Alineación Estricta a 128 Bytes)
 * V808.1: prev_bank y writer_heartbeat_ns para protocolo correcto.
 * Invariante del protocolo V808.1:
 *   - Los lectores leen ÚNICAMENTE active_bank (published).
 *   - El escritor escribe el banco que NO es active_bank NI prev_bank,
 *     drena ese banco con timeout real y publica en commit.
 *   - global_epoch avanza SOLO en commit_writer. */
typedef struct {
    uint32_t global_epoch;           /* 0  - época global monotónica (avanza en commit) */
    uint32_t active_bank;            /* 4  - banco publicado; los lectores leen ESTE */
    uint32_t writer_active;          /* 8  - mutex atómico del escritor único */
    uint32_t owner_pid;              /* 12 - PID del proceso escritor actual */
    uint64_t sequence;               /* 16 - nº de secuencia de publicación */
    uint64_t owner_start_time_ns;    /* 24 - timestamp de inicio del escritor */
    uint32_t num_reclaimed_orphans;  /* 32 - contador de procesos zombi purgados */
    uint32_t prev_bank;              /* 36 - banco publicado en el commit anterior */
    uint64_t writer_heartbeat_ns;    /* 40 - último latido del escritor (anti-steal erróneo) */
    uint8_t  header_padding[80];     /* 48..128 - leases_bank0 empieza exactamente en 128 */
    PmtpReaderLease leases_bank0[PMTP_MAX_READERS_PER_BANK];
    PmtpReaderLease leases_bank1[PMTP_MAX_READERS_PER_BANK];
    PmtpReaderLease leases_bank2[PMTP_MAX_READERS_PER_BANK];
} PmtpBankedSlotHeader;

/* Estructura de Opciones del Optimizador (64 bytes, SIN objective_tolerance) */
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

/* Evento de Telemetría para el Anillo SPSC (128 bytes, espejo exacto C++/Python) */
typedef struct {
    uint64_t timestamp_ns;
    uint32_t event_type;
    uint32_t thread_id;
    double   metrics[14];            /* metrics[0]=iteration, [1]=objective, ... */
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
static_assert(sizeof(PolydimSolverOptions) == 64, "PolydimSolverOptions ABI drift");
static_assert(sizeof(PolydimTelemetryEvent) == 128, "PolydimTelemetryEvent ABI drift");
#endif

#ifdef __cplusplus
}
#endif

#endif /* POLYDIM_SOLVER_ABI_H */
