# AL1GN/1.0 — Application-Layer 1-on-1 Gaming Network

Custom application-layer protocol for 1v1 turn-based games over TCP.  
Games supported: **Tic-Tac-Toe (TTT)** and **Connect4 (C4)**.

---

## Files

| File | Description |
|------|-------------|
| `server.py` | AL1GN server — handles all clients, game logic, matchmaking |
| `client.py` | AL1GN client — interactive terminal UI |
| `protocol_spec.md` | Full protocol specification in Thai (PDF source) |
| `test_protocol.py` | Automated integration test suite (57 tests) |

---

## Quick Start

**1. Start the server**
```
python server.py
```
Default: listens on `0.0.0.0:25146`

**2. Start two clients** (in separate terminals)
```
python client.py
python client.py
```
Connect to a remote server: `python client.py <host> <port>`

---

## Playing a Game

### Tic-Tac-Toe via auto-queue

**Both clients run these commands in order:**
```
HELO Alice          <- register your name
QUEUE TTT           <- join matchmaking queue
```
Once matched, the first player is prompted to move:
```
MOVE 1,1            <- place at row 1, col 1  (0-indexed)
```

### Connect4 via private room

**Player 1:**
```
HELO Alice
MAKE C4             <- server returns a 6-char room code, e.g. "XK9P2M"
```
**Player 2:**
```
HELO Bob
JOIN XK9P2M         <- join the room
```

---

## All Commands

| Command | Description |
|---------|-------------|
| `HELO <name>` | Register player name (required first) |
| `QUEUE TTT\|C4` | Auto-matchmaking queue |
| `MAKE TTT\|C4` | Create private room |
| `JOIN <code>` | Join room by 6-char code |
| `MOVE <pos>` | Make a move: TTT=`row,col`, C4=`col` |
| `REMATCH` | Request rematch after game ends |
| `ACCEPT` | Accept opponent's rematch request |
| `DECLINE` | Decline opponent's rematch request |
| `QUIT` | Disconnect gracefully |
| `HELP` | Show command list |

---

## Configurable Parameters

Edit the constants at the top of `server.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PORT` | 25146 | Server listen port |
| `TURN_TIMEOUT` | 60s | Max time per move before forfeit |
| `RECONNECT_TIMEOUT` | 60s | Time to wait for disconnected player |
| `HEARTBEAT_INTERVAL` | 30s | Seconds between server PINGs |
| `PING_TIMEOUT` | 10s | Time to wait for PONG |

---

## Protocol Overview

Text-based, SMTP-inspired. Every message ends with `\r\n`.

```
Client -> Server:   COMMAND [argument]\r\n
Server -> Client:   3xx phrase [data]\r\n
```

**Status code families:**
- `2xx` — Success
- `3xx` — Game state (turn, game over, waiting)
- `4xx` — Client error (wrong turn, invalid move, bad sequence)
- `5xx` — Server error

See `protocol_spec.md` for the full specification.
