from colorama import init, Fore, Back, Style

init(autoreset=True)


def _colorize(ch: str, highlight: bool = False) -> str:
    """Colorize a piece character, optionally with highlighting."""
    if highlight:
        # Highlight with yellow background
        if ch.isupper():
            return Back.YELLOW + Fore.RED + ch + Style.RESET_ALL  # Red side pieces
        elif ch.islower():
            return Back.YELLOW + Fore.GREEN + ch + Style.RESET_ALL  # Black side pieces
        else:
            return Back.YELLOW + ch + Style.RESET_ALL  # Empty squares
    else:
        if ch.isupper():
            return Fore.RED + ch + Style.RESET_ALL  # Red side pieces
        elif ch.islower():
            return Fore.GREEN + ch + Style.RESET_ALL  # Black side pieces
        else:
            return ch


def _parse_move_coordinates(move: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """Parse a move string like '1013' or 'a0a3' into source and destination coordinates."""
    if len(move) != 4:
        raise ValueError("Move must be 4 characters")
    
    # Handle both numeric (1013) and algebraic (a0a3) notation
    if move[0].isdigit():
        # Numeric notation: file 1-9, rank 0-9
        src_file = int(move[0]) - 1  # Convert to 0-8
        src_rank = int(move[1])
        dst_file = int(move[2]) - 1
        dst_rank = int(move[3])
    else:
        # Algebraic notation: file a-i, rank 0-9
        src_file = ord(move[0]) - ord('a')  # Convert to 0-8
        src_rank = int(move[1])
        dst_file = ord(move[2]) - ord('a')
        dst_rank = int(move[3])
    
    return ((src_file, src_rank), (dst_file, dst_rank))


def render(ascii_board: str, last_move: str = "", flip_board: bool = False) -> str:
    """Return *ascii_board* with ANSI colors applied to the pieces and last move highlighted.
    
    Args:
        ascii_board: The ASCII board string from board.ascii()
        last_move: The last move for highlighting (e.g., "1013")
        flip_board: Whether to flip the board (True when human plays as Black)
    """
    lines = ascii_board.splitlines()
    
    # Parse move coordinates if provided
    highlighted_squares = set()
    if last_move:
        try:
            (src_file, src_rank), (dst_file, dst_rank) = _parse_move_coordinates(last_move)
            if flip_board:
                # Adjust coordinates for flipped board
                src_file = 8 - src_file
                src_rank = 9 - src_rank
                dst_file = 8 - dst_file
                dst_rank = 9 - dst_rank
            highlighted_squares.add((src_file, src_rank))
            highlighted_squares.add((dst_file, dst_rank))
        except (ValueError, IndexError):
            # Invalid move format, just skip highlighting
            pass
    
    if flip_board:
        # Flip the board for Black player perspective
        return _render_flipped_board(lines, highlighted_squares)
    else:
        # Normal rendering for Red player perspective
        return _render_normal_board(lines, highlighted_squares)


def _render_normal_board(lines: list[str], highlighted_squares: set[tuple[int, int]]) -> str:
    """Render the board in normal orientation (Red at bottom)."""
    out_lines = []
    
    for line_idx, line in enumerate(lines):
        if line_idx == 0 or line_idx == len(lines) - 1:
            # Header/footer lines (file coordinates)
            out_lines.append(line)
            continue
        
        # Board lines have format: "9  r h e a k a e h r" (rank, space, space, pieces)
        if len(line) < 3:
            out_lines.append(line)
            continue
        
        # Extract rank number (9 down to 0)
        rank = 9 - (line_idx - 1)  # Convert line index to rank
        
        # Handle both single-digit ranks (0-9)
        parts = line.split()
        if len(parts) >= 2:
            # parts[0] is the rank number, parts[1] onwards are pieces
            new_line = f"{parts[0]} "
            for file_idx, piece in enumerate(parts[1:]):
                if file_idx < 9:  # Valid file position
                    is_highlighted = (file_idx, rank) in highlighted_squares  # rank uses 0-9 directly
                    new_line += " " + _colorize(piece, highlight=is_highlighted)
        else:
            new_line = line
        
        out_lines.append(new_line)
    
    return "\n".join(out_lines)


def _render_flipped_board(lines: list[str], highlighted_squares: set[tuple[int, int]]) -> str:
    """Render the board flipped 180 degrees (Black at bottom).
    
    In xiangqi notation, files are numbered 1-9 from each player's perspective.
    So for Black, file 1 is on Black's left (which appears on the right side of the flipped display).
    """
    out_lines = []
    
    # For flipped board, files are still 1-9 but from Black's perspective
    # File 1 is on Black's left (right side of display)
    header_footer = "   1 2 3 4 5 6 7 8 9"
    
    # Add flipped header
    out_lines.append(header_footer)
    
    # Process board lines in reverse order (flip vertically)
    board_lines = lines[1:-1]  # Exclude original header and footer
    
    for line_idx, line in enumerate(reversed(board_lines)):
        if len(line) < 3:
            out_lines.append(line)
            continue
        
        # After flipping, we want the bottom row (closest to Black) to be rank 0
        # and the top row to be rank 9 to match the coordinate system shown to
        # the human Black player.

        original_rank = 9 - line_idx  # Original rank before flipping
        flipped_rank_display = original_rank  # Display this rank number on the flipped board

        # Build the new line with the correct flipped rank number
        new_line = f"{flipped_rank_display} "
        
        # Extract pieces from the line (skip rank number and spaces)
        # Handle both single-digit ranks
        pieces = []
        # Find where the pieces start (after rank number and spaces)
        parts = line.split()
        if len(parts) >= 2:
            # parts[0] is the rank number, parts[1] onwards are pieces
            for i in range(1, len(parts)):
                pieces.append(parts[i])
        
        # Reverse the pieces horizontally and add highlighting
        for file_idx, ch in enumerate(reversed(pieces)):
            # Calculate the flipped coordinates for highlighting
            # Convert display rank back to 0-9 for highlighting (original_rank)
            highlight_rank = original_rank
            is_highlighted = (file_idx, highlight_rank) in highlighted_squares
            new_line += " " + _colorize(ch, highlight=is_highlighted)
        
        out_lines.append(new_line)
    
    # Add flipped footer
    out_lines.append(header_footer)
    
    return "\n".join(out_lines) 