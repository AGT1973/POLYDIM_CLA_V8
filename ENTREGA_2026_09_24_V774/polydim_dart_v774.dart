import 'dart:ffi';
import 'package:ffi/ffi.dart';

/// Dart FFI bindings para POLYDIM V774 (P0-06)
/// Implementa struct ABI C y NativeFinalizer idempotente.

class PolydimHandle extends Struct {
  external Pointer<Void> data;
  
  @Size()
  external int bytes;
  
  @Int32()
  external int refcount;
  
  @Uint32()
  external int flags;
  
  @Uint64()
  external int allocationId;
}

class PolydimSolverOptions extends Struct {
  @Uint64()
  external int maxIterations;
  @Double()
  external double gradientTolerance;
  @Double()
  external double stepTolerance;
  @Double()
  external double objectiveTolerance;
  @Double()
  external double orthoTolerance;
  @Uint32()
  external int retractionType;
  @Uint32()
  external int samplingPeriod;
  @Uint32()
  external int numThreads;
  @Double()
  external double learningRate;
  @Double()
  external double shiftRegularization;
}

class PolydimSolverResult extends Struct {
  @Int32()
  external int status;
  @Uint64()
  external int iterationsExecuted;
  @Double()
  external double finalObjective;
  @Double()
  external double finalGradNorm;
  @Double()
  external double finalOrthoError;
  @Uint64()
  external int totalTimeNs;
  
  @Array(256)
  external Array<Uint8> statusMessage;
}

/// Idempotent Wrapper de POLYDIM
class PolydimV774 {
  late final DynamicLibrary _lib;
  late final NativeFinalizer _finalizer;
  
  // Pointers to FFI functions
  late final Pointer<NativeFunction<Void Function(Pointer<PolydimHandle>)>> _releaseHandlePtr;

  PolydimV774(String path) {
    _lib = DynamicLibrary.open(path);
    _releaseHandlePtr = _lib.lookup<NativeFunction<Void Function(Pointer<PolydimHandle>)>>('polydim_handle_release');
    
    // NativeFinalizer idempotente que asegura liberación atómica
    _finalizer = NativeFinalizer(_releaseHandlePtr.cast());
  }

  /// Vincula el ciclo de vida del Handle C++ al Garbage Collector de Dart.
  void attachFinalizer(Object dartObject, Pointer<PolydimHandle> handlePtr) {
    _finalizer.attach(dartObject, handlePtr.cast(), detach: dartObject);
  }

  void detachFinalizer(Object dartObject) {
    _finalizer.detach(dartObject);
  }
}
