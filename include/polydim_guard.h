#ifndef PD_GUARD_807_H
#define PD_GUARD_807_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {uint32_t u,v;} pd_edge;
typedef struct {uint32_t vertices,components;uint64_t edges;int64_t cycles;} pd_graph_result;
typedef struct {uint32_t candidates,dimension,component_size,medoid_index,components,reserved;int64_t cycles;double mean_distance;} pd_cluster_result;
uint32_t pd_rust_abi_version(void);
size_t pd_graph_size(void);size_t pd_graph_alignment(void);
size_t pd_cluster_size(void);size_t pd_cluster_alignment(void);
int32_t pd_graph(const pd_edge*,size_t,uint32_t,pd_graph_result*);
int32_t pd_cluster(const double*,size_t,uint32_t,uint32_t,double,double*,size_t,pd_cluster_result*);
#ifdef __cplusplus
}
#endif
#endif
