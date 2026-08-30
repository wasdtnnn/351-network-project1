"""
AL1GN/1.0 — Server entry point
================================
Run with:
    python server.py [host] [port]
    Defaults: 0.0.0.0  25146
"""

import sys
from al1gn.server_core import AL1GNServer
from al1gn.protocol import HOST, PORT

if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
    AL1GNServer(host=host, port=port).run()
