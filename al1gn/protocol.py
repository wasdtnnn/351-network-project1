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

# ---------------------------------------------------------------------------
# 2xx — Success
# ---------------------------------------------------------------------------
R_OK               = "200 OK"
R_SESSION_CREATED  = "201 Session created"
R_SESSION_RESTORED = "201 Session restored"
R_ROOM_CREATED     = "202 Room created"
R_JOINED_ROOM      = "203 Joined room"
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
# ---------------------------------------------------------------------------
R_WAITING            = "300 Waiting for opponent"
R_YOUR_TURN          = "301 Your turn"
R_OPP_TURN           = "302 Opponent's turn"
R_GAME_WIN           = "303 Game over Win"
R_GAME_LOSS          = "304 Game over Loss"
R_GAME_DRAW          = "305 Game over Draw"
R_GAME_FORFEIT       = "306 Game over Forfeit"
R_REMATCH_REQUESTED  = "307 Rematch requested"
R_OPP_DISCONNECTED   = "308 Opponent disconnected Waiting for reconnect"
R_REMATCH_DECLINED   = "309 Rematch declined"

# ---------------------------------------------------------------------------
# 4xx — Client errors
# ---------------------------------------------------------------------------
R_BAD_REQUEST      = "400 Bad request"
R_NOT_REGISTERED   = "401 Not registered"
R_ROOM_NOT_FOUND   = "402 Room not found"
R_ROOM_FULL        = "403 Room full"
R_NOT_YOUR_TURN    = "404 Not your turn"
R_INVALID_MOVE     = "405 Invalid move"
R_GAME_NOT_STARTED = "406 Game not started"
R_NAME_TAKEN       = "407 Name already taken"
R_UNKNOWN_GAME     = "408 Unknown game type"

# ---------------------------------------------------------------------------
# 5xx — Server errors
# ---------------------------------------------------------------------------
R_SYNTAX_ERROR   = "500 Syntax error"
R_BAD_PARAM      = "501 Bad parameter"
R_BAD_SEQUENCE   = "503 Bad command sequence"
R_INTERNAL_ERROR = "520 Internal server error"
R_SHUTTING_DOWN  = "521 Service closing"
