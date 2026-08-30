"""
AL1GN/1.0 — Session Layer
==========================
PlayerSession  — one connected client: socket wrapper + FSM state.
GameSession    — one active game between two PlayerSessions.

Dependencies:
  - al1gn.protocol  (reply codes + config constants)
  - al1gn.games     (get_board factory)

No imports from server_core, client_net, or client_ui.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Optional, Callable

from al1gn.protocol import (
    TURN_TIMEOUT,
    R_MOVE_ACCEPTED,
    R_GAME_TURN,
    R_GAME_WIN, R_GAME_LOSS, R_GAME_DRAW, R_GAME_FORFEIT,
    R_NOT_YOUR_TURN, R_INVALID_MOVE, R_GAME_NOT_STARTED, R_BAD_PARAM,
)
from al1gn.games import get_board


# ---------------------------------------------------------------------------
# Thread-safe logger (injected at startup by server_core)
# ---------------------------------------------------------------------------
_log_fn: Callable[[str], None] = print


def set_logger(fn: Callable[[str], None]) -> None:
    global _log_fn
    _log_fn = fn


def _log(msg: str) -> None:
    _log_fn(msg)


# ---------------------------------------------------------------------------
# PlayerSession
# ---------------------------------------------------------------------------
class PlayerSession:
    """
    Represents one connected TCP client.

    State machine:
        Connected -> Registered -> Waiting -> InGame -> PostGame | Registered  (after decline/new game)
    """

    def __init__(self, conn: socket.socket, addr: tuple):
        self.conn = conn
        self.addr = addr
        self.name: Optional[str] = None
        self.token: Optional[str] = None   # session token issued on first HELO

        # Protocol FSM state
        self.state: str = 'Connected'

        # Active game reference (set by AL1GNServer._start_game, cleared on game end)
        self.game: Optional[GameSession] = None

        # Held across a disconnect so reconnect can resume
        self.pending_game: Optional[GameSession] = None

        # Post-game rematch bookkeeping
        self.last_opponent: Optional[PlayerSession] = None
        self.last_game_type: Optional[str] = None
        self.rematch_requested: bool = False

        # Networking
        self._send_lock = threading.Lock()
        self.last_pong: float = time.time()
        self.alive: bool = True

    # ------------------------------------------------------------------
    # Networking
    # ------------------------------------------------------------------

    def send(self, message: str) -> None:
        """Thread-safe send.  Marks the session dead on any socket error."""
        try:
            with self._send_lock:
                self.conn.sendall((message + '\r\n').encode('utf-8'))
                _log(f"[SEND -> {self.name or self.addr}] {message}")
        except Exception:
            self.alive = False

    # ------------------------------------------------------------------
    # Post-game helpers
    # ------------------------------------------------------------------

    def record_game_end(self, opponent: PlayerSession, game_type: str) -> None:
        """Called when the game finishes so REMATCH/ACCEPT/DECLINE can work."""
        self.last_opponent = opponent
        self.last_game_type = game_type
        self.game = None


# ---------------------------------------------------------------------------
# GameSession
# ---------------------------------------------------------------------------
class GameSession:
    """
    Manages one active game between two PlayerSessions.

    The session is intentionally not aware of AL1GNServer.  When a game ends
    (win, draw, or turn-timeout) it:
      1. Sends the appropriate reply codes to both players directly via
         PlayerSession.send().
      2. Calls the injected `on_game_end` callback so AL1GNServer can do any
         post-game housekeeping (setting state, wiring last_opponent, etc.).

    Move validation
    ---------------
    The protocol delegates move validity entirely to the game implementation
    (the board class).  GameSession calls board.is_valid_move() which may be
    game-specific.  The protocol itself only defines that an invalid move
    results in reply code 451.  What constitutes "invalid" is left to the
    protocol adopter's board implementation — AL1GN imposes no rules.

    Constructor parameters
    ----------------------
    game_type   : 'TTT' | 'C4' (or any type registered by the adopter)
    player1     : goes first, plays 'X'
    player2     : goes second, plays 'O'
    on_game_end : callable(winner, loser, outcome) where outcome is
                  'win' | 'draw' | 'forfeit'.  Pass None for no callback.
    """

    def __init__(
        self,
        game_type: str,
        player1: PlayerSession,
        player2: PlayerSession,
        on_game_end: Optional[Callable[[Optional[PlayerSession],
                                        Optional[PlayerSession],
                                        str], None]] = None,
    ):
        self.game_type = game_type
        self.players: list[PlayerSession] = [player1, player2]
        self.symbols: list[str] = ['X', 'O']
        self.current_turn: int = 0          # index into self.players
        self.board = get_board(game_type)
        self.over: bool = False
        self._on_game_end = on_game_end
        self._turn_timer: Optional[threading.Timer] = None
        self._start_turn_timer()

    # ------------------------------------------------------------------
    # Turn helpers
    # ------------------------------------------------------------------

    def current_player(self) -> PlayerSession:
        return self.players[self.current_turn]

    def opponent_of(self, player: PlayerSession) -> PlayerSession:
        idx = self.players.index(player)
        return self.players[1 - idx]

    def symbol_of(self, player: PlayerSession) -> str:
        return self.symbols[self.players.index(player)]

    # ------------------------------------------------------------------
    # Turn notification  (broadcast — same message to both players)
    # ------------------------------------------------------------------

    def broadcast_turn(self) -> None:
        """
        Send '301 Game turn <active_player_name> <board_state>' to both players.
        Both players receive the identical message; each client compares
        <active_player_name> to its own registered name to decide whose turn it is.
        """
        active = self.current_player()
        board_enc = self.board.encode()
        msg = f"{R_GAME_TURN} {active.name} {board_enc}"
        for p in self.players:
            p.send(msg)

    # ------------------------------------------------------------------
    # Turn timer
    # ------------------------------------------------------------------

    def _start_turn_timer(self) -> None:
        self._cancel_turn_timer()
        self._turn_timer = threading.Timer(TURN_TIMEOUT, self._on_turn_timeout)
        self._turn_timer.daemon = True
        self._turn_timer.start()

    def _cancel_turn_timer(self) -> None:
        if self._turn_timer:
            self._turn_timer.cancel()
            self._turn_timer = None

    def _on_turn_timeout(self) -> None:
        if self.over:
            return
        self.over = True
        loser = self.current_player()
        winner = self.opponent_of(loser)
        _log(f"[GAME] Turn timeout — {loser.name} forfeits")
        winner.send(R_GAME_FORFEIT)
        loser.send("304 Game over Loss Timeout")
        self._finish(winner, loser, 'forfeit')

    # ------------------------------------------------------------------
    # Move processing
    # ------------------------------------------------------------------

    def apply_move(self, player: PlayerSession, arg: str) -> tuple[bool, str]:
        """
        Validate and apply one move from *player*.

        Move validity is entirely delegated to the board implementation —
        the protocol only defines the reply codes, not the game rules.

        Returns (success, result_tag) where result_tag is one of:
            'ok'    — game continues
            'win'   — player won
            'draw'  — board full, no winner
        On failure returns (False, reply_code_string).
        """
        if self.over:
            return False, R_GAME_NOT_STARTED

        if player is not self.current_player():
            return False, R_NOT_YOUR_TURN

        symbol = self.symbol_of(player)

        # --- Move validation is fully delegated to the board class. ---
        # The protocol defines only that invalid moves receive 451.
        # What "invalid" means is decided by the board implementation.
        try:
            if self.game_type == 'TTT':
                from al1gn.games.ttt import TicTacToeBoard
                row, col = TicTacToeBoard.parse_move(arg)
                if not self.board.is_valid_move(row, col):
                    return False, R_INVALID_MOVE
                self.board.apply_move(row, col, symbol)
            else:  # C4 or any future game registered by the adopter
                from al1gn.games.connect4 import Connect4Board
                col = Connect4Board.parse_move(arg)
                if not self.board.is_valid_move(col):
                    return False, R_INVALID_MOVE
                self.board.apply_move(col, symbol)
        except (ValueError, IndexError):
            return False, R_BAD_PARAM

        self._cancel_turn_timer()
        board_enc = self.board.encode()

        # 204 goes to the mover *before* any push messages
        player.send(R_MOVE_ACCEPTED)

        opponent = self.opponent_of(player)

        # Win?
        if self.board.check_win(symbol):
            self.over = True
            player.send(f"{R_GAME_WIN} {board_enc}")
            opponent.send(f"{R_GAME_LOSS} {board_enc}")
            self._finish(player, opponent, 'win')
            return True, 'win'

        # Draw?
        if self.board.check_draw():
            self.over = True
            player.send(f"{R_GAME_DRAW} {board_enc}")
            opponent.send(f"{R_GAME_DRAW} {board_enc}")
            self._finish(player, opponent, 'draw')
            return True, 'draw'

        # Game continues — advance turn and broadcast to both players
        self.current_turn = 1 - self.current_turn
        self.broadcast_turn()
        self._start_turn_timer()
        return True, 'ok'

    # ------------------------------------------------------------------
    # Internal finish helper
    # ------------------------------------------------------------------

    def _finish(
        self,
        winner: Optional[PlayerSession],
        loser: Optional[PlayerSession],
        outcome: str,
    ) -> None:
        p1, p2 = self.players
        p1.record_game_end(p2, self.game_type)
        p2.record_game_end(p1, self.game_type)
        p1.state = 'PostGame'
        p2.state = 'PostGame'
        if self._on_game_end:
            self._on_game_end(winner, loser, outcome)
