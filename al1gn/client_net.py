"""
AL1GN/1.0 — Client Network Layer
==================================
Handles all raw TCP I/O for the client:
  - send_raw()      — encode and transmit one command
  - receive_loop()  — background thread: buffer stream, split on CRLF,
                      dispatch each line to a handler callback

Also owns the shared 'alive' flag so both the receive loop and the input
loop can signal each other to stop.

Dependencies:
  - al1gn.protocol  (only for the CRLF wire format constant, implicitly)

No imports from client_ui, session, or server_core.
"""

from __future__ import annotations

import socket
import threading
from typing import Callable


# ---------------------------------------------------------------------------
# Shared runtime state (module-level so both net and ui layers can access)
# ---------------------------------------------------------------------------
alive: bool = True                 # cleared to stop all client threads
_alive_lock = threading.Lock()


def set_alive(value: bool) -> None:
    global alive
    with _alive_lock:
        alive = value


# ---------------------------------------------------------------------------
# Logging (injected by the entry point to share one print_lock)
# ---------------------------------------------------------------------------
_log_fn: Callable[[str], None] = print


def set_logger(fn: Callable[[str], None]) -> None:
    global _log_fn
    _log_fn = fn


def _log(msg: str) -> None:
    _log_fn(msg)


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send_raw(sock: socket.socket, message: str) -> None:
    """Encode *message* with CRLF and send it.  Logs on failure."""
    try:
        sock.sendall((message + '\r\n').encode('utf-8'))
        _log(f"[SEND -> SERVER] {message}")
    except Exception as exc:
        _log(f"[ERROR] Failed to send '{message}': {exc}")
        set_alive(False)


# ---------------------------------------------------------------------------
# Receive loop
# ---------------------------------------------------------------------------

def receive_loop(
    sock: socket.socket,
    on_message: Callable[[str, socket.socket], None],
) -> None:
    """
    Background thread body.

    Reads raw bytes from *sock*, reassembles the stream, splits on CRLF,
    and calls *on_message(line, sock)* for every complete line received.
    *on_message* is expected to be client_ui.handle_server_message.
    """
    buf = ''
    try:
        while alive:
            try:
                sock.settimeout(1.0)
                chunk = sock.recv(4096).decode('utf-8', errors='replace')
                if not chunk:
                    _log("[INFO] Server closed the connection.")
                    set_alive(False)
                    break
                buf += chunk
                while '\r\n' in buf:
                    line, buf = buf.split('\r\n', 1)
                    line = line.strip()
                    if line:
                        on_message(line, sock)
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError,
                    BrokenPipeError, OSError):
                _log("[INFO] Connection lost.")
                set_alive(False)
                break
    except Exception as exc:
        _log(f"[ERROR] Receive loop: {exc}")
        set_alive(False)
