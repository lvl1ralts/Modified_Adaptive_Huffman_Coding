"""TCP chat client with adaptive Huffman compression.

Usage:
    $ python -m chat_huffman_py.client <HOST> [PORT] [USERNAME]

The client connects to the chat server, starts a receive thread that decodes
incoming messages, and allows the user to input messages from stdin.
"""

from __future__ import annotations

import socket
import struct
import sys
import threading
from typing import Optional

from .encoder import AdaptiveHuffman

DEFAULT_PORT = 9000


def receive_loop(sock: socket.socket, decoder: AdaptiveHuffman) -> None:
    try:
        while True:
            prefix = sock.recv(4)
            if not prefix:
                print("Server closed connection.")
                break
            if len(prefix) < 4:
                print("Incomplete length prefix from server.")
                break
            (length,) = struct.unpack("!I", prefix)
            payload = b""
            while len(payload) < length:
                chunk = sock.recv(length - len(payload))
                if not chunk:
                    print("Server closed connection.")
                    return
                payload += chunk
            try:
                message = decoder.decode(payload)
                print(f"\r[IN] {message}\n> ", end="", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"\rDecode error: {exc}\n> ", end="", flush=True)
    finally:
        sock.close()
        sys.exit(0)


def run_client(host: str, port: int, username: str) -> None:
    encoder = AdaptiveHuffman()
    decoder = AdaptiveHuffman()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.connect((host, port))
        except OSError as exc:
            print(f"Connection failed: {exc}")
            return

        threading.Thread(target=receive_loop, args=(sock, decoder), daemon=True).start()
        print("Connected – type messages and press Enter to send. Ctrl+C to quit.")
        try:
            while True:
                try:
                    line = input(" > ")
                except EOFError:
                    break
                if not line:
                    continue
                full_message = f"{username}: {line}"
                payload = encoder.encode(full_message)
                prefix = struct.pack("!I", len(payload))
                try:
                    sock.sendall(prefix + payload)
                except OSError:
                    print("Disconnected from server.")
                    break
        except KeyboardInterrupt:
            pass
        finally:
            sock.close()
            print("Bye.")


if __name__ == "__main__":
    host_arg = sys.argv[1] if len(sys.argv) >= 2 else "127.0.0.1"
    port_arg = int(sys.argv[2]) if len(sys.argv) >= 3 else DEFAULT_PORT
    username_arg: str = sys.argv[3] if len(sys.argv) >= 4 else "anon"
    run_client(host_arg, port_arg, username_arg) 