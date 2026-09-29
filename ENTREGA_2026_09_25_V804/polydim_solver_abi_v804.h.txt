/**
 * @file polydim_solver_abi.h
 * @brief Definición canónica del ABI C para el Solver de Stiefel, Plano de Control,
 *        SPSC Ring Buffer de Telemetría y Allocator Pairing en POLYDIM V773.
 * @copyright POLYDIM Architecture - 2026
 */

#ifndef POLYDIM_SOLVER_ABI_H
#define POLYDIM_SOLVER_ABI_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
#include <atomic>
extern "C" {
#endif

/* Códigos de Estado Terminales */
typedef enum {
    POLYDIM_STATUS_OK                  =  0,
    POLYDIM_STATUS_CONVERGED_GRADIENT  =  1,
    POLYDIM_STATUS_CONVERGED_STEP      =  2,
    POLYDIM_STATUS_MAX_ITERATIONS      =  3,
    POLYDIM_STATUS_ERR_NULL_PTR        = -1,
    POLYDIM_STATUS_ERR_INVALID_DIM     = -2,
    POLYDIM_STATUS_ERR_NUMERICAL_NAN   = -3,
    POLYDIM_STATUS_ERR_DEGENERATE_NORM = -4,
    POLYDIM_STATUS_ERR_ORTHO_VIOLATION = -5,
    POLYDIM_STATUS_ERR_ALLOC           = -6,
    POLYDIM_STATUS_ERR_RING_FULL       = -7,
    POLYDIM_STATUS_ERR_RING_EMPTY      = -8,
    POLYDIM_STATUS_ERR_UNKNOWN         = -99
} PolydimStatusCode;

/* Tipos de Retracción Stiefel */
typedef enum {
    POLYDIM_RETRACTION_CHOLQR2        = 0,
    POLYDIM_RETRACTION_CAYLEY_SMW     = 1,
    POLYDIM_RETRACTION_QR_HOUSEHOLDER = 2,
    POLYDIM_RETRACTION_SHIFTED_CHOLQR = 3
} PolydimRetractionType;

#define POLYDIM_CACHE_LINE 128
#define POLYDIM_ALIGN_128 alignas(POLYDIM_CACHE_LINE)
#define PMTP_MAX_READERS_PER_BANK 16

/* Opciones de Configuración del Optimizador */
#pragma pack(push, 8)
typedef struct {
    uint64_t max_iterations;
    double   gradient_tolerance;
    double   step_tolerance;
    double   objective_tolerance;
    double   ortho_tolerance;       /* Tolerancia de ortogonalidad ||X^T X - I||_F */
    uint32_t retraction_type;       /* PolydimRetractionType */
    uint32_t sampling_period;       /* Periodo de registro de telemetría */
    uint32_t num_threads;           /* Hilos OpenMP */
    double   learning_rate;         /* Tamaño de paso base alpha */
    double   shift_regularization;  /* Desplazamiento dinámico para Shifted CholQR */
} PolydimSolverOptions;

/* Punto Muestral de Telemetría Clásico */
typedef struct {
    uint64_t iteration;
    double   objective_value;
    double   gradient_norm;
    double   step_size;
    double   ortho_error;          /* ||X^T X - I||_F */
    uint64_t elapsed_time_ns;
} PolydimTelemetryPoint;

/* Buffer de Telemetría Preasignado */
typedef struct {
    PolydimTelemetryPoint* points;
    size_t   capacity;
    size_t   recorded_count;
} PolydimTelemetryBuffer;

/* Evento de Telemetría de Alta Frecuencia para SPSC Ring Buffer (64 bytes exactos) */
typedef struct {
    uint64_t timestamp_ns;
    uint32_t thread_id;
    uint32_t event_type;
    uint64_t iteration;
    double   objective_value;
    double   gradient_norm;
    double   ortho_error;
    double   step_size;
    uint64_t reserved;              /* Relleno para alineación exacta a 64 bytes */
} PolydimTelemetryEvent;

/* Anillo SPSC Wait-Free con Índices Aislados en Líneas de Caché Separadas (128 bytes) */
typedef struct {
    alignas(128) uint64_t write_index;
    alignas(128) uint64_t read_index;
    alignas(128) uint64_t capacity;       /* Potencia de 2 */
    uint64_t capacity_mask;
    PolydimTelemetryEvent* ring_buffer;
} PolydimSpscRing;

/* Estructura para Emparejamiento de Alocador y Conteo de Referencias (FFI Area 4) */
typedef struct {
    void*    data;
    size_t   bytes;
    int32_t  refcount;
    uint32_t flags;
    uint64_t allocation_id;
} PolydimHandle;

/* Resultado Final de la Optimización */
typedef struct {
    int32_t  status;                /* PolydimStatusCode */
    uint64_t iterations_executed;
    double   final_objective;
    double   final_grad_norm;
    double   final_ortho_error;
    uint64_t total_time_ns;
    char     status_message[256];
} PolydimSolverResult;

typedef enum {
    PMTP_LEASE_FREE      = 0,
    PMTP_LEASE_ACTIVE    = 1,
    PMTP_LEASE_RECLAIMED = 2,
    PMTP_LEASE_CLOSED    = 3
} PmtpLeaseState;

/* Registro de Lease Individual de Lector con Identidad de Proceso */
typedef struct {
    uint32_t pid;
    uint32_t state;                 /* PmtpLeaseState */
    uint64_t process_start_time_ns;
    uint64_t generation;
    uint64_t acquired_ns;
} PmtpReaderLease;

/* Encabezado de Slot PMTP Banked Double-Buffer Lease */
typedef struct POLYDIM_ALIGN_128 {
    uint32_t active_bank;           /* 0 o 1 */
    uint32_t writer_active;         /* 1 si hay escritor adquiriendo banco inactivo */
    uint64_t sequence;              /* Versión monotónica */
    uint32_t owner_pid;             /* PID del proceso que escribe */
    uint64_t owner_start_time_ns;   /* Timestamp de inicio del proceso */
    uint32_t num_reclaimed_orphans; /* Métrica de leases huérfanos recuperados */
    uint8_t  header_padding[96];    /* Alineado a 128 bytes */
    PmtpReaderLease leases_bank0[PMTP_MAX_READERS_PER_BANK];
    PmtpReaderLease leases_bank1[PMTP_MAX_READERS_PER_BANK];
} PmtpBankedSlotHeader;
#pragma pack(pop)

/* Verificaciones Estáticas de ABI (static_assert offsetof) */
#ifdef __cplusplus
static_assert(sizeof(PolydimTelemetryEvent) == 64, "PolydimTelemetryEvent debe medir exactamente 64 bytes");
static_assert(offsetof(PolydimTelemetryEvent, timestamp_ns) == 0, "Alineación de timestamp_ns inválida");
static_assert(offsetof(PolydimTelemetryEvent, thread_id) == 8, "Alineación de thread_id inválida");
static_assert(offsetof(PolydimTelemetryEvent, event_type) == 12, "Alineación de event_type inválida");
static_assert(offsetof(PolydimTelemetryEvent, iteration) == 16, "Alineación de iteration inválida");
static_assert(offsetof(PolydimTelemetryEvent, objective_value) == 24, "Alineación de objective_value inválida");
static_assert(offsetof(PolydimTelemetryEvent, gradient_norm) == 32, "Alineación de gradient_norm inválida");
static_assert(offsetof(PolydimTelemetryEvent, ortho_error) == 40, "Alineación de ortho_error inválida");
static_assert(offsetof(PolydimTelemetryEvent, step_size) == 48, "Alineación de step_size inválida");
static_assert(offsetof(PolydimTelemetryEvent, reserved) == 56, "Alineación de reserved inválida");

static_assert(sizeof(PolydimTelemetryPoint) == 48, "PolydimTelemetryPoint debe medir exactamente 48 bytes");
static_assert(sizeof(PolydimHandle) == 32, "PolydimHandle debe medir exactamente 32 bytes");
#endif

/* ========================================================================= */
/* FUNCIONES EXPORTADAS C ABI                                                */
/* ========================================================================= */

/**
 * @brief Ejecuta la optimización completa sobre la variedad de Stiefel St(D, K) en C++.
 */
int32_t polydim_stiefel_optimize(
    const double*               problem_data,
    size_t                      problem_size,
    double*                     X,
    size_t                      D,
    size_t                      K,
    const PolydimSolverOptions* options,
    PolydimSolverResult*        result,
    PolydimTelemetryBuffer*     telemetry
);

/**
 * @brief Computa la Gramiana simétrica K_out = X^T * X usando BLAS dsyrk o fallback micro-tiled.
 */
int32_t polydim_gram_dsyrk(
    const double* X,
    size_t D,
    size_t K,
    double* K_out,
    uint32_t num_threads
);

/**
 * @brief Copia tensorial streaming mediante Non-Temporal Stores (evita contaminación de caché en D >= 10^5).
 */
int32_t polydim_stream_copy_nt(
    double* dest,
    const double* src,
    size_t count
);

/**
 * @brief Inicializa el anillo SPSC de telemetría wait-free.
 */
int32_t polydim_spsc_init(
    PolydimSpscRing* ring,
    size_t capacity
);

/**
 * @brief Inserción wait-free en el anillo SPSC.
 */
int32_t polydim_spsc_push(
    PolydimSpscRing* ring,
    const PolydimTelemetryEvent* event
);

/**
 * @brief Extracción wait-free del anillo SPSC.
 */
int32_t polydim_spsc_pop(
    PolydimSpscRing* ring,
    PolydimTelemetryEvent* event
);

/**
 * @brief Libera los recursos del anillo SPSC.
 */
void polydim_spsc_destroy(
    PolydimSpscRing* ring
);

/**
 * @brief Alocador emparejado seguro (Strict Allocator Pairing).
 */
void* polydim_alloc_aligned(
    size_t bytes,
    size_t alignment
);

/**
 * @brief Liberador emparejado seguro.
 */
void polydim_free_aligned(
    void* ptr
);

/**
 * @brief Crea un handle refcounted protegido contra UAF en FFI boundaries.
 */
PolydimHandle* polydim_handle_create(
    size_t bytes,
    size_t alignment
);

/**
 * @brief Incrementa el refcount de un handle.
 */
void polydim_handle_retain(
    PolydimHandle* handle
);

/**
 * @brief Decrementa el refcount y libera cuando llega a 0.
 */
void polydim_handle_release(
    PolydimHandle* handle
);

#ifdef __cplusplus
}
#endif

#endif /* POLYDIM_SOLVER_ABI_H */
