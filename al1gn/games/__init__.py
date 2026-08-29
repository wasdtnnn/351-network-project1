"""
Game registry — maps game type codes to their board classes.
Adding a new game only requires dropping a new module here and
registering it in GAME_REGISTRY below.
"""

from al1gn.games.ttt import TicTacToeBoard
from al1gn.games.connect4 import Connect4Board

# Registry: game_type string -> board class
GAME_REGISTRY = {
    'TTT': TicTacToeBoard,
    'C4':  Connect4Board,
}

VALID_GAME_TYPES = set(GAME_REGISTRY.keys())


def get_board(game_type: str):
    """Instantiate and return the board for the given game type.
    Raises KeyError if game_type is not registered."""
    return GAME_REGISTRY[game_type]()
