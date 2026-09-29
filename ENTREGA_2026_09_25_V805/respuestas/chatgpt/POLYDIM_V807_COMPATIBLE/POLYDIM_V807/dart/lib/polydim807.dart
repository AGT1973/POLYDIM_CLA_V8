// Optional CPU adapter for ABI 807. Source reviewed; Dart runtime not tested here.
import 'dart:ffi';
import 'package:ffi/ffi.dart';
typedef _VersionN = Uint32 Function();
typedef _VersionD = int Function();
typedef _RotateN = Int32 Function(Pointer<Double>,Pointer<Double>,Pointer<Double>,Size,Double,Pointer<Double>,Size);
typedef _RotateD = int Function(Pointer<Double>,Pointer<Double>,Pointer<Double>,int,double,Pointer<Double>,int);
class Polydim807 {
 final DynamicLibrary library;
 late final _RotateD _rotate;
 Polydim807(String absoluteLibraryPath):library=DynamicLibrary.open(absoluteLibraryPath){
  final version=library.lookupFunction<_VersionN,_VersionD>('pd_abi_version')();
  if(version!=807)throw StateError('ABI incompatible: $version');
  _rotate=library.lookupFunction<_RotateN,_RotateD>('pd_rotate');
 }
 List<double> rotate(List<double> y,List<double> u,List<double> v,double theta){
  if(y.isEmpty||y.length!=u.length||y.length!=v.length||!theta.isFinite)throw ArgumentError('shape or angle');
  if([y,u,v].any((a)=>a.any((x)=>!x.isFinite)))throw ArgumentError('nonfinite input');
  final arena=Arena();
  try{
   final d=y.length;
   final py=arena<Double>(d),pu=arena<Double>(d),pv=arena<Double>(d),out=arena<Double>(d);
   for(var i=0;i<d;i++){py[i]=y[i];pu[i]=u[i];pv[i]=v[i];}
   final status=_rotate(py,pu,pv,d,theta,out,d);
   if(status!=0)throw StateError('pd_rotate status=$status');
   return List<double>.generate(d,(i)=>out[i],growable:false);
  }finally{arena.releaseAll();}
 }
}
