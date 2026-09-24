#include "polydim.h"
#include <vector>
#include <cstdio>
#include <random>
#include <chrono>
#include <algorithm>
int main(){
  std::mt19937_64 rng(3); std::uniform_real_distribution<double> ud(-1,1);
  for (uint64_t D : {1000ull,100000ull,1000000ull}) {
    std::vector<double> u(D),v(D),y(D),yn(D),o(D);
    for(uint64_t i=0;i<D;++i){u[i]=ud(rng);v[i]=ud(rng);}
    polydim_orthonormalize_pair_f64(u.data(),v.data(),D,nullptr);
    for(uint64_t i=0;i<D;++i) y[i]=0.6*u[i]+0.3*v[i]+0.1*ud(rng);
    polydim_project_sphere_f64(y.data(),yn.data(),D,nullptr);
    PolydimReport r;
    polydim_rodrigues_geodesic_f64(yn.data(),u.data(),v.data(),o.data(),0.7,D,nullptr,&r);
    std::vector<double> t;
    for(int i=0;i<9;++i){auto a=std::chrono::steady_clock::now();
      polydim_rodrigues_geodesic_f64(yn.data(),u.data(),v.data(),o.data(),0.7,D,nullptr,&r);
      auto b=std::chrono::steady_clock::now();
      t.push_back(std::chrono::duration<double,std::milli>(b-a).count());}
    std::sort(t.begin(),t.end());
    std::printf("D=%-9llu mediana=%8.3f ms  deriva=%.3e\n",(unsigned long long)D,t[4],r.out_norm_err);
  }
  return 0;
}
