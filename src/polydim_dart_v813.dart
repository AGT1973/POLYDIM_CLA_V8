import 'dart:ffi';
import 'dart:typed_data';
import 'package:ffi/ffi.dart';

/// =========================================================================
/// POLYDIM V813 DART FFI & 3D GAUSSIAN SPLATTING TERMINAL BRIDGE
/// Conecta la esfera unitaria S^(D-1) con shaders Impeller / Vulkan / Metal.
/// =========================================================================

/// 1. ABI Structures C++ / Rust
final class PolydimHandle extends Struct {
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

final class PolydimEdge extends Struct {
  @Uint32()
  external int u;
  @Uint32()
  external int v;
}

final class PolydimBettiResult extends Struct {
  @Int32()
  external int status;
  @Uint32()
  external int componentsBetti0;
  @Int64()
  external int cyclesBetti1;
  @Uint32()
  external int numVertices;
  @Uint32()
  external int numEdges;
  @Uint8()
  external int isCriticallyHealthy;
  @Uint8()
  external int isOptimallyHealthy;

  @Array(102)
  external Array<Uint8> pad;
}

final class PolydimFrechetBettiResult extends Struct {
  @Int32()
  external int status;
  @Uint32()
  external int numCandidates;
  @Uint32()
  external int dimension;
  @Uint32()
  external int connectedComponentsBetti0;
  @Int64()
  external int cyclesBetti1;
  @Uint32()
  external int consensusNodeIdx;
  @Uint32()
  external int activeSwarmCount;
  @Uint32()
  external int rejectedOutliersCount;
  @Double()
  external double frechetResidual;
  @Uint8()
  external int isConsensusCertified;

  @Array(79)
  external Array<Uint8> pad;
}

/// 2. Gaussian Splatting 3D Struct (Render Output - 4-byte floats for GPU/Shaders)
final class GaussianSplatPoint3D extends Struct {
  @Float()
  external double posX;
  @Float()
  external double posY;
  @Float()
  external double posZ;

  @Float()
  external double scaleX;
  @Float()
  external double scaleY;
  @Float()
  external double scaleZ;

  @Float()
  external double rotW;
  @Float()
  external double rotX;
  @Float()
  external double rotY;
  @Float()
  external double rotZ;

  @Float()
  external double opacity;

  @Float()
  external double r;
  @Float()
  external double g;
  @Float()
  external double b;
}

/// Dart-managed representation of a 3D Gaussian Splat
class GaussianSplatData {
  final double posX, posY, posZ;
  final double scaleX, scaleY, scaleZ;
  final double rotW, rotX, rotY, rotZ;
  final double opacity;
  final double r, g, b;

  const GaussianSplatData({
    required this.posX, required this.posY, required this.posZ,
    required this.scaleX, required this.scaleY, required this.scaleZ,
    required this.rotW, required this.rotX, required this.rotY, required this.rotZ,
    required this.opacity,
    required this.r, required this.g, required this.b,
  });
}

/// 3. Polydim V813 Client Wrapper
class PolydimV813 {
  late final DynamicLibrary _cppLib;
  late final DynamicLibrary _rustLib;
  late final NativeFinalizer _handleFinalizer;

  // C++ Functions
  late final int Function(Pointer<Double>, int, int, Pointer<Double>, int) _gramDsyrk;
  late final int Function(Pointer<Double>, Pointer<Double>, Pointer<Int8>, Pointer<Uint32>, Pointer<Int8>, Pointer<Uint32>, int, double, double) _structuredLsm;
  late final Pointer<PolydimHandle> Function(int, int) _handleCreate;
  late final void Function(Pointer<PolydimHandle>) _handleRelease;

  // Rust Functions
  late final int Function(Pointer<PolydimEdge>, int, int, int, Pointer<PolydimBettiResult>) _bettiGuard;
  late final int Function(Pointer<Double>, int, int, double, int, Pointer<Double>, Pointer<PolydimFrechetBettiResult>) _frechetBetti;

  PolydimV813({required String cppDllPath, required String rustDllPath}) {
    _cppLib = DynamicLibrary.open(cppDllPath);
    _rustLib = DynamicLibrary.open(rustDllPath);

    // Bind C++
    _gramDsyrk = _cppLib.lookupFunction<
        Int32 Function(Pointer<Double>, Size, Size, Pointer<Double>, Uint32),
        int Function(Pointer<Double>, int, int, Pointer<Double>, int)>('polydim_gram_dsyrk');

    _structuredLsm = _cppLib.lookupFunction<
        Int32 Function(Pointer<Double>, Pointer<Double>, Pointer<Int8>, Pointer<Uint32>, Pointer<Int8>, Pointer<Uint32>, Size, Double, Double),
        int Function(Pointer<Double>, Pointer<Double>, Pointer<Int8>, Pointer<Uint32>, Pointer<Int8>, Pointer<Uint32>, int, double, double)>('polydim_structured_lsm_step');

    _handleCreate = _cppLib.lookupFunction<
        Pointer<PolydimHandle> Function(Size, Size),
        Pointer<PolydimHandle> Function(int, int)>('polydim_handle_create');

    final releasePtr = _cppLib.lookup<NativeFunction<Void Function(Pointer<PolydimHandle>)>>('polydim_handle_release');
    _handleRelease = releasePtr.asFunction();
    _handleFinalizer = NativeFinalizer(releasePtr.cast());

    // Bind Rust
    _bettiGuard = _rustLib.lookupFunction<
        Int32 Function(Pointer<PolydimEdge>, Uint32, Uint32, Int64, Pointer<PolydimBettiResult>),
        int Function(Pointer<PolydimEdge>, int, int, int, Pointer<PolydimBettiResult>)>('polydim_rust_betti_dual_guard');

    _frechetBetti = _rustLib.lookupFunction<
        Int32 Function(Pointer<Double>, Uint32, Uint32, Double, Int64, Pointer<Double>, Pointer<PolydimFrechetBettiResult>),
        int Function(Pointer<Double>, int, int, double, int, Pointer<Double>, Pointer<PolydimFrechetBettiResult>)>('polydim_rust_frechet_betti_filter');
  }

  /// Proyecta un tensor S^(D-1) hacia una lista Dart gestionada (Cero Memory Leaks - FFI-002)
  List<GaussianSplatData> projectLatentTo3DGS(Float64List latentVector, {int numSplats = 1000}) {
    final splats = <GaussianSplatData>[];
    final d = latentVector.length;
    if (d < 3 || numSplats <= 0) return splats;

    final Pointer<GaussianSplatPoint3D> buffer = calloc<GaussianSplatPoint3D>(numSplats);
    try {
      // Proyeccion Isométrica de Clifford (Random Projection Orthogonal Frame)
      for (int i = 0; i < numSplats; i++) {
        final idx = (i * 7) % (d - 2);
        final x = latentVector[idx];
        final y = latentVector[idx + 1];
        final z = latentVector[idx + 2];
        final norm = (x * x + y * y + z * z);
        final scale = 0.05 * (1.0 - norm).abs();

        final ptr = buffer.elementAt(i);
        ptr.ref.posX = x;
        ptr.ref.posY = y;
        ptr.ref.posZ = z;
        ptr.ref.scaleX = scale;
        ptr.ref.scaleY = scale;
        ptr.ref.scaleZ = scale;
        ptr.ref.rotW = 1.0;
        ptr.ref.rotX = 0.0;
        ptr.ref.rotY = 0.0;
        ptr.ref.rotZ = 0.0;
        ptr.ref.opacity = 0.8;
        ptr.ref.r = (x.abs() % 1.0);
        ptr.ref.g = (y.abs() % 1.0);
        ptr.ref.b = (z.abs() % 1.0);

        splats.add(GaussianSplatData(
          posX: ptr.ref.posX, posY: ptr.ref.posY, posZ: ptr.ref.posZ,
          scaleX: ptr.ref.scaleX, scaleY: ptr.ref.scaleY, scaleZ: ptr.ref.scaleZ,
          rotW: ptr.ref.rotW, rotX: ptr.ref.rotX, rotY: ptr.ref.rotY, rotZ: ptr.ref.rotZ,
          opacity: ptr.ref.opacity,
          r: ptr.ref.r, g: ptr.ref.g, b: ptr.ref.b,
        ));
      }
      return splats;
    } finally {
      calloc.free(buffer);
    }
  }

  /// Aloca buffer nativo contiguo para shaders de GPU (Impeller / Vulkan)
  Pointer<GaussianSplatPoint3D> allocateNativeSplatBuffer(int count) {
    return calloc<GaussianSplatPoint3D>(count);
  }

  /// Libera buffer nativo contiguo
  void freeNativeSplatBuffer(Pointer<GaussianSplatPoint3D> ptr) {
    calloc.free(ptr);
  }
}
