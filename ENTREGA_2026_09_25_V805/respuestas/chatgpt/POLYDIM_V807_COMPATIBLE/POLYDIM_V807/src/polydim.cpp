#include "polydim.h"
#ifdef __FAST_MATH__
#error "POLYDIM reference kernel requires strict IEEE floating point"
#endif
#include <algorithm>
#include <cmath>
#include <limits>
#include <new>
#include <vector>
#include <cfenv>
namespace {
using Vec=std::vector<double>;
bool shape(size_t d,size_t k,size_t len) {
 return d && k && k<=d && d<=size_t(PTRDIFF_MAX)/sizeof(double)/k && len==d*k;
}
bool finite(const double* x,size_t n){for(size_t i=0;i<n;++i)if(!std::isfinite(x[i]))return false;return true;}
// Neumaier accumulator: strict IEEE build, finite products required.
struct Sum{double s=0,c=0;void add(double x){double t=s+x;c+=(std::abs(s)>=std::abs(x))?(s-t)+x:(x-t)+s;s=t;}double get()const{return s+c;}};
double dot(const double* a,const double* b,size_t n,size_t sa=1,size_t sb=1){Sum s;for(size_t i=0;i<n;++i)s.add(a[i*sa]*b[i*sb]);return s.get();}
double norm(const double* x,size_t n){double scale=0;for(size_t i=0;i<n;++i)scale=std::max(scale,std::abs(x[i]));if(scale==0)return 0;Sum s;for(size_t i=0;i<n;++i){double z=x[i]/scale;s.add(z*z);}return scale*std::sqrt(s.get());}
bool sphere(const double* x,size_t n){double r=norm(x,n);return std::isfinite(r)&&std::abs(r-1)<=1e-10;}
int qr(const double* x,size_t d,size_t k,Vec& q){
 // Scaled Householder thin QR. Reject unresolved rank; never manufacture columns.
 size_t n=d*k;double scale=0;for(size_t i=0;i<n;++i)scale=std::max(scale,std::abs(x[i]));if(scale==0)return PD_RANK;
 Vec a(n),tau(k),sgn(k);for(size_t i=0;i<n;++i)a[i]=x[i]/scale;
 double floor=64*std::numeric_limits<double>::epsilon()*std::max(1.0,std::sqrt(double(d)));
 for(size_t j=0;j<k;++j){
  double r=0;for(size_t i=j;i<d;++i)r=std::hypot(r,a[i*k+j]);
  if(!std::isfinite(r)||r<=floor)return PD_RANK;
  double alpha=-std::copysign(r,a[j*k+j]),v0=a[j*k+j]-alpha;
  tau[j]=(alpha-a[j*k+j])/alpha;sgn[j]=std::signbit(alpha)?-1:1;
  for(size_t i=j+1;i<d;++i)a[i*k+j]/=v0;
  a[j*k+j]=alpha;
  for(size_t c=j+1;c<k;++c){Sum s;s.add(a[j*k+c]);for(size_t i=j+1;i<d;++i)s.add(a[i*k+j]*a[i*k+c]);double t=tau[j]*s.get();a[j*k+c]-=t;for(size_t i=j+1;i<d;++i)a[i*k+c]-=a[i*k+j]*t;}
 }
 q.assign(n,0);for(size_t j=0;j<k;++j)q[j*k+j]=1;
 for(size_t jj=k;jj>0;--jj){size_t j=jj-1;for(size_t c=0;c<k;++c){Sum s;s.add(q[j*k+c]);for(size_t i=j+1;i<d;++i)s.add(a[i*k+j]*q[i*k+c]);double t=tau[j]*s.get();q[j*k+c]-=t;for(size_t i=j+1;i<d;++i)q[i*k+c]-=a[i*k+j]*t;}}
 for(size_t i=0;i<d;++i)for(size_t j=0;j<k;++j)q[i*k+j]*=sgn[j];
 return finite(q.data(),n)?PD_OK:PD_NUMERIC;
}
double ortho(const Vec& x,size_t d,size_t k){Sum e;for(size_t i=0;i<k;++i)for(size_t j=0;j<k;++j){double t=dot(x.data()+i,x.data()+j,d,k,k)-(i==j?1:0);e.add(t*t);}return std::sqrt(e.get());}
double objective(const Vec& x,const double* t){Sum s;for(size_t i=0;i<x.size();++i){double v=x[i]-t[i];s.add(.5*v*v);}return s.get();}
void gradient(const Vec& x,const double* target,size_t d,size_t k,Vec& g){
 size_t n=d*k;g.resize(n);for(size_t i=0;i<n;++i)g[i]=x[i]-target[i];
 Vec xtg(k*k),sym(k*k);for(size_t i=0;i<k;++i)for(size_t j=0;j<k;++j)xtg[i*k+j]=dot(x.data()+i,g.data()+j,d,k,k);
 for(size_t i=0;i<k;++i)for(size_t j=0;j<k;++j)sym[i*k+j]=.5*(xtg[i*k+j]+xtg[j*k+i]);
 for(size_t i=0;i<d;++i)for(size_t j=0;j<k;++j){Sum s;for(size_t c=0;c<k;++c)s.add(x[i*k+c]*sym[c*k+j]);g[i*k+j]-=s.get();}
}
// All exported computational calls contain C++ exceptions. Raw pointer validity
// remains a caller obligation: no portable C ABI can prove it from an address.
template<class F>int guard(F f)noexcept{try{if(std::fegetround()!=FE_TONEAREST)return PD_NUMERIC;volatile double tiny=std::numeric_limits<double>::denorm_min();volatile double two=2.0;volatile double probe=tiny*two;if(probe==0)return PD_NUMERIC;return f();}catch(const std::bad_alloc&){return PD_ALLOC;}catch(...){return PD_NUMERIC;}}
}
extern "C" {
uint32_t pd_abi_version(){return 807;}
size_t pd_result_size(){return sizeof(pd_result);}
size_t pd_result_alignment(){return alignof(pd_result);}
int32_t pd_gram(const double*x,size_t d,size_t k,size_t len,double*out,size_t cap){return guard([&]()->int{
 if(!x||!out)return PD_NULL;if(!shape(d,k,len))return PD_DIM;if(cap<k*k)return PD_CAPACITY;if(!finite(x,len))return PD_NONFINITE;
 Vec g(k*k);for(size_t i=0;i<k;++i)for(size_t j=i;j<k;++j)g[i*k+j]=g[j*k+i]=dot(x+i,x+j,d,k,k);
 if(!finite(g.data(),g.size()))return PD_NUMERIC;std::copy(g.begin(),g.end(),out);return PD_OK;});}
int32_t pd_qr(const double*x,size_t d,size_t k,size_t len,double*out,size_t cap){return guard([&]()->int{
 if(!x||!out)return PD_NULL;if(!shape(d,k,len))return PD_DIM;if(cap<len)return PD_CAPACITY;if(!finite(x,len))return PD_NONFINITE;Vec q;int st=qr(x,d,k,q);if(st)return st;if(ortho(q,d,k)>1e-10*std::max(1.0,double(k)))return PD_NUMERIC;std::copy(q.begin(),q.end(),out);return PD_OK;});}
int32_t pd_qr_f32(const float*x,size_t d,size_t k,size_t len,float*out,size_t cap){return guard([&]()->int{
 if(!x||!out)return PD_NULL;if(!shape(d,k,len))return PD_DIM;if(cap<len)return PD_CAPACITY;Vec a(len),q;for(size_t i=0;i<len;++i){if(!std::isfinite(x[i]))return PD_NONFINITE;a[i]=x[i];}int st=qr(a.data(),d,k,q);if(st)return st;for(size_t i=0;i<len;++i)out[i]=float(q[i]);return PD_OK;});}
int32_t pd_normalize(const double*x,size_t d,double*out,size_t cap){return guard([&]()->int{
 if(!x||!out)return PD_NULL;if(!shape(d,1,d))return PD_DIM;if(cap<d)return PD_CAPACITY;if(!finite(x,d))return PD_NONFINITE;
 double scale=0;for(size_t i=0;i<d;++i)scale=std::max(scale,std::abs(x[i]));if(!scale)return PD_RANK;Vec q(d);for(size_t i=0;i<d;++i)q[i]=x[i]/scale;double r=norm(q.data(),d);if(!std::isfinite(r)||r==0)return PD_NUMERIC;for(double&v:q)v/=r;std::copy(q.begin(),q.end(),out);return PD_OK;});}
int32_t pd_rotate(const double*y,const double*u,const double*v,size_t d,double theta,double*out,size_t cap){return guard([&]()->int{
 if(!y||!u||!v||!out)return PD_NULL;if(!shape(d,1,d))return PD_DIM;if(cap<d)return PD_CAPACITY;if(!std::isfinite(theta)||!finite(y,d)||!finite(u,d)||!finite(v,d))return PD_NONFINITE;
 if(!sphere(y,d)||!sphere(u,d)||!sphere(v,d)||std::abs(dot(u,v,d))>1e-10)return PD_NUMERIC;
 double a=dot(y,u,d),b=dot(y,v,d),s=std::sin(theta),h=std::sin(theta*.5),versin=2*h*h;
 Vec q(d);for(size_t i=0;i<d;++i){double delta=-versin*(a*u[i]+b*v[i])+s*(a*v[i]-b*u[i]);q[i]=y[i]+delta;}
 if(!finite(q.data(),d)||!sphere(q.data(),d))return PD_NUMERIC;std::copy(q.begin(),q.end(),out);return PD_OK;});}
int32_t pd_optimize(const double*t,const double*initial,size_t d,size_t k,size_t len,uint64_t maxit,double lr,double tol,double*out,size_t cap,pd_result*res){
 if(!res)return PD_NULL;*res={0,0,0,0,0,PD_NUMERIC};
 int st=guard([&]()->int{
 if(!t||!initial||!out)return PD_NULL;if(!shape(d,k,len)||!maxit||maxit>1000000)return PD_DIM;if(cap<len)return PD_CAPACITY;
 if(!std::isfinite(lr)||lr<=0||!std::isfinite(tol)||tol<=0)return PD_DIM;if(!finite(t,len)||!finite(initial,len))return PD_NONFINITE;
 Vec x,g;int rc=qr(initial,d,k,x);if(rc)return rc;double f=objective(x,t);if(!std::isfinite(f))return PD_NUMERIC;
 for(uint64_t it=0;it<maxit;++it){gradient(x,t,d,k,g);double gn=norm(g.data(),len);if(!std::isfinite(gn))return PD_NUMERIC;if(gn<=tol)break;
  double step=lr;bool accepted=false;Vec trial(len),q;
  for(int bt=0;bt<40;++bt){for(size_t i=0;i<len;++i)trial[i]=x[i]-step*g[i];if(finite(trial.data(),len)&&qr(trial.data(),d,k,q)==PD_OK){double nf=objective(q,t);if(std::isfinite(nf)&&nf<=f-1e-4*step*gn*gn){x.swap(q);f=nf;accepted=true;break;}}step*=.5;}
  if(!accepted)break;++res->iterations;
 }
 gradient(x,t,d,k,g);res->objective=objective(x,t);res->gradient_norm=norm(g.data(),len);res->orthogonality=ortho(x,d,k);
 if(!std::isfinite(res->objective)||!std::isfinite(res->gradient_norm)||res->orthogonality>1e-10*double(k))return PD_NUMERIC;
 res->converged=res->gradient_norm<=tol;std::copy(x.begin(),x.end(),out);return PD_OK;});res->status=st;return st;
}
int32_t pd_lsm(const double*state,const double*input,const int8_t*signs,const uint32_t*p,size_t d,double leak,double inscale,double*out,size_t cap){return guard([&]()->int{
 if(!state||!signs||!p||!out)return PD_NULL;if(!shape(d,1,d)||(d&(d-1))||d>UINT32_MAX)return PD_DIM;if(cap<d)return PD_CAPACITY;
 if(!std::isfinite(leak)||leak<0||leak>1||!std::isfinite(inscale))return PD_DIM;if(!finite(state,d)||(input&&!finite(input,d)))return PD_NONFINITE;
 std::vector<uint8_t>seen(d);Vec q(d);for(size_t i=0;i<d;++i){if(p[i]>=d||seen[p[i]]||(signs[i]!=1&&signs[i]!=-1))return PD_DIM;seen[p[i]]=1;q[i]=state[p[i]]*signs[i];}
 // Normalize at every butterfly to reduce intermediate overflow.
 const double c=std::sqrt(.5);for(size_t h=1;h<d;h*=2)for(size_t base=0;base<d;base+=2*h)for(size_t j=0;j<h;++j){double a=q[base+j]*c,b=q[base+j+h]*c;q[base+j]=a+b;q[base+j+h]=a-b;}
 for(size_t i=0;i<d;++i){double z=q[i]+(input?inscale*input[i]:0);if(!std::isfinite(z))return PD_NUMERIC;q[i]=(1-leak)*state[i]+leak*std::tanh(z);}
 if(!finite(q.data(),d))return PD_NUMERIC;std::copy(q.begin(),q.end(),out);return PD_OK;});}
}
