// ============================================================================
// POLYDIM V769 — puente FFI Dart (parche Red Team)
//   C1: PMTPControl era de 1 byte vs 64 bytes en C -> ABI roto. Corregido.
//   C2: nombres de simbolos inexistentes (begin_write vs write_begin). Corregido.
//   C3: aridad incorrecta en init/begin/commit/read. Corregido contra polydim.h.
//   C4: faltaban ALLOC(-13) e INTERNAL(-14) en el mapa de estados. Agregados.
// ============================================================================
import 'dart:ffi';
import 'dart:io' show Platform, Directory;
import 'package:ffi/ffi.dart' show calloc, Array;

const int polydimSuccess = 0;
const Map<int, String> polydimStatus = {
  0: 'SUCCESS',
  -1: 'NULL_POINTER',
  -2: 'INVALID_DIMENSION',
  -3: 'NAN_OR_INF',
  -4: 'DEGENERATE_NORM',
  -5: 'NUMERICAL_INSTABILITY',
  -6: 'SEQLOCK_RACE',
  -7: 'BUFFER_OVERFLOW',
  -8: 'INVALID_SCALAR',
  -9: 'BASIS_NOT_ORTHONORMAL',
  -10: 'POINT_OFF_MANIFOLD',
  -11: 'ALIASED_BUFFERS',
  -12: 'COMPENSATION_BROKEN',
  -13: 'ALLOC_FAILED',
  -14: 'INTERNAL_EXCEPTION',
  -15: 'SUBNORMAL_DETECTED',
};

String statusName(int rc) => polydimStatus[rc] ?? 'DESCONOCIDO($rc)';

class PolydimException implements Exception {
  final int code;
  final String op;
  PolydimException(this.op, this.code);
  @override
  String toString() => 'PolydimException: $op -> ${statusName(code)} ($code)';
}

final class PolydimTolerances extends Struct {
  @Double() external double basisOrtho;
  @Double() external double pointNorm;
  @Double() external double gramOrtho;
  @Double() external double pivotRel;
  @Int32() external int rejectSubnormal;
}

final class PolydimReport extends Struct {
  @Double() external double pointNormErr;
  @Double() external double basisUuErr;
  @Double() external double basisVvErr;
  @Double() external double basisUvErr;
  @Double() external double outNormErr;
  @Double() external double pivotMin;
  @Double() external double pivotThreshold;
  @Double() external double orthoErr;
  @Uint64() external int threadsUsed;
}

// --- PMTP: layout EXACTO de kernel_cpp_v768.cpp (alignas(64)) ---
// magic(u32) num_slots(u32) payload_bytes(u64) pub_seq(u64)
// pub_slot(u32) wlock(u32) wticket(u32) reserved[28]  => 64 bytes
final class PMTPControl extends Struct {
  @Uint32() external int magic;
  @Uint32() external int numSlots;
  @Uint64() external int payloadBytes;
  @Uint64() external int pubSeq;
  @Uint32() external int pubSlot;
  @Uint32() external int wlock;
  @Uint32() external int wticket;
  @Array(28) external Array<Uint8> reserved;
}

final class PMTPSlotHeader extends Struct {
  @Uint64() external int seq;
  @Array(56) external Array<Uint8> reserved;
}

// --- firmas EXACTAS de polydim.h ---
typedef _RodriguesNative = Int32 Function(
    Pointer<Double>, Pointer<Double>, Pointer<Double>, Pointer<Double>,
    Double, Uint64, Pointer<PolydimTolerances>, Pointer<PolydimReport>);
typedef _RodriguesDart = int Function(
    Pointer<Double>, Pointer<Double>, Pointer<Double>, Pointer<Double>,
    double, int, Pointer<PolydimTolerances>, Pointer<PolydimReport>);

typedef _ProjectNative = Int32 Function(
    Pointer<Double>, Pointer<Double>, Uint64, Pointer<PolydimReport>);
typedef _ProjectDart = int Function(
    Pointer<Double>, Pointer<Double>, int, Pointer<PolydimReport>);

typedef _SelftestNative = Int32 Function();
typedef _SelftestDart = int Function();
typedef _InfoNative = Pointer<Uint8> Function();
typedef _InfoDart = Pointer<Uint8> Function();

typedef _PmtpSizeofNative = Uint64 Function(Uint32, Uint64);
typedef _PmtpSizeofDart = int Function(int, int);
typedef _PmtpInitNative = Int32 Function(Pointer<PMTPControl>, Uint32, Uint64);
typedef _PmtpInitDart = int Function(Pointer<PMTPControl>, int, int);
typedef _PmtpWriteBeginNative = Int32 Function(
    Pointer<PMTPControl>, Pointer<Uint32>, Pointer<Uint64>);
typedef _PmtpWriteBeginDart = int Function(
    Pointer<PMTPControl>, Pointer<Uint32>, Pointer<Uint64>);
typedef _PmtpCommitNative = Void Function(Pointer<PMTPControl>, Uint32, Uint64);
typedef _PmtpCommitDart = void Function(Pointer<PMTPControl>, int, int);
typedef _PmtpReadBeginNative = Int32 Function(
    Pointer<PMTPControl>, Pointer<Uint32>, Pointer<Uint64>);
typedef _PmtpReadBeginDart = int Function(
    Pointer<PMTPControl>, Pointer<Uint32>, Pointer<Uint64>);
typedef _PmtpValidateNative = Int32 Function(Pointer<PMTPControl>, Uint32, Uint64);
typedef _PmtpValidateDart = int Function(Pointer<PMTPControl>, int, int);

class Polydim {
  final DynamicLibrary _lib;
  late final _RodriguesDart _rodrigues;
  late final _ProjectDart _projectSphere;
  late final _SelftestDart _selftestAll;
  late final _InfoDart _buildInfo;
  late final _PmtpSizeofDart _pmtpSizeof;
  late final _PmtpInitDart _pmtpInit;
  late final _PmtpWriteBeginDart _pmtpWriteBegin;
  late final _PmtpCommitDart _pmtpWriteCommit;
  late final _PmtpReadBeginDart _pmtpReadBegin;
  late final _PmtpValidateDart _pmtpReadValidate;

  Polydim._(this._lib) {
    _rodrigues = _lib.lookupFunction<_RodriguesNative, _RodriguesDart>(
        'polydim_rodrigues_geodesic_f64');
    _projectSphere = _lib.lookupFunction<_ProjectNative, _ProjectDart>(
        'polydim_project_sphere_f64');
    _selftestAll =
        _lib.lookupFunction<_SelftestNative, _SelftestDart>('polydim_selftest_all');
    _buildInfo = _lib.lookupFunction<_InfoNative, _InfoDart>('polydim_build_info');
    // C2: nombres reales exportados por kernel_cpp_v768.cpp
    _pmtpSizeof = _lib.lookupFunction<_PmtpSizeofNative, _PmtpSizeofDart>(
        'polydim_pmtp_sizeof');
    _pmtpInit = _lib.lookupFunction<_PmtpInitNative, _PmtpInitDart>(
        'polydim_pmtp_init');
    _pmtpWriteBegin = _lib.lookupFunction<_PmtpWriteBeginNative, _PmtpWriteBeginDart>(
        'polydim_pmtp_write_begin');
    _pmtpWriteCommit = _lib.lookupFunction<_PmtpCommitNative, _PmtpCommitDart>(
        'polydim_pmtp_write_commit');
    _pmtpReadBegin = _lib.lookupFunction<_PmtpReadBeginNative, _PmtpReadBeginDart>(
        'polydim_pmtp_read_begin');
    _pmtpReadValidate =
        _lib.lookupFunction<_PmtpValidateNative, _PmtpValidateDart>(
            'polydim_pmtp_read_validate');
  }

  static Polydim open({String? path, bool runSelftest = true}) {
    final name = path ??
        (Platform.isWindows
            ? 'polydim.dll'
            : Platform.isMacOS
                ? 'libpolydim.dylib'
                : 'libpolydim.so');
    final cwd = Directory.current.path;
    DynamicLibrary? lib;
    final errors = <String>[];
    for (final c in [name, './$name', '$cwd/$name', '$cwd/build/$name']) {
      try {
        lib = DynamicLibrary.open(c);
        break;
      } on ArgumentError catch (e) {
        errors.add('$c: $e');
      }
    }
    if (lib == null) throw StateError('No se pudo abrir $name.\n${errors.join('\n')}');
    final p = Polydim._(lib);
    if (runSelftest) {
      final rc = p._selftestAll();
      if (rc != polydimSuccess) throw PolydimException('selftest_all', rc);
    }
    return p;
  }

  String get buildInfo {
    final ptr = _buildInfo();
    final bytes = <int>[];
    for (var i = 0; ptr[i] != 0; i++) bytes.add(ptr[i]);
    return String.fromCharCodes(bytes);
  }

  int pmtpSizeof(int numSlots, int payloadBytes) =>
      _pmtpSizeof(numSlots, payloadBytes);
  int pmtpInit(Pointer<PMTPControl> ctrl, int numSlots, int payloadBytes) =>
      _pmtpInit(ctrl, numSlots, payloadBytes);
  int pmtpWriteBegin(Pointer<PMTPControl> ctrl, Pointer<Uint32> slot,
          Pointer<Uint64> ver) =>
      _pmtpWriteBegin(ctrl, slot, ver);
  void pmtpWriteCommit(Pointer<PMTPControl> ctrl, int slot, int ver) =>
      _pmtpWriteCommit(ctrl, slot, ver);
  int pmtpReadBegin(Pointer<PMTPControl> ctrl, Pointer<Uint32> slot,
          Pointer<Uint64> ver) =>
      _pmtpReadBegin(ctrl, slot, ver);
  int pmtpReadValidate(Pointer<PMTPControl> ctrl, int slot, int ver) =>
      _pmtpReadValidate(ctrl, slot, ver);
}
