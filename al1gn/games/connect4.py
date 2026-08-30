"""
Connect4 board
"""

class Connect4Board:
    """7-column × 6-row Connect4 board.  Row 0 is the top."""

    ROWS = 6
    COLS = 7

    def __init__(self):
        # board[row][col] = '.' | 'X' | 'O'
        self.board: list[list[str]] = [
            ['.' for _ in range(self.COLS)] for _ in range(self.ROWS)
        ]

    # ------------------------------------------------------------------
    # Move interface
    # ------------------------------------------------------------------

    @staticmethod
    def parse_move(arg: str) -> int:
        """Parse 'col' -> int.  Raises ValueError on bad input."""
        return int(arg)

    def is_valid_move(self, col: int) -> bool:
        """A column is playable when it is in range and has a free top cell."""
        if not (0 <= col < self.COLS):
            return False
        return self.board[0][col] == '.'

    def apply_move(self, col: int, symbol: str) -> int:
        """Drop a piece into *col* under gravity.
        Returns the row index the piece landed on.
        Raises ValueError if the column is full (call is_valid_move first)."""
        for row in range(self.ROWS - 1, -1, -1):
            if self.board[row][col] == '.':
                self.board[row][col] = symbol
                return row
        raise ValueError(f"Column {col} is full")

    # ------------------------------------------------------------------
    # Game-state queries
    # ------------------------------------------------------------------

    def check_win(self, symbol: str) -> bool:
        b = self.board
        # horizontal
        for r in range(self.ROWS):
            for c in range(self.COLS - 3):
                if all(b[r][c + k] == symbol for k in range(4)):
                    return True
        # vertical
        for r in range(self.ROWS - 3):
            for c in range(self.COLS):
                if all(b[r + k][c] == symbol for k in range(4)):
                    return True
        # diagonal down-right
        for r in range(self.ROWS - 3):
            for c in range(self.COLS - 3):
                if all(b[r + k][c + k] == symbol for k in range(4)):
                    return True
        # diagonal down-left
        for r in range(self.ROWS - 3):
            for c in range(3, self.COLS):
                if all(b[r + k][c - k] == symbol for k in range(4)):
                    return True
        return False

    def check_draw(self) -> bool:
        """Board is a draw when every top cell is occupied."""
        return all(self.board[0][c] != '.' for c in range(self.COLS))

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def encode(self) -> str:
        """Wire format: rows joined by '/', cells by ','.
        Example (row 0 first): '.,.,.,.,.,.,./...'"""
        return '/'.join(','.join(row) for row in self.board)

    def render(self) -> str:
        """Human-readable ASCII grid for console output."""
        lines = ["  " + "   ".join(str(c) for c in range(self.COLS))]
        for r, row in enumerate(self.board):
            lines.append(f"{r} " + " | ".join(row))
            if r < self.ROWS - 1:
                lines.append("  " + "---+" * (self.COLS - 1) + "---")
        return '\n'.join(lines)
