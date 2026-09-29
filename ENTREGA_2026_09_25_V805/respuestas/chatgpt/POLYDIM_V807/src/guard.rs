//! ABI 807: graph invariants and extrinsic medoid. No Byzantine certification.
//! Unsafe FFI preconditions: valid aligned nonoverlapping buffers, live for call;
//! trusted caller supplies truthful capacities. Unwinding caught, aborts are not.
use std::panic::{catch_unwind, AssertUnwindSafe};
#[repr(C)]
pub struct Edge {pub u:u32,pub v:u32}
#[repr(C)]
#[derive(Default)]
pub struct GraphResult {pub vertices:u32,pub components:u32,pub edges:u64,pub cycles:i64}
#[repr(C)]
#[derive(Default)]
pub struct ClusterResult {pub candidates:u32,pub dimension:u32,pub component_size:u32,pub medoid_index:u32,pub components:u32,pub reserved:u32,pub cycles:i64,pub mean_distance:f64}
struct Dsu {p:Vec<usize>, rank:Vec<u8>,count:usize}
impl Dsu {
 fn new(n:usize)->Self{Self{p:(0..n).collect(),rank:vec![0;n],count:n}}
 fn find(&mut self,mut x:usize)->usize{while self.p[x]!=x{let y=self.p[x];self.p[x]=self.p[y];x=self.p[x];}x}
 fn join(&mut self,a:usize,b:usize){let(mut x,mut y)=(self.find(a),self.find(b));if x==y{return;}if self.rank[x]<self.rank[y]{std::mem::swap(&mut x,&mut y);}self.p[y]=x;if self.rank[x]==self.rank[y]{self.rank[x]+=1;}self.count-=1;}
}
fn protect<F:FnOnce()->i32>(f:F)->i32 {catch_unwind(AssertUnwindSafe(f)).unwrap_or(6)}
#[no_mangle] pub extern "C" fn pd_rust_abi_version()->u32{807}
#[no_mangle] pub extern "C" fn pd_graph_size()->usize{std::mem::size_of::<GraphResult>()}
#[no_mangle] pub extern "C" fn pd_graph_alignment()->usize{std::mem::align_of::<GraphResult>()}
#[no_mangle] pub extern "C" fn pd_cluster_size()->usize{std::mem::size_of::<ClusterResult>()}
#[no_mangle] pub extern "C" fn pd_cluster_alignment()->usize{std::mem::align_of::<ClusterResult>()}
#[no_mangle]
pub unsafe extern "C" fn pd_graph(edges:*const Edge,edge_count:usize,vertices:u32,out:*mut GraphResult)->i32{
 protect(||{
  if out.is_null(){return 1;}unsafe{*out=GraphResult::default();}
  if vertices==0||vertices>10_000_000||edge_count>100_000_000{return 2;}
  let e:&[Edge]=if edge_count==0{&[]}else{if edges.is_null(){return 1;}unsafe{std::slice::from_raw_parts(edges,edge_count)}};
  if e.iter().any(|e|e.u>=vertices||e.v>=vertices){return 2;}
  let mut d=Dsu::new(vertices as usize);for edge in e{d.join(edge.u as usize,edge.v as usize);}
  unsafe{*out=GraphResult{vertices,components:d.count as u32,edges:edge_count as u64,cycles:edge_count as i64-vertices as i64+d.count as i64};}0
 })
}
fn distance(a:&[f64],b:&[f64])->f64 {let mut scale=0f64;for(x,y)in a.iter().zip(b){scale=scale.max((x-y).abs());}if scale==0.0{return 0.0;}if !scale.is_finite(){return f64::INFINITY;}let(mut s,mut c)=(0f64,0f64);for(x,y)in a.iter().zip(b){let z=((x-y)/scale).powi(2);let t=s+z;c+=if s.abs()>=z.abs(){(s-t)+z}else{(z-t)+s};s=t;}scale*(s+c).sqrt()}
#[no_mangle]
pub unsafe extern "C" fn pd_cluster(input:*const f64,input_len:usize,n:u32,d:u32,threshold:f64,
 output:*mut f64,output_len:usize,out:*mut ClusterResult)->i32{
 protect(||{
  if out.is_null(){return 1;}unsafe{*out=ClusterResult::default();}
  if input.is_null()||output.is_null(){return 1;}
  let(n,d)=(n as usize,d as usize);let len=match n.checked_mul(d){Some(x)=>x,None=>return 2};
  if n==0||d==0||n>10000||d>10000000||len!=input_len||len>isize::MAX as usize/8{return 2;}
  if output_len<d{return 8;}if !threshold.is_finite()||threshold<0.0{return 2;}
  // Explicit work budget; callers must reduce swarm size rather than silently stall.
  if (n as u128)*(n as u128)*(d as u128)>2_000_000_000{return 8;}
  let a=unsafe{std::slice::from_raw_parts(input,len)};if a.iter().any(|x|!x.is_finite()){return 3;}
  let mut ds=Dsu::new(n);let mut edges=0i64;
  for i in 0..n{for j in i+1..n{let r=distance(&a[i*d..(i+1)*d],&a[j*d..(j+1)*d]);if !r.is_finite(){return 6;}if r<=threshold{ds.join(i,j);edges+=1;}}}
  let mut sizes=vec![0usize;n];for i in 0..n{let root=ds.find(i);sizes[root]+=1;}
  let mut root=0;for i in 1..n{if sizes[i]>sizes[root]{root=i;}}
  let members:Vec<usize>=(0..n).filter(|i|ds.find(*i)==root).collect();
  let(mut best,mut cost)=(members[0],f64::INFINITY);
  for &i in &members{let mut sum=0.0;for &j in &members{sum+=distance(&a[i*d..(i+1)*d],&a[j*d..(j+1)*d]);}if sum<cost{cost=sum;best=i;}}
  if !cost.is_finite(){return 6;}
  unsafe{std::ptr::copy_nonoverlapping(a.as_ptr().add(best*d),output,d);*out=ClusterResult{candidates:n as u32,dimension:d as u32,component_size:members.len() as u32,medoid_index:best as u32,components:ds.count as u32,reserved:0,cycles:edges-n as i64+ds.count as i64,mean_distance:cost/members.len() as f64};}0
 })
}
#[cfg(test)]mod tests{use super::*;
 #[test]fn empty_edges(){let mut r=GraphResult::default();assert_eq!(unsafe{pd_graph(std::ptr::null(),0,3,&mut r)},0);assert_eq!(r.components,3);assert_eq!(r.cycles,0);}
 #[test]fn identical_candidates(){let a=[1.,0.,1.,0.];let mut v=[0.;2];let mut r=ClusterResult::default();assert_eq!(unsafe{pd_cluster(a.as_ptr(),4,2,2,0.,v.as_mut_ptr(),2,&mut r)},0);assert_eq!(v,[1.,0.]);assert_eq!(r.component_size,2);}
 #[test]fn no_overalignment(){assert_eq!(std::mem::align_of::<ClusterResult>(),8);}
}
