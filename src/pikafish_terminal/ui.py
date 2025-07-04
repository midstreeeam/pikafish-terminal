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


def render(ascii_board: str, last_move: str = "") -> str:
    """Return *ascii_board* with ANSI colors applied to the pieces and last move highlighted."""
    lines = ascii_board.splitlines()
    out_lines = []
    
    # Parse move coordinates if provided
    highlighted_squares = set()
    if last_move:
        try:
            (src_file, src_rank), (dst_file, dst_rank) = _parse_move_coordinates(last_move)
            highlighted_squares.add((src_file, src_rank))
            highlighted_squares.add((dst_file, dst_rank))
        except (ValueError, IndexError):
            # Invalid move format, just skip highlighting
            pass
    
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
        
        new_line = ""
        char_idx = 0
        for ch in line:
            if char_idx >= 3 and char_idx % 2 == 1:
                # This is a piece position (odd indices after rank and spaces)
                file_idx = (char_idx - 3) // 2
                if file_idx < 9:  # Valid file position
                    is_highlighted = (file_idx, rank) in highlighted_squares
                    new_line += _colorize(ch, highlight=is_highlighted)
                else:
                    new_line += ch
            else:
                new_line += ch
            char_idx += 1
        
        out_lines.append(new_line)
    
    return "\n".join(out_lines) 