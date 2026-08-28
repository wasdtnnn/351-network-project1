"""
AL1GN/1.0 — Client entry point
================================
Run with:
    python client.py [host] [port]
    Defaults: 127.0.0.1 25146
"""

import socket
import sys
import threading

from al1gn.protocol import PORT

# Shared print lock — injected into both client layers so output never interleaves
_print_lock = threading.Lock()


def _log(msg: str) -> None:
    with _print_lock:
        print(msg)


# Wire the shared logger before importing the layers that use it
import al1gn.client_net as net
import al1gn.client_ui as ui

net.set_logger(_log)
ui.set_logger(_log)

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = PORT

if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT

    _log(f"[INFO] Connecting to {host}:{port} …")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
    except ConnectionRefusedError:
        _log(f"[ERROR] Could not connect to {host}:{port}. Is the server running?")
        sys.exit(1)

    _log("[INFO] Connected. Type HELP for available commands.")

    # Receive loop runs as a background daemon thread
    recv_thread = threading.Thread(
        target=net.receive_loop,
        args=(sock, ui.handle_server_message),
        daemon=True,
    )
    recv_thread.start()

    # Input loop runs on the main thread
    ui.input_loop(sock)

    try:
        sock.close()
    except Exception:
        pass

    _log("[INFO] Disconnected. Goodbye!")
