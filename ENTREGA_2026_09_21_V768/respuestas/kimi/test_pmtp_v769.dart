import 'dart:ffi';
import 'package:ffi/ffi.dart';
import 'polydim_ffi_v769.dart';

void main() {
  print("=== RED TEAM: DART FFI PMTP SEQLOCK v769 ===");
  final p = Polydim.open(); // selftest obligatorio dentro de open()

  final numSlots = 4;
  final payloadBytes = 10000 * 8;
  final totalBytes = p.pmtpSizeof(numSlots, payloadBytes);
  final heapBuf = calloc<Uint8>(totalBytes);
  final ctrl = heapBuf.cast<PMTPControl>();

  final rcInit = p.pmtpInit(ctrl, numSlots, payloadBytes);
  assert(rcInit == 0, "pmtp_init fallo: $rcInit");

  final slotOut = calloc<Uint32>();
  final verOut = calloc<Uint64>();
  int rc = p.pmtpWriteBegin(ctrl, slotOut, verOut);
  assert(rc == 0, "write_begin fallo: $rc");
  final writeSlot = slotOut.value;
  p.pmtpWriteCommit(ctrl, writeSlot, verOut.value);

  final rdSlot = calloc<Uint32>();
  final rdVer = calloc<Uint64>();
  rc = p.pmtpReadBegin(ctrl, rdSlot, rdVer);
  assert(rc == 0, "read_begin fallo: $rc (empty/busy)");
  assert(rdSlot.value == writeSlot, "slot publicado no coincide");

  rc = p.pmtpReadValidate(ctrl, rdSlot.value, rdVer.value);
  print(rc == 0
      ? "DART PMTP v769 PASSED: contrato ABI validado contra polydim.h."
      : "DART PMTP v769 FAILED: validate rc=$rc ${statusName(rc)}");

  calloc.free(heapBuf);
  calloc.free(slotOut);
  calloc.free(verOut);
  calloc.free(rdSlot);
  calloc.free(rdVer);
}
