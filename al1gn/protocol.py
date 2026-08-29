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
R_SESSION_CREATED  = "201 Session_created"    # + <token>  appended by server
R_SESSION_RESTORED = "201 Session_restored"   # + <board_state>  appended by server
R_ROOM_CREATED     = "202 Room_created"       # + <room_code>  appended by server
R_JOINED_ROOM      = "203 Joined_room"        # + <room_code>  appended by server
R_MOVE_ACCEPTED    = "204 Move_accepted"
R_REMATCH_ACCEPTED = "205 Rematch_accepted"
R_PONG             = "206 Pong_received"

# ---------------------------------------------------------------------------
# 2xx — Connection lifecycle (also success family)
# ---------------------------------------------------------------------------
R_SERVICE_READY    = "220 Service_ready AL1GN/1.0"
R_SERVICE_CLOSING  = "221 Service_closing_connection"

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
R_WAITING          = "300 Waiting_for_opponent"
R_GAME_TURN        = "301 Game_turn"         # + <active_player_name> <board_state>
R_GAME_WIN         = "303 Game_over_Win"     # + <board_state>
R_GAME_LOSS        = "304 Game_over_Loss"    # + <board_state>
R_GAME_DRAW        = "305 Game_over_Draw"    # + <board_state>
R_GAME_FORFEIT     = "306 Game_over_Forfeit"
R_REMATCH_REQUESTED = "307 Rematch_requested"
R_OPP_DISCONNECTED = "308 Opponent_disconnected_Waiting_for_reconnect"
R_REMATCH_DECLINED = "309 Rematch_declined"

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
R_BAD_REQUEST      = "400 Bad_request"
R_NOT_REGISTERED   = "430 Not_registered"
R_ROOM_NOT_FOUND   = "431 Room_not_found"
R_ROOM_FULL        = "432 Room_full"
R_NAME_TAKEN       = "433 Name_already_taken"
R_UNKNOWN_GAME     = "434 Unknown_game_type"
R_NOT_YOUR_TURN    = "450 Not_your_turn"
R_INVALID_MOVE     = "451 Invalid_move"
R_GAME_NOT_STARTED = "452 Game_not_started"
R_BAD_TOKEN        = "460 Bad_token"

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
R_SYNTAX_ERROR     = "500 Syntax_error"
R_BAD_PARAM        = "501 Bad_parameter"
R_BAD_SEQUENCE     = "503 Bad_command_sequence"
R_INTERNAL_ERROR   = "520 Internal_server_error"
R_SHUTTING_DOWN    = "521 Service_closing"
