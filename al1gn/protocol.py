"""
AL1GN/1.0 — Application-Layer 1-on-1 Gaming Network Protocol
=============================================================
All protocol-level constants live here:
  - Configurable server parameters
  - Every reply code (numeric string + human phrase)

Nothing in this module imports from any other al1gn module.
Any module that needs a reply code imports it from here.
"""

# ---------------------------------------------------------------------------
# Configurable parameters (protocol adopter may adjust)
# ---------------------------------------------------------------------------
HOST               = "0.0.0.0"
PORT               = 25146
TURN_TIMEOUT       = 60    # seconds per move before forfeit
RECONNECT_TIMEOUT  = 60    # seconds to wait for a dropped player to return
HEARTBEAT_INTERVAL = 30    # seconds between server PING messages
PING_TIMEOUT       = 10    # seconds to wait for PONG before marking disconnected
MAX_NAME_LENGTH    = 32
ROOM_CODE_LENGTH   = 6
TOKEN_LENGTH       = 16    # length of randomly-generated session token (hex chars)

# ---------------------------------------------------------------------------
# 2xx — Success
# ---------------------------------------------------------------------------
R_OK               = "200 OK"
R_SESSION_CREATED  = "201 Session created"    # + <token>  appended by server
R_SESSION_RESTORED = "201 Session restored"   # + <board_state>  appended by server
R_ROOM_CREATED     = "202 Room created"       # + <room_code>  appended by server
R_JOINED_ROOM      = "203 Joined room"        # + <room_code>  appended by server
R_MOVE_ACCEPTED    = "204 Move accepted"
R_REMATCH_ACCEPTED = "205 Rematch accepted"
R_PONG             = "206 Pong received"

# ---------------------------------------------------------------------------
# 2xx — Connection lifecycle (also success family)
# ---------------------------------------------------------------------------
R_SERVICE_READY    = "220 AL1GN/1.0 Service ready"
R_SERVICE_CLOSING  = "221 Service closing connection"

# ---------------------------------------------------------------------------
# 3xx — Game state
#
# 301 Game turn <active_player_name> <board_state>
#   Sent to BOTH players after every move (and at game start).
#   <active_player_name> is the name of the player whose turn it is now.
#   Each client compares this name against its own registered name to
#   determine whether it is their turn or the opponent's.
#   This single broadcast replaces the old asymmetric 301/302 pair.
# ---------------------------------------------------------------------------
R_WAITING            = "300 Waiting for opponent"
R_GAME_TURN          = "301 Game turn"         # + <active_player_name> <board_state>
R_GAME_WIN           = "303 Game over Win"     # + <board_state>
R_GAME_LOSS          = "304 Game over Loss"    # + <board_state>
R_GAME_DRAW          = "305 Game over Draw"    # + <board_state>
R_GAME_FORFEIT       = "306 Game over Forfeit"
R_REMATCH_REQUESTED  = "307 Rematch requested"
R_OPP_DISCONNECTED   = "308 Opponent disconnected Waiting for reconnect"
R_REMATCH_DECLINED   = "309 Rematch declined"

# ---------------------------------------------------------------------------
# 4xx — Client errors
#
# Numbering rationale (aligned with FTP RFC 959 / SMTP RFC 5321):
#   400  Bad request        — generic malformed command (x00 syntax group)
#   430  Not registered     — analogous to FTP 430 "not logged in"
#   431  Room not found     — resource unavailable (4x1 group)
#   432  Room full          — resource unavailable
#   433  Name already taken — credential/identity conflict (4x3 group)
#   434  Unknown game type  — requested resource does not exist
#   450  Not your turn      — FTP 450 "action not taken, try again"
#   451  Invalid move       — FTP 451 "action aborted, game-defined rule"
#   452  Game not started   — FTP 452 "insufficient state to act"
#   460  Bad token          — authentication token mismatch on reconnect
# ---------------------------------------------------------------------------
R_BAD_REQUEST      = "400 Bad request"
R_NOT_REGISTERED   = "430 Not registered"
R_ROOM_NOT_FOUND   = "431 Room not found"
R_ROOM_FULL        = "432 Room full"
R_NAME_TAKEN       = "433 Name already taken"
R_UNKNOWN_GAME     = "434 Unknown game type"
R_NOT_YOUR_TURN    = "450 Not your turn"
R_INVALID_MOVE     = "451 Invalid move"
R_GAME_NOT_STARTED = "452 Game not started"
R_BAD_TOKEN        = "460 Bad token"

# ---------------------------------------------------------------------------
# 5xx — Server errors (permanent; client must change something before retry)
#
# Aligned with FTP 5xx / SMTP 5xx permanent-failure semantics:
#   500  Syntax error       — unrecognised command (FTP 500)
#   501  Bad parameter      — syntax error in arguments (FTP 501)
#   503  Bad command seq    — out-of-order command (FTP 503)
#   520  Internal error     — server-side fault
#   521  Service closing    — server shutting down
# ---------------------------------------------------------------------------
R_SYNTAX_ERROR   = "500 Syntax error"
R_BAD_PARAM      = "501 Bad parameter"
R_BAD_SEQUENCE   = "503 Bad command sequence"
R_INTERNAL_ERROR = "520 Internal server error"
R_SHUTTING_DOWN  = "521 Service closing"
