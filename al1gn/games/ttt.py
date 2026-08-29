"""
Tic-Tac-Toe board
"""

class TicTacToeBoard:
    """3×3 Tic-Tac-Toe board."""

    ROWS = 3
    COLS = 3

    def __init__(self):
        # board[row][col] = '.' | 'X' | 'O'
        self.board: list[list[str]] = [
            ['.' for _ in range(self.COLS)] for _ in range(self.ROWS)
        ]

    # ------------------------------------------------------------------
    # Move interface
    # ------------------------------------------------------------------

    @staticmethod
    def parse_move(arg: str) -> tuple[int, int]:
        """Parse 'row,col' -> (row, col).  Raises ValueError on bad input."""
        parts = arg.split(',')
        if len(parts) != 2:
            raise ValueError(f"Expected 'row,col', got '{arg}'")
        return int(parts[0]), int(parts[1])

    def is_valid_move(self, row: int, col: int) -> bool:
        if not (0 <= row < self.ROWS and 0 <= col < self.COLS):
            return False
        return self.board[row][col] == '.'

    def apply_move(self, row: int, col: int, symbol: str) -> None:
        self.board[row][col] = symbol

    # ------------------------------------------------------------------
    # Game-state queries
    # ------------------------------------------------------------------

    def check_win(self, symbol: str) -> bool:
        b = self.board
        for i in range(3):
            if all(b[i][j] == symbol for j in range(3)):   # row
                return True
            if all(b[j][i] == symbol for j in range(3)):   # col
                return True
        if all(b[i][i]     == symbol for i in range(3)):   # main diagonal
            return True
        if all(b[i][2 - i] == symbol for i in range(3)):   # anti-diagonal
            return True
        return False

    def check_draw(self) -> bool:
        return all(
            self.board[r][c] != '.'
            for r in range(self.ROWS)
            for c in range(self.COLS)
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def encode(self) -> str:
        """Wire format: rows joined by '/', cells by ','.
        Example: 'X,.,O/.,X,./O,.,.'"""
        return '/'.join(','.join(row) for row in self.board)

    def render(self) -> str:
        """Human-readable ASCII grid for console output."""
        lines = ["    0   1   2"]
        for r, row in enumerate(self.board):
            lines.append(f"  {r}  " + " | ".join(row))
            if r < self.ROWS - 1:
                lines.append("    ---+---+---")
        return '\n'.join(lines)
