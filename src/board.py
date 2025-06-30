from typing import List

# Traditional Chinese xiangqi notation: files 1-9 from left to right
FILES = "123456789"
# Standard FEN for Xiangqi recognized by major engines like Pikafish.
INITIAL_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w"

# Map engine's piece notation to the display characters
PIECE_DISPLAY = {
    'r': 'r', 'n': 'h', 'b': 'e', 'a': 'a', 'k': 'k', 'c': 'c', 'p': 'p',
    'R': 'R', 'N': 'H', 'B': 'E', 'A': 'A', 'K': 'K', 'C': 'C', 'P': 'P',
    '.': '.'
}


class XiangqiBoard:
    """Very small Xiangqi board representation sufficient for playing and displaying.
    This class does *not* validate moves – validation is left to the engine. It merely
    keeps a mirror of the board so that we can render it in the terminal.
    """

    def __init__(self, fen: str = INITIAL_FEN):
        self.board: List[List[str]] = self._fen_to_board(fen)
        self._move_history: List[str] = []

    # ---------------------------- Fen helpers ---------------------------------
    def _fen_to_board(self, fen: str) -> List[List[str]]:
        rows = fen.split()[0].split("/")
        board: List[List[str]] = []
        for row in rows:  # top (black side) -> bottom (red side)
            current: List[str] = []
            for ch in row:
                if ch.isdigit():
                    current.extend(['.'] * int(ch))
                else:
                    current.append(ch)
            board.append(current)
        return board

    def board_to_fen(self) -> str:
        fen_rows: List[str] = []
        for row in self.board:
            empties = 0
            fen_row = ""
            for ch in row:
                if ch == '.':
                    empties += 1
                else:
                    if empties:
                        fen_row += str(empties)
                        empties = 0
                    fen_row += ch
            if empties:
                fen_row += str(empties)
            fen_rows.append(fen_row)
        
        # Determine whose turn it is. 'w' for Red (White), 'b' for Black.
        side_to_move = "w" if len(self._move_history) % 2 == 0 else "b"
        return f'{"/".join(fen_rows)} {side_to_move}'

    # ----------------------------- Moves --------------------------------------
    @property
    def move_history(self) -> List[str]:
        return self._move_history

    def push_move(self, uci: str) -> None:
        """Apply *uci* to the internal board with basic validation."""
        if len(uci) < 4:
            raise ValueError("Invalid move string, expected something like '1013'.")

        if uci[0].isalpha():
            s_file = ord(uci[0]) - ord('a')
            d_file = ord(uci[2]) - ord('a')
        else:
            s_file = int(uci[0]) - 1
            d_file = int(uci[2]) - 1
            
        s_rank = int(uci[1])
        d_rank = int(uci[3])
        
        if not (0 <= s_file <= 8 and 0 <= d_file <= 8):
            raise ValueError(f"Invalid file coordinates in move: {uci}")
        if not (0 <= s_rank <= 9 and 0 <= d_rank <= 9):
            raise ValueError(f"Invalid rank coordinates in move: {uci}")
        
        s_row = 9 - s_rank
        d_row = 9 - d_rank
        
        if not (0 <= s_row <= 9 and 0 <= d_row <= 9):
            raise ValueError(f"Invalid row coordinates in move: {uci}")
        
        piece = self.board[s_row][s_file]
        
        if piece == '.':
            raise ValueError(f"Invalid move: No piece found at source position {uci[:2]} (row {s_row}, file {s_file})")
        
        # Basic validation for king moves
        if piece.lower() == 'k':
            file_diff = abs(d_file - s_file)
            rank_diff = abs(d_rank - s_rank)
            
            # Kings can only move one square orthogonally
            if file_diff + rank_diff != 1:
                raise ValueError(f"Invalid king move: {uci} - Kings can only move one square orthogonally")
            
            # Red king must stay in red palace (ranks 0-2, files 3-5)
            if piece == 'K':
                if not (0 <= d_rank <= 2 and 3 <= d_file <= 5):
                    raise ValueError(f"Invalid king move: {uci} - Red king must stay in palace")
            
            # Black king must stay in black palace (ranks 7-9, files 3-5)  
            if piece == 'k':
                if not (7 <= d_rank <= 9 and 3 <= d_file <= 5):
                    raise ValueError(f"Invalid king move: {uci} - Black king must stay in palace")
        
        self.board[s_row][s_file] = '.'
        self.board[d_row][d_file] = piece
        engine_move = self._convert_to_engine_format(uci)
        self._move_history.append(engine_move)

    def _convert_to_engine_format(self, move: str) -> str:
        """Convert move from display format to engine format (a-i notation)."""
        if move[0].isalpha():
            return move
        
        s_file_num = int(move[0])
        s_rank = move[1]
        d_file_num = int(move[2])
        d_rank = move[3]
        
        s_file_letter = chr(ord('a') + s_file_num - 1)
        d_file_letter = chr(ord('a') + d_file_num - 1)
        
        return f"{s_file_letter}{s_rank}{d_file_letter}{d_rank}"

    def _convert_from_engine_format(self, move: str) -> str:
        """Convert move from engine format (a-i notation) to display format (1-9)."""
        if move[0].isdigit():
            return move
        
        s_file_letter = move[0]
        s_rank = move[1]
        d_file_letter = move[2]
        d_rank = move[3]
        
        s_file_num = ord(s_file_letter) - ord('a') + 1
        d_file_num = ord(d_file_letter) - ord('a') + 1
        
        return f"{s_file_num}{s_rank}{d_file_num}{d_rank}"

    # --------------------------- Rendering ------------------------------------
    def ascii(self) -> str:
        header = "   " + " ".join(FILES)
        lines = [header]
        for idx, row in enumerate(self.board):
            rank = 9 - idx
            row_str = f"{rank} "
            for ch in row:
                row_str += " " + PIECE_DISPLAY.get(ch, ch)
            lines.append(row_str)
        lines.append(header)
        return "\n".join(lines)