import 'dart:ffi';
import 'dart:typed_data';
import 'package:ffi/ffi.dart';

/// =========================================================================
/// POLYDIM V812 DART FFI & 3D GAUSSIAN SPLATTING TERMINAL BRIDGE
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

/// 2. Gaussian Splatting 3D Struct (Render Output)
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

/// 3. Polydim V812 Client Wrapper
class PolydimV812 {
  late final DynamicLibrary _cppLib;
  late final DynamicLibrary _rustLib;
  late final NativeFinalizer _handleFinalizer;

  // C++ Functions
  late final int Function(Pointer<Double>, int, int, Pointer<Double>, int) _gramDsyrk;
  late final int Function(Pointer<Double>, Pointer<Double>, Pointer<Double>, int, double, double) _structuredLsm;
  late final Pointer<PolydimHandle> Function(int, int) _handleCreate;
  late final void Function(Pointer<PolydimHandle>) _handleRelease;

  // Rust Functions
  late final int Function(Pointer<PolydimEdge>, int, int, int, Pointer<PolydimBettiResult>) _bettiGuard;
  late final int Function(Pointer<Double>, int, int, double, int, Pointer<Double>, Pointer<PolydimFrechetBettiResult>) _frechetBetti;

  PolydimV812({required String cppDllPath, required String rustDllPath}) {
    _cppLib = DynamicLibrary.open(cppDllPath);
    _rustLib = DynamicLibrary.open(rustDllPath);

    // Bind C++
    _gramDsyrk = _cppLib.lookupFunction<
        Int32 Function(Pointer<Double>, Size, Size, Pointer<Double>, Uint32),
        int Function(Pointer<Double>, int, int, Pointer<Double>, int)>('polydim_gram_dsyrk');

    _structuredLsm = _cppLib.lookupFunction<
        Int32 Function(Pointer<Double>, Pointer<Double>, Pointer<Double>, Size, Double, Double),
        int Function(Pointer<Double>, Pointer<Double>, Pointer<Double>, int, double, double)>('polydim_structured_lsm_step');

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

  /// Proyecta un tensor S^(D-1) de dimension D hacia una nube de gaussianas 3D
  List<GaussianSplatPoint3D> projectLatentTo3DGS(Float64List latentVector, {int numSplats = 1000}) {
    final splats = <GaussianSplatPoint3D>[];
    final d = latentVector.length;
    if (d < 3) return splats;

    // Proyeccion Isométrica de Clifford (Random Projection Orthogonal Frame)
    for (int i = 0; i < numSplats; i++) {
      final idx = (i * 7) % (d - 2);
      final x = latentVector[idx];
      final y = latentVector[idx + 1];
      final z = latentVector[idx + 2];
      final norm = (x * x + y * y + z * z);

      // Instanciar punto de gaussiana 3D
      final ptr = calloc<GaussianSplatPoint3D>();
      ptr.ref.posX = x.toDouble();
      ptr.ref.posY = y.toDouble();
      ptr.ref.posZ = z.toDouble();
      ptr.ref.scaleX = (0.05 * (1.0 - norm).abs()).toDouble();
      ptr.ref.scaleY = (0.05 * (1.0 - norm).abs()).toDouble();
      ptr.ref.scaleZ = (0.05 * (1.0 - norm).abs()).toDouble();
      ptr.ref.rotW = 1.0;
      ptr.ref.rotX = 0.0;
      ptr.ref.rotY = 0.0;
      ptr.ref.rotZ = 0.0;
      ptr.ref.opacity = 0.8;
      ptr.ref.r = ((x.abs() % 1.0)).toDouble();
      ptr.ref.g = ((y.abs() % 1.0)).toDouble();
      ptr.ref.b = ((z.abs() % 1.0)).toDouble();

      splats.add(ptr.ref);
    }
    return splats;
  }
}
