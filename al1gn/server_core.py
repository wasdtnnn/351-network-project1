"""
AL1GN/1.0 — Server Core
========================
AL1GNServer orchestrates all server-side concerns:
  - Accepting TCP connections (one thread per client)
  - Player registration and session registry
  - Matchmaking: queue-based and room-based
  - Command dispatch (HELO / QUEUE / MAKE / JOIN / MOVE / REMATCH / …)
  - Heartbeat loop per client
  - Disconnection detection and reconnect timeout

Dependencies:
  - al1gn.protocol  (reply codes + config)
  - al1gn.session   (PlayerSession, GameSession)
  - al1gn.games     (VALID_GAME_TYPES — only for validation)

No game-specific logic lives here.
"""

from __future__ import annotations

import random
import socket
import string
import threading
import time
from typing import Optional

import al1gn.session as _session_module
from al1gn.games import VALID_GAME_TYPES
from al1gn.protocol import (
    HOST, PORT,
    HEARTBEAT_INTERVAL, PING_TIMEOUT, RECONNECT_TIMEOUT,
    MAX_NAME_LENGTH, ROOM_CODE_LENGTH,
    # 2xx
    R_OK, R_SERVICE_READY, R_SERVICE_CLOSING,
    R_SESSION_CREATED, R_SESSION_RESTORED,
    R_ROOM_CREATED, R_JOINED_ROOM,
    R_REMATCH_ACCEPTED, R_PONG,
    # 3xx
    R_WAITING, R_YOUR_TURN, R_OPP_TURN,
    R_GAME_FORFEIT,
    R_REMATCH_REQUESTED, R_OPP_DISCONNECTED, R_REMATCH_DECLINED,
    # 4xx
    R_BAD_REQUEST, R_NOT_REGISTERED,
    R_ROOM_NOT_FOUND, R_ROOM_FULL,
    R_GAME_NOT_STARTED,
    R_NAME_TAKEN, R_UNKNOWN_GAME,
    R_BAD_PARAM, R_BAD_SEQUENCE,
    # 5xx
    R_SYNTAX_ERROR,
)
from al1gn.session import GameSession, PlayerSession


# ---------------------------------------------------------------------------
# Thread-safe logger
# ---------------------------------------------------------------------------
_log_lock = threading.Lock()


def _log(msg: str) -> None:
    with _log_lock:
        print(msg)


# Wire the same logger into the session layer so GameSession log calls
# go through the same lock.
_session_module.set_logger(_log)


