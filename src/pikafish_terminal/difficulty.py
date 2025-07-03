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


# Predefined difficulty levels
DIFFICULTY_LEVELS = {
    1: DifficultyLevel(
        name="Beginner",
        description="Very easy - Quick moves, shallow thinking",
        depth=3,
        time_limit_ms=500,
        uci_options={}
    ),
    2: DifficultyLevel(
        name="Easy",
        description="Easy - Basic tactics",
        depth=5,
        time_limit_ms=1000,
        uci_options={}
    ),
    3: DifficultyLevel(
        name="Medium",
        description="Medium - Good for casual players",
        depth=8,
        time_limit_ms=2000,
        uci_options={}
    ),
    4: DifficultyLevel(
        name="Hard",
        description="Hard - Strong tactical play",
        depth=12,
        time_limit_ms=5000,
        uci_options={}
    ),
    5: DifficultyLevel(
        name="Expert",
        description="Expert - Very strong play",
        depth=16,
        time_limit_ms=10000,
        uci_options={}
    ),
    6: DifficultyLevel(
        name="Master",
        description="Master - Near optimal play (slow)",
        depth=20,
        time_limit_ms=30000,
        uci_options={}
    )
}


def get_difficulty_level(level: int) -> DifficultyLevel:
    """Get difficulty level by number."""
    if level not in DIFFICULTY_LEVELS:
        raise ValueError(f"Invalid difficulty level: {level}. Must be 1-{len(DIFFICULTY_LEVELS)}")
    return DIFFICULTY_LEVELS[level]


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
    """Return a formatted string listing all difficulty levels."""
    lines = ["Available difficulty levels:"]
    for level_num, level in DIFFICULTY_LEVELS.items():
        lines.append(f"  {level_num}. {level.name} - {level.description}")
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


def prompt_difficulty_selection() -> DifficultyLevel:
    """Prompt user to select a difficulty level."""
    print(list_difficulty_levels())
    print("\nYou can also specify custom difficulty when starting the game:")
    print("  pikafish --depth 10 --time 3.0")
    
    while True:
        try:
            choice = input("\nSelect difficulty level (1-6, default=3): ").strip()
            if not choice:
                choice = "3"  # Default to Medium
            
            level = int(choice)
            return get_difficulty_level(level)
            
        except (ValueError, KeyError):
            print(f"Invalid choice. Please enter a number between 1 and {len(DIFFICULTY_LEVELS)}.")