"""
Pikafish Terminal - A terminal-based Xiangqi (Chinese Chess) game.

This package provides a command-line interface for playing Xiangqi against
the Pikafish engine with automatic engine download and setup.
"""

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from .game import play
from .engine import PikafishEngine
from .board import XiangqiBoard
from .difficulty import DifficultyLevel, get_difficulty_level

__all__ = [
    "__version__",
    "play",
    "PikafishEngine", 
    "XiangqiBoard",
    "DifficultyLevel",
    "get_difficulty_level",
] 