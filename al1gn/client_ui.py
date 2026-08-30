"""
AL1GN/1.0 — Client UI Layer
=============================
Everything the human-facing side of the client needs:

  Board rendering    — decode wire-format board_state, draw ASCII grids
  Move validation    — client-side pre-check before sending MOVE
  Message handler    — parse server replies, update client FSM, print feedback
  Input loop         — read user commands, validate, call send_raw()

Dependencies:
  - al1gn.client_net  (send_raw, set_alive, alive)
  - al1gn.protocol    (reply code prefixes)

No imports from session, server_core, or games.
"""

from __future__ import annotations

import socket
import threading
from typing import Callable

import al1gn.client_net as net


# ---------------------------------------------------------------------------
# Logging (shared print_lock injected from entry point)
# ---------------------------------------------------------------------------
_log_fn: Callable[[str], None] = print


def set_logger(fn: Callable[[str], None]) -> None:
    global _log_fn
    _log_fn = fn


def _log(msg: str) -> None:
    _log_fn(msg)


# ---------------------------------------------------------------------------
# Client-side session state
# ---------------------------------------------------------------------------
state: str = 'Connected'
my_name: str | None = None        # registered name — used to parse 301
my_token: str | None = None       # session token received on 201
my_symbol: str | None = None
game_type: str | None = None
my_turn: bool = False
last_board_enc: str | None = None


def _reset_game_state() -> None:
    global my_symbol, my_turn, last_board_enc
    my_symbol = None
    my_turn = False
    last_board_enc = None


# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

def _decode_board(encoded: str) -> list[list[str]]:
    return [row.split(',') for row in encoded.split('/')]


def _render_ttt(encoded: str) -> str:
    rows = _decode_board(encoded)
    lines = ["", "  Tic-Tac-Toe", "  -----------", "    0   1   2"]
    for r, row in enumerate(rows):
        lines.append(f"  {r}  " + " | ".join(row))
        if r < len(rows) - 1:
            lines.append("    ---+---+---")
    lines.append("")
    return '\n'.join(lines)


def _render_c4(encoded: str) -> str:
    rows = _decode_board(encoded)
    cols = len(rows[0]) if rows else 7
    lines = [
        "",
        "  Connect4",
        "  " + "-" * (cols * 4 - 1),
        "    " + "   ".join(str(c) for c in range(cols)),
    ]
    for r, row in enumerate(rows):
        lines.append(f"  {r}  " + " | ".join(row))
        if r < len(rows) - 1:
            lines.append("    " + "---+" * (cols - 1) + "---")
    lines.append("")
    return '\n'.join(lines)


def render_board(encoded: str) -> str:
    global game_type
    # Auto-detect game type based on row count
    if encoded.count('/') == 2:
        game_type = 'TTT'
    elif encoded.count('/') == 5:
        game_type = 'C4'

    if game_type == 'TTT':
        return _render_ttt(encoded)
    if game_type == 'C4':
        return _render_c4(encoded)
    return encoded


# ---------------------------------------------------------------------------
# Client-side move pre-validation
# ---------------------------------------------------------------------------

def validate_move(arg: str, board_enc: str) -> tuple[bool, str]:
    """Best-effort client check.  The server is still authoritative."""
    if game_type == 'TTT':
        return _validate_ttt(arg, board_enc)
    if game_type == 'C4':
        return _validate_c4(arg, board_enc)
    return True, ''


def _validate_ttt(arg: str, board_enc: str) -> tuple[bool, str]:
    parts = arg.split(',')
    if len(parts) != 2:
        return False, "Format: row,col  e.g. 1,2"
    try:
        row, col = int(parts[0]), int(parts[1])
    except ValueError:
        return False, "Row and col must be integers"
    if not (0 <= row <= 2 and 0 <= col <= 2):
        return False, "Row and col must each be 0–2"
    rows = _decode_board(board_enc)
    if rows[row][col] != '.':
        return False, f"Cell ({row},{col}) is already taken"
    return True, ''


def _validate_c4(arg: str, board_enc: str) -> tuple[bool, str]:
    try:
        col = int(arg)
    except ValueError:
        return False, "Column must be an integer"
    if not (0 <= col <= 6):
        return False, "Column must be 0–6"
    rows = _decode_board(board_enc)
    if rows[0][col] != '.':
        return False, f"Column {col} is full"
    return True, ''


# ---------------------------------------------------------------------------
# Server-message handler  (called by client_net.receive_loop)
# ---------------------------------------------------------------------------

