from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class DifficultyLevel:
    """Represents a difficulty level with engine settings."""
    name: str
    description: str
    depth: int
    time_limit_ms: Optional[int] = None
    uci_options: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.uci_options is None:
            self.uci_options = {}


def create_custom_difficulty(depth: int, time_limit_ms: Optional[int] = None, 
                           uci_options: Optional[Dict[str, Any]] = None) -> DifficultyLevel:
    """Create a custom difficulty level with specified parameters."""
    if depth < 1:
        raise ValueError("Depth must be at least 1")
    if time_limit_ms is not None and time_limit_ms < 100:
        raise ValueError("Time limit must be at least 100ms")
    
    # Determine difficulty name based on depth
    if depth <= 3:
        name = "Custom-Beginner"
    elif depth <= 6:
        name = "Custom-Easy"
    elif depth <= 10:
        name = "Custom-Medium"
    elif depth <= 15:
        name = "Custom-Hard"
    elif depth <= 20:
        name = "Custom-Expert"
    else:
        name = "Custom-Master"
    
    time_desc = f" (thinking time: {time_limit_ms/1000:.1f}s)" if time_limit_ms else ""
    description = f"Custom difficulty - Depth {depth}{time_desc}"
    
    return DifficultyLevel(
        name=name,
        description=description,
        depth=depth,
        time_limit_ms=time_limit_ms,
        uci_options=uci_options or {}
    )


def list_difficulty_levels() -> str:
    """Return a formatted string listing difficulty level options."""
    lines = ["Difficulty levels are configured in config.yaml"]
    lines.append("Use --config-list to see available difficulties")
    lines.append("\nCustom difficulty options:")
    lines.append("  --depth N            Set search depth (1-50, higher = stronger)")
    lines.append("  --time N             Set thinking time per move in seconds (0.1-300)")
    lines.append("  --depth N --time N   Combine both for full control")
    lines.append("\nIn-game commands:")
    lines.append("  h, hint              Show top 3 move suggestions")
    lines.append("  hint N               Show top N move suggestions (1-10)")
    lines.append("  s, score             Toggle position evaluation display")
    lines.append("  quit, exit, q        Exit the game")
    return "\n".join(lines)


