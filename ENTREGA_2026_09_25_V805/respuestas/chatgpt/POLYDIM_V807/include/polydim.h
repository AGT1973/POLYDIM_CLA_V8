#ifndef POLYDIM_V807_H
#define POLYDIM_V807_H
#include <stdint.h>
#include <stddef.h>
#ifdef _WIN32
#define PD_API __declspec(dllexport)
#else
#define PD_API __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
/* ABI 807 is intentionally incompatible with V806. All lengths count elements.
   Caller owns live, aligned, host-resident storage for the entire call.
   No concurrent mutation; input/output buffers must not overlap unless specified.
   Status 0 means successful computation; optimizer convergence is separate. */
enum pd_status { PD_OK=0, PD_NULL=1, PD_DIM=2, PD_NONFINITE=3,
 PD_RANK=4, PD_ALLOC=5, PD_NUMERIC=6, PD_UNSUPPORTED=7, PD_CAPACITY=8 };
typedef struct pd_result {
 uint64_t iterations;
 double objective, gradient_norm, orthogonality;
 int32_t converged;
 int32_t status;
} pd_result;
PD_API uint32_t pd_abi_version(void);
PD_API size_t pd_result_size(void);
PD_API size_t pd_result_alignment(void);
PD_API int32_t pd_gram(const double* x,size_t d,size_t k,size_t input_len,double* out,size_t out_len);
PD_API int32_t pd_qr(const double* x,size_t d,size_t k,size_t input_len,double* out,size_t out_len);
PD_API int32_t pd_normalize(const double* x,size_t d,double* out,size_t out_len);
PD_API int32_t pd_rotate(const double* y,const double* u,const double* v,size_t d,double theta,double* out,size_t out_len);
PD_API int32_t pd_optimize(const double* target,const double* initial,size_t d,size_t k,size_t input_len,
 uint64_t max_iterations,double learning_rate,double tolerance,double* out,size_t out_len,pd_result* result);
PD_API int32_t pd_lsm(const double* state,const double* input,const int8_t* signs,const uint32_t* permutation,
 size_t d,double leak,double input_scale,double* out,size_t out_len);
/* This FP32 convenience path returns FP32 precision, not a FP64 norm guarantee. */
PD_API int32_t pd_qr_f32(const float* x,size_t d,size_t k,size_t input_len,float* out,size_t out_len);
#ifdef __cplusplus
}
#endif
#endif
