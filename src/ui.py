from colorama import init, Fore, Style

init(autoreset=True)


def _colorize(ch: str) -> str:
    if ch.isupper():
        return Fore.RED + ch + Style.RESET_ALL  # Red side pieces
    if ch.islower():
        return Fore.GREEN + ch + Style.RESET_ALL  # Black side pieces
    return ch


def render(ascii_board: str) -> str:
    """Return *ascii_board* with ANSI colors applied to the pieces."""
    out_lines = []
    for line in ascii_board.splitlines():
        new_line = "".join(_colorize(c) if c.isalpha() else c for c in line)
        out_lines.append(new_line)
    return "\n".join(out_lines) 