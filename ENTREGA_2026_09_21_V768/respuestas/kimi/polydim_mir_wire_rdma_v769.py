# ============================================================================
# POLYDIM v769 - MIR-WIRE RDMA EMULATOR (TCP)
#   C1: recv() no garantiza entrega completa en TCP. Frame valido con header
#       partido en 2 segmentos era descartado; ACK partido daba falso negativo.
#       Fix: _recv_exact en bucle, en header, payload y ACK.
#   C2: accept secuencial serializaba conexiones. Un hilo por conexion.
# ============================================================================
import socket, struct, threading, time
import numpy as np

PORT = 19876
HEADER_STRUCT = "!IIQ"
MAGIC_RDMA = 0x504D5450


def _recv_exact(conn, n):
    # C1: TCP entrega un stream, no mensajes.
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("stream cerrado a medio mensaje")
        buf += chunk
    return bytes(buf)


class MirWireRdmaEndpointV769:
    def __init__(self, host="127.0.0.1", port=PORT):
        self.host, self.port = host, port
        self.is_running = False
        self.server_sock = None
        self.received_tensors = []

    def start_receiver(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(16)
        self.is_running = True
        self.rx_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.rx_thread.start()

    def _accept_loop(self):
        while self.is_running:
            try:
                conn, _ = self.server_sock.accept()
            except OSError:
                break
            # C2: hilo por conexion => transferencias concurrentes
            threading.Thread(target=self._handle_conn, args=(conn,),
                             daemon=True).start()

    def _handle_conn(self, conn):
        try:
            raw = _recv_exact(conn, struct.calcsize(HEADER_STRUCT))   # C1
            magic, imm_data, tensor_bytes = struct.unpack(HEADER_STRUCT, raw)
            if magic != MAGIC_RDMA:
                return
            payload = _recv_exact(conn, tensor_bytes)                 # C1
            tensor = np.frombuffer(payload, dtype=np.float64).copy()
            self.received_tensors.append((imm_data, tensor))
            conn.sendall(b"ACK")
        except (ConnectionError, OSError):
            pass
        finally:
            conn.close()

    def rdma_write_with_imm(self, tensor, imm_data):
        t0 = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        sock.sendall(struct.pack(HEADER_STRUCT, MAGIC_RDMA, imm_data,
                                 tensor.nbytes))
        sock.sendall(memoryview(tensor))
        if _recv_exact(sock, 3) != b"ACK":                            # C1
            raise ConnectionError("ACK corrupto")
        sock.close()
        return (time.perf_counter() - t0) * 1000.0

    def stop(self):
        self.is_running = False
        if self.server_sock:
            self.server_sock.close()