# ---------------------------------------------------------------------------
# AL1GNServer
# ---------------------------------------------------------------------------
class AL1GNServer:
    """
    Central server class.  Call run() to start accepting connections.
    All public state is protected by per-collection locks.
    """

    def __init__(self, host: str = HOST, port: int = PORT):
        self.host = host
        self.port = port

        # name → PlayerSession
        self._players: dict[str, PlayerSession] = {}
        self._players_lock = threading.Lock()

        # game_type → [PlayerSession, …]  (players waiting in auto-queue)
        self._queues: dict[str, list[PlayerSession]] = {
            gt: [] for gt in VALID_GAME_TYPES
        }
        self._queues_lock = threading.Lock()

        # room_code → {'game_type': str, 'creator': PlayerSession}
        self._rooms: dict[str, dict] = {}
        self._rooms_lock = threading.Lock()

    # ======================================================================
    # Public entry point
    # ======================================================================

    def run(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(10)
        _log(f"[SERVER] AL1GN/1.0 listening on {self.host}:{self.port}")
        _log(
            f"[SERVER] TURN_TIMEOUT={_session_module.TURN_TIMEOUT}s  "
            f"RECONNECT_TIMEOUT={RECONNECT_TIMEOUT}s  "
            f"HEARTBEAT_INTERVAL={HEARTBEAT_INTERVAL}s"
        )
        try:
            while True:
                conn, addr = srv.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(conn, addr),
                    daemon=True,
                ).start()
        except KeyboardInterrupt:
            _log("[SERVER] Shutting down.")
        finally:
            srv.close()

    # ======================================================================
    # Per-client lifecycle
    # ======================================================================

    def _handle_client(self, conn: socket.socket, addr: tuple) -> None:
        session = PlayerSession(conn, addr)
        _log(f"[CONNECT] New connection from {addr}")
        session.send(R_SERVICE_READY)

        # Heartbeat runs in its own daemon thread
        threading.Thread(
            target=self._heartbeat_loop,
            args=(session,),
            daemon=True,
        ).start()

        buf = ''
        try:
            while session.alive:
                try:
                    conn.settimeout(1.0)
                    chunk = conn.recv(4096).decode('utf-8', errors='replace')
                    if not chunk:
                        break
                    buf += chunk
                    while '\r\n' in buf:
                        line, buf = buf.split('\r\n', 1)
                        line = line.strip()
                        if line:
                            self._dispatch(session, line)
                except socket.timeout:
                    continue
                except (ConnectionResetError, ConnectionAbortedError,
                        BrokenPipeError, OSError):
                    break
        finally:
            if session.alive:
                self._handle_disconnect(session)
            try:
                conn.close()
            except Exception:
                pass
            _log(f"[CLOSE] Connection from {addr} closed")

    # ======================================================================
    # Heartbeat
    # ======================================================================

    def _heartbeat_loop(self, session: PlayerSession) -> None:
        while session.alive:
            time.sleep(HEARTBEAT_INTERVAL)
            if not session.alive:
                break
            session.send("PING")
            deadline = time.time() + PING_TIMEOUT
            while time.time() < deadline:
                if time.time() - session.last_pong < HEARTBEAT_INTERVAL + PING_TIMEOUT:
                    break
                time.sleep(0.5)
            if time.time() - session.last_pong > HEARTBEAT_INTERVAL + PING_TIMEOUT:
                _log(f"[HEARTBEAT] No PONG from {session.name or session.addr}")
                self._handle_disconnect(session)
                break

    # ======================================================================
    # Disconnection + reconnect timeout
    # ======================================================================

    def _handle_disconnect(self, session: PlayerSession) -> None:
        session.alive = False
        _log(f"[DISCONNECT] {session.name or session.addr}")

        game = session.game
        if game and not game.over:
            game._cancel_turn_timer()
            opponent = game.opponent_of(session)
            session.pending_game = game
            session.game = None
            opponent.send(R_OPP_DISCONNECTED)
            threading.Timer(
                RECONNECT_TIMEOUT,
                self._on_reconnect_timeout,
                args=(session, opponent, game),
            ).start()

    def _on_reconnect_timeout(
        self,
        disconnected: PlayerSession,
        opponent: PlayerSession,
        game: GameSession,
    ) -> None:
        if disconnected.alive or game.over:
            return
        game.over = True
        _log(f"[FORFEIT] {disconnected.name} did not reconnect in time")
        opponent.send(R_GAME_FORFEIT)
        opponent.state = 'PostGame'
        opponent.game = None
        disconnected.pending_game = None

    # ======================================================================
    # Registration
    # ======================================================================

    def _register_player(self, session: PlayerSession, name: str) -> str:
        """Register *name* for *session*.  Returns the reply string to send."""
        if not name or len(name) > MAX_NAME_LENGTH:
            return R_BAD_PARAM

        with self._players_lock:
            existing = self._players.get(name)
            if existing is not None:
                if existing.alive:
                    return R_NAME_TAKEN
                # Dead session — allow reconnect
                old_game = existing.pending_game or existing.game
                self._players[name] = session
                session.name = name
                session.state = 'Registered'

                if old_game and not old_game.over:
                    # Slot this session back into the game
                    idx = old_game.players.index(existing)
                    old_game.players[idx] = session
                    session.game = old_game
                    session.pending_game = None
                    session.state = 'InGame'
                    board_enc = old_game.board.encode()
                    return f"{R_SESSION_RESTORED} {board_enc}"

                return R_SESSION_CREATED

            self._players[name] = session
            session.name = name
            session.state = 'Registered'
            return R_SESSION_CREATED

    # ======================================================================
    # Matchmaking
    # ======================================================================

    def _generate_room_code(self) -> str:
        chars = string.ascii_uppercase + string.digits
        with self._rooms_lock:
            while True:
                code = ''.join(random.choices(chars, k=ROOM_CODE_LENGTH))
                if code not in self._rooms:
                    return code

    def _queue_player(self, session: PlayerSession, game_type: str) -> Optional[str]:
        """Add *session* to the auto-queue.
        Returns a reply string, or None if a match was made (match sends its own replies)."""
        if game_type not in VALID_GAME_TYPES:
            return R_UNKNOWN_GAME
        with self._queues_lock:
            queue = self._queues[game_type]
            for waiting in queue:
                if waiting is not session and waiting.alive and waiting.state == 'Waiting':
                    queue.remove(waiting)
                    self._start_game(game_type, waiting, session)
                    return None          # _start_game already notified both
            queue.append(session)
        session.state = 'Waiting'
        return R_WAITING

    def _make_room(self, session: PlayerSession, game_type: str) -> str:
        if game_type not in VALID_GAME_TYPES:
            return R_UNKNOWN_GAME
        code = self._generate_room_code()
        with self._rooms_lock:
            self._rooms[code] = {'game_type': game_type, 'creator': session}
        session.state = 'Waiting'
        return f"{R_ROOM_CREATED} {code}"

    def _join_room(self, session: PlayerSession, code: str) -> Optional[str]:
        """Join a room by code.
        Returns a reply string on error, or None on success (sends its own replies)."""
        with self._rooms_lock:
            room = self._rooms.get(code)
            if not room:
                return R_ROOM_NOT_FOUND
            creator: PlayerSession = room['creator']
            if creator is session:
                return R_BAD_REQUEST
            if creator.state != 'Waiting':
                return R_ROOM_FULL
            game_type = room['game_type']
            del self._rooms[code]

        session.send(f"{R_JOINED_ROOM} {code}")
        self._start_game(game_type, creator, session)
        return None

    def _start_game(
        self, game_type: str, p1: PlayerSession, p2: PlayerSession
    ) -> None:
        """Wire up a GameSession and notify both players."""
        game = GameSession(
            game_type, p1, p2,
            on_game_end=self._on_game_end,
        )
        p1.game = game
        p2.game = game
        p1.state = 'InGame'
        p2.state = 'InGame'
        p1.rematch_requested = False
        p2.rematch_requested = False
        board_enc = game.board.encode()
        _log(f"[MATCH] {p1.name} vs {p2.name} — {game_type}")
        p1.send(f"{R_YOUR_TURN} {board_enc}")
        p2.send(f"{R_OPP_TURN} {board_enc}")

    def _on_game_end(
        self,
        winner: Optional[PlayerSession],
        loser: Optional[PlayerSession],
        outcome: str,
    ) -> None:
        """Callback fired by GameSession._finish() after a game concludes."""
        # PlayerSession.state and record_game_end() are already handled inside
        # GameSession._finish().  Nothing extra needed here for now, but
        # keeping the hook lets subclasses log stats, persist scores, etc.
        pass

    # ======================================================================
    # Command dispatcher
    # ======================================================================

    def _dispatch(self, session: PlayerSession, line: str) -> None:
        parts = line.strip().split(' ', 1)
        cmd = parts[0].upper()
        arg = parts[1].strip() if len(parts) > 1 else ''

        _log(f"[RECV ← {session.name or session.addr}] {line.strip()}")

        # ------------------------------------------------------------------
        # Commands valid in any state
        # ------------------------------------------------------------------
        if cmd == 'QUIT':
            session.send(R_SERVICE_CLOSING)
            session.alive = False
            return

        if cmd == 'PONG':
            session.last_pong = time.time()
            session.send(R_PONG)
            return

        # ------------------------------------------------------------------
        # HELO — must be the first real command
        # ------------------------------------------------------------------
        if cmd == 'HELO':
            if not arg:
                session.send(R_BAD_PARAM)
                return
            reply = self._register_player(session, arg)
            session.send(reply)
            # If this was a reconnect into an active game, push turn state
            if reply.startswith('201') and session.state == 'InGame':
                game = session.game
                board_enc = game.board.encode()
                if game.current_player() is session:
                    session.send(f"{R_YOUR_TURN} {board_enc}")
                else:
                    session.send(f"{R_OPP_TURN} {board_enc}")
                game.opponent_of(session).send("200 Opponent reconnected")
                game._start_turn_timer()
            return

        # ------------------------------------------------------------------
        # All remaining commands require registration
        # ------------------------------------------------------------------
        if session.state == 'Connected':
            session.send(R_NOT_REGISTERED)
            return

        # ------------------------------------------------------------------
        # QUEUE
        # ------------------------------------------------------------------
        if cmd == 'QUEUE':
            if session.state not in ('Registered', 'PostGame'):
                session.send(R_BAD_SEQUENCE)
                return
            reply = self._queue_player(session, arg.upper())
            if reply:
                session.send(reply)
            return

        # ------------------------------------------------------------------
        # MAKE
        # ------------------------------------------------------------------
        if cmd == 'MAKE':
            if session.state not in ('Registered', 'PostGame'):
                session.send(R_BAD_SEQUENCE)
                return
            session.send(self._make_room(session, arg.upper()))
            return

        # ------------------------------------------------------------------
        # JOIN
        # ------------------------------------------------------------------
        if cmd == 'JOIN':
            if session.state not in ('Registered', 'PostGame'):
                session.send(R_BAD_SEQUENCE)
                return
            if not arg:
                session.send(R_BAD_PARAM)
                return
            reply = self._join_room(session, arg.upper())
            if reply:
                session.send(reply)
            return

        # ------------------------------------------------------------------
        # MOVE
        # ------------------------------------------------------------------
        if cmd == 'MOVE':
            if session.state != 'InGame' or session.game is None:
                session.send(
                    R_GAME_NOT_STARTED
                    if session.state in ('Registered', 'PostGame', 'Waiting')
                    else R_BAD_SEQUENCE
                )
                return
            if not arg:
                session.send(R_BAD_PARAM)
                return
            success, result = session.game.apply_move(session, arg)
            if not success:
                session.send(result)
            return

        # ------------------------------------------------------------------
        # REMATCH
        # ------------------------------------------------------------------
        if cmd == 'REMATCH':
            if session.state != 'PostGame':
                session.send(R_BAD_SEQUENCE)
                return
            session.rematch_requested = True
            session.send(R_OK)
            opp = session.last_opponent
            if opp and opp.alive:
                opp.send(R_REMATCH_REQUESTED)
            return

        # ------------------------------------------------------------------
        # ACCEPT
        # ------------------------------------------------------------------
        if cmd == 'ACCEPT':
            if session.state != 'PostGame':
                session.send(R_BAD_SEQUENCE)
                return
            opp = session.last_opponent
            gt = session.last_game_type
            if not opp or not gt or not opp.rematch_requested:
                session.send(R_BAD_SEQUENCE)
                return
            session.rematch_requested = False
            opp.rematch_requested = False
            session.send(R_REMATCH_ACCEPTED)
            opp.send(R_REMATCH_ACCEPTED)
            self._start_game(gt, opp, session)
            return

        # ------------------------------------------------------------------
        # DECLINE
        # ------------------------------------------------------------------
        if cmd == 'DECLINE':
            if session.state != 'PostGame':
                session.send(R_BAD_SEQUENCE)
                return
            session.send(R_OK)
            opp = session.last_opponent
            if opp and opp.alive:
                opp.send(R_REMATCH_DECLINED)
            session.state = 'Registered'
            session.rematch_requested = False
            if opp:
                opp.state = 'Registered'
                opp.rematch_requested = False
            return

        # ------------------------------------------------------------------
        # Unknown command
        # ------------------------------------------------------------------
        session.send(R_SYNTAX_ERROR)