def handle_server_message(line: str, sock: socket.socket) -> None:
    """Parse one server reply line and update client state / print feedback."""
    global state, my_name, my_token, my_symbol, my_turn, last_board_enc, game_type

    _log(f"[RECV <- SERVER] {line}")

    parts = line.split(' ', 3)
    code   = parts[0]
    phrase = parts[1] if len(parts) > 1 else ''
    data1  = parts[2] if len(parts) > 2 else ''
    data2  = parts[3] if len(parts) > 3 else ''

    # ------------------------------------------------------------------
    # Connection / registration
    # ------------------------------------------------------------------
    if code == '220':
        _log("[INFO] Connected to AL1GN server.")
        _log("[INFO] Register with:  HELO <your_name>")

    elif code == '201':
        state = 'Registered'
        # data1 is the session token
        my_token = data1
        _log(f"[INFO] Registered! Your session token: {my_token}")
        _log("[INFO] Keep this token — you will need it to reconnect as the same player.")
        _log("[INFO] Start a game:")
        _log("[INFO]   QUEUE TTT | C4   — auto-matchmaking")
        _log("[INFO]   MAKE  TTT | C4   — create private room")
        _log("[INFO]   JOIN  <code>     — join private room")

    elif code == '207':
        state = 'InGame'
        # data1 is the board_state
        last_board_enc = data1
        _log("[INFO] Session restored! Resuming your game:")
        if data1:
            _log(render_board(data1))

    elif code == '221':
        _log("[INFO] Server closed the connection.")
        net.set_alive(False)

    elif code == '433':
        _log("[WARN] Name already taken. Try:  HELO <other_name>")

    elif code == '460':
        _log("[ERROR] Bad token — name/token mismatch. Cannot reconnect as this player.")

    # ------------------------------------------------------------------
    # Matchmaking
    # ------------------------------------------------------------------
    elif code == '202':
        # "202 Room_created <code>"
        room_code = data1
        _log(f"[INFO] Room created — share this code: {room_code}")
        _log("[INFO] Waiting for opponent to join…")
        state = 'Waiting'

    elif code == '203':
        if data2:
            game_type = data2
        _log("[INFO] Joined room. Waiting for game to start…")
        state = 'Waiting'

    elif code == '300':
        state = 'Waiting'
        _log("[INFO] Waiting for an opponent…")

    # ------------------------------------------------------------------
    # 301 Game_turn <active_player_name> <board_state>
    #
    # Both players receive the same message.  The client compares
    # <active_player_name> to its own registered name (my_name) to
    # determine whether it is their turn or the opponent's.
    # ------------------------------------------------------------------
    elif code == '301':
        # parts: ['301', 'Game_turn', '<active_player_name>', '<board_state>']
        active_name = data1
        board_enc   = data2
        last_board_enc = board_enc

        it_is_my_turn = (active_name == my_name)

        if state != 'InGame':
            state = 'InGame'
            # Determine symbol: if I go first I am X (index 0)
            if it_is_my_turn:
                my_symbol = 'X'
                _log("[INFO] Game started! You are X (go first).")
            else:
                my_symbol = 'O'
                _log("[INFO] Game started! You are O (opponent goes first).")

        my_turn = it_is_my_turn
        _log(render_board(board_enc))

        if it_is_my_turn:
            _prompt_move()
        else:
            _log(f"[INFO] Waiting for {active_name}'s move…")

    # ------------------------------------------------------------------
    # Game over
    # ------------------------------------------------------------------
    elif code == '303':
        if data1:
            _log(render_board(data1))
        _log("[INFO] *** YOU WIN! Congratulations! ***")
        state = 'PostGame'
        my_turn = False
        _prompt_rematch()

    elif code == '304':
        if data1 and data1 != 'Timeout':
            _log(render_board(data1))
        _log("[INFO] *** YOU LOSE. Better luck next time! ***")
        state = 'PostGame'
        my_turn = False
        _prompt_rematch()

    elif code == '305':
        if data1:
            _log(render_board(data1))
        _log("[INFO] *** DRAW! ***")
        state = 'PostGame'
        my_turn = False
        _prompt_rematch()

    elif code == '306':
        _log("[INFO] *** Opponent forfeited. You win! ***")
        state = 'PostGame'
        my_turn = False
        _prompt_rematch()

    # ------------------------------------------------------------------
    # Disconnection / reconnect
    # ------------------------------------------------------------------
    elif code == '308':
        _log("[INFO] Opponent disconnected. Waiting for them to reconnect…")

    elif code == '200':
        extra = ' '.join(parts[1:])
        if 'reconnected' in extra.lower():
            _log(f"[INFO] {extra}")

    # ------------------------------------------------------------------
    # Rematch
    # ------------------------------------------------------------------
    elif code == '307':
        _log("[INFO] Opponent wants a rematch!")
        _log("[INFO]   ACCEPT   — play again")
        _log("[INFO]   DECLINE  — no thanks")

    elif code == '205':
        _log("[INFO] Rematch accepted! Starting new game…")
        _reset_game_state()

    elif code == '309':
        _log("[INFO] Opponent declined the rematch.")
        state = 'Registered'
        _log("[INFO] Start a new game with QUEUE / MAKE / JOIN.")

    # ------------------------------------------------------------------
    # Move feedback
    # ------------------------------------------------------------------
    elif code == '204':
        _log("[INFO] Move accepted.")

    elif code == '450':
        _log("[WARN] Not your turn!")

    elif code == '451':
        _log("[WARN] Invalid move — try again:")
        _prompt_move()

    elif code == '452':
        _log("[WARN] Game has not started yet.")

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------
    elif code == 'PING':
        net.send_raw(sock, 'PONG')

    elif code == '206':
        pass   # pong acknowledged

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------
    elif code == '400':
        _log(f"[ERROR] Bad request: {line}")
    elif code == '430':
        _log("[ERROR] Not registered — send HELO <name> first.")
    elif code == '431':
        _log("[ERROR] Room not found. Check the code and try again.")
    elif code == '432':
        _log("[ERROR] Room is full.")
    elif code == '434':
        _log("[ERROR] Unknown game type. Use TTT or C4.")
    elif code == '500':
        _log("[ERROR] Server does not recognise that command.")
    elif code == '501':
        _log(f"[ERROR] Bad parameter: {line}")
    elif code == '503':
        _log(f"[ERROR] Command out of sequence: {line}")
    elif code == '520':
        _log("[ERROR] Internal server error.")
    elif code == '521':
        _log("[ERROR] Server is shutting down.")
        net.set_alive(False)


# ---------------------------------------------------------------------------
# Input loop  (runs on the main thread)
# ---------------------------------------------------------------------------

def input_loop(sock: socket.socket) -> None:
    """Read user commands, validate locally, forward to server."""
    global state, my_name, game_type, my_turn, last_board_enc

    _log("[INFO] AL1GN Client ready. Type HELP for commands.")

    try:
        while net.alive:
            try:
                raw = input()
            except EOFError:
                break

            raw = raw.strip()
            if not raw:
                continue

            parts = raw.split(' ', 1)
            cmd = parts[0].upper()
            arg = parts[1].strip() if len(parts) > 1 else ''

            if cmd == 'HELO':
                if not arg:
                    _log("[INFO] Usage: HELO <your_name>  or  HELO <your_name> <token>")
                    continue
                helo_parts = arg.split(' ', 1)
                my_name = helo_parts[0]
                net.send_raw(sock, f"HELO {arg}")

            elif cmd == 'QUEUE':
                if not arg:
                    _log("[INFO] Usage: QUEUE TTT  or  QUEUE C4")
                    continue
                game_type = arg.upper()
                net.send_raw(sock, f"QUEUE {game_type}")

            elif cmd == 'MAKE':
                if not arg:
                    _log("[INFO] Usage: MAKE TTT  or  MAKE C4")
                    continue
                game_type = arg.upper()
                net.send_raw(sock, f"MAKE {game_type}")

            elif cmd == 'JOIN':
                if not arg:
                    _log("[INFO] Usage: JOIN <room_code>")
                    continue
                net.send_raw(sock, f"JOIN {arg.upper()}")

            elif cmd == 'MOVE':
                if state != 'InGame':
                    _log("[WARN] No game in progress.")
                    continue
                if not my_turn:
                    _log("[WARN] It's not your turn yet.")
                    continue
                if not arg:
                    _prompt_move()
                    continue
                if last_board_enc is not None:
                    ok, reason = validate_move(arg, last_board_enc)
                    if not ok:
                        _log(f"[WARN] Invalid move: {reason}")
                        _prompt_move()
                        continue
                net.send_raw(sock, f"MOVE {arg}")

            elif cmd == 'REMATCH':
                net.send_raw(sock, 'REMATCH')

            elif cmd == 'ACCEPT':
                net.send_raw(sock, 'ACCEPT')

            elif cmd == 'DECLINE':
                net.send_raw(sock, 'DECLINE')

            elif cmd == 'PONG':
                net.send_raw(sock, 'PONG')

            elif cmd == 'QUIT':
                net.send_raw(sock, 'QUIT')
                net.set_alive(False)
                break

            elif cmd == 'HELP':
                _print_help()

            else:
                _log(f"[WARN] Unknown command '{cmd}'. Type HELP.")

    except KeyboardInterrupt:
        _log("\n[INFO] Interrupted. Disconnecting…")
        try:
            net.send_raw(sock, 'QUIT')
        except Exception:
            pass
    finally:
        net.set_alive(False)


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _prompt_move() -> None:
    if game_type == 'TTT':
        _log("[INPUT] Your move — row,col  e.g. 1,2")
    elif game_type == 'C4':
        _log("[INPUT] Your move — col 0-6  e.g. 3")
    else:
        _log("[INPUT] Your move:")


def _prompt_rematch() -> None:
    _log("[INFO] Type REMATCH to play again, or QUEUE/MAKE/JOIN to start fresh.")


def _print_help() -> None:
    _log("""
[HELP] AL1GN/1.0 Commands
--------------------------
  HELO <name>              Register (first time)
  HELO <name> <token>      Reconnect using your session token
  QUEUE TTT|C4             Join auto-matchmaking queue
  MAKE  TTT|C4             Create a private room (returns a room code)
  JOIN  <code>             Join a room by its 6-character code
  MOVE  <pos>              Make a move:
                             TTT -> row,col  (e.g. MOVE 1,2)
                             C4  -> col      (e.g. MOVE 3)
  REMATCH                  Request a rematch after a game ends
  ACCEPT                   Accept opponent's rematch request
  DECLINE                  Decline opponent's rematch request
  QUIT                     Disconnect gracefully
  HELP                     Show this message
--------------------------""")
