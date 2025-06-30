"""TCP chat server with adaptive Huffman compression.

Usage:
    $ python -m chat_huffman_py.server [PORT]

The server prints all received messages after decoding and rebroadcasts the
compressed payload (length-prefixed) to every other connected client.
"""

from __future__ import annotations

import socket
import struct
import threading
from pathlib import Path
from typing import List

from .encoder import AdaptiveHuffman

DEFAULT_PORT = 9000
MAX_PAYLOAD = 1_000_000  # 1 MB max safety limit


def broadcast(clients: List[socket.socket], payload: bytes, sender: socket.socket, lock: threading.Lock) -> None:
    length_prefix = struct.pack("!I", len(payload))
    with lock:
        dead: List[socket.socket] = []
        for client in clients:
            if client is sender:
                continue
            try:
                client.sendall(length_prefix + payload)
            except OSError:
                dead.append(client)
        for d in dead:
            clients.remove(d)
            d.close()


def client_thread(conn: socket.socket, addr: tuple[str, int], clients: List[socket.socket], lock: threading.Lock) -> None:
    decoder = AdaptiveHuffman()
    try:
        while True:
            # Read 4-byte big-endian length prefix
            length_raw = conn.recv(4)
            if not length_raw:
                break  # disconnected
            if len(length_raw) < 4:
                # socket closed mid-prefix
                break
            (length,) = struct.unpack("!I", length_raw)
            if length == 0 or length > MAX_PAYLOAD:
                break
            payload = b""
            while len(payload) < length:
                chunk = conn.recv(length - len(payload))
                if not chunk:
                    raise ConnectionError("Unexpected disconnect while receiving payload")
                payload += chunk
            # Decode and print
            try:
                message = decoder.decode(payload)
                print(f"[{addr[0]}:{addr[1]}] {message}")
            except Exception as exc:  # noqa: BLE001
                print(f"Decode error from {addr}: {exc}")
                continue
            # Broadcast raw payload
            broadcast(clients, payload, conn, lock)
    except (OSError, ConnectionError):
        pass
    finally:
        with lock:
            if conn in clients:
                clients.remove(conn)
        conn.close()
        print(f"Client {addr} disconnected")


def run_server(port: int = DEFAULT_PORT) -> None:
    clients: List[socket.socket] = []
    clients_lock = threading.Lock()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("", port))
        server_sock.listen()
        print(f"Server listening on port {port}…")
        try:
            while True:
                conn, addr = server_sock.accept()
                with clients_lock:
                    clients.append(conn)
                print(f"New client: {addr[0]}:{addr[1]}")
                threading.Thread(
                    target=client_thread,
                    args=(conn, addr, clients, clients_lock),
                    daemon=True,
                ).start()
        except KeyboardInterrupt:
            print("Shutting down server…")

        # Gracefully close all clients
        with clients_lock:
            for c in clients:
                c.close()


if __name__ == "__main__":
    import sys

    port_arg = int(sys.argv[1]) if len(sys.argv) >= 2 else DEFAULT_PORT
    run_server(port_arg) 