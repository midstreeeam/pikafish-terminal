"""
Pikafish Terminal - A terminal-based Xiangqi (Chinese Chess) game.

This package provides a command-line interface for playing Xiangqi against
the Pikafish engine with automatic engine download and setup.
"""


from .game import play
from .engine import PikafishEngine
from .board import XiangqiBoard
from .difficulty import DifficultyLevel, create_custom_difficulty
from .config import get_config, ConfigManager

__all__ = [
    "play",
    "PikafishEngine", 
    "XiangqiBoard",
    "DifficultyLevel",
    "create_custom_difficulty",
    "get_config",
    "ConfigManager",
] 