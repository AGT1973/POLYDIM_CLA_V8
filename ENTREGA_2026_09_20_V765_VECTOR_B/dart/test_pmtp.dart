import 'dart:ffi';
import 'package:ffi/ffi.dart';
import 'polydim_ffi.dart';

void main() {
  print("=== SABUESO RED TEAM: DART FFI PMTP TRIPLE BUFFER ===");
  final p = Polydim.open(path: r'..\build\libpolydim.dll');
  
  final ctrl = calloc<PMTPControl>();
  
  print("Inicializando PMTP...");
  p.pmtpInit(ctrl);
  
  print("Escribiendo TENSOR_READY (Simulado)...");
  final slotOut = calloc<Uint64>();
  int rc = p.pmtpBeginWrite(ctrl, slotOut);
  if (rc != 0) throw Exception("Begin Write Failed");
  int writeSlot = slotOut.value;
  print("Escribiendo en el slot: $writeSlot");
  
  rc = p.pmtpCommitWrite(ctrl, writeSlot);
  if (rc != 0) throw Exception("Commit Write Failed");
  
  print("Leyendo Buffer...");
  final observedSeq = calloc<Uint64>();
  observedSeq.value = 0;
  final readSlotOut = calloc<Uint64>();
  final ticketOut = calloc<Uint64>();
  
  int hasNew = p.pmtpAcquireRead(ctrl, observedSeq, readSlotOut, ticketOut);
  
  print("Novedad detectada: $hasNew");
  print("Buffer Seguro Asignado (Slot): ${readSlotOut.value}");
  
  if (hasNew == 1 && readSlotOut.value == writeSlot) {
    rc = p.pmtpValidateRead(ctrl, readSlotOut.value, ticketOut.value);
    if (rc == 0) {
      print("DART PMTP TEST PASSED: Zero-Copy Bridge Operativo.");
    } else {
      print("DART PMTP TEST FAILED: Validate Read failed with rc = $rc");
    }
  } else {
    print("DART PMTP TEST FAILED.");
  }
  
  calloc.free(ctrl);
  calloc.free(slotOut);
  calloc.free(observedSeq);
  calloc.free(readSlotOut);
  calloc.free(ticketOut);
}
