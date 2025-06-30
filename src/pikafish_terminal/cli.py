#!/usr/bin/env python3
"""
Command-line interface for Pikafish Terminal.

This module provides the main entry point when the package is installed
and run via `pikafish` or `xiangqi` commands.
"""

import sys
import argparse
from typing import Optional
from pathlib import Path

from .logging_config import setup_logging
from .game import play
from .difficulty import list_difficulty_levels, get_difficulty_level


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="pikafish",
        description="Play Xiangqi (Chinese Chess) in your terminal against the Pikafish engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  pikafish                    # Start game with default settings
  pikafish --difficulty 5     # Play against expert level
  xiangqi --engine ./pikafish # Use custom engine path
  
{list_difficulty_levels()}

Environment Variables:
  PIKAFISH_LOG_LEVEL    Set logging level (DEBUG, INFO, WARNING, ERROR)
  PIKAFISH_LOG_FILE     Save logs to file
        """
    )
    
    parser.add_argument(
        "--engine",
        type=str,
        help="Path to Pikafish engine binary (auto-download if not specified)"
    )
    
    parser.add_argument(
        "--difficulty", "-d",
        type=int,
        choices=range(1, 7),
        help="Difficulty level (1=Beginner, 6=Master)"
    )
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"%(prog)s {get_version()}"
    )
    
    parser.add_argument(
        "--list-difficulties",
        action="store_true",
        help="List all available difficulty levels and exit"
    )
    
    return parser


def get_version() -> str:
    """Get the package version."""
    try:
        from ._version import version
        return version
    except ImportError:
        return "unknown"


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Handle special commands
    if args.list_difficulties:
        print(list_difficulty_levels())
        sys.exit(0)
    
    # Initialize logging
    setup_logging()
    
    # Determine difficulty
    difficulty = None
    if args.difficulty:
        try:
            difficulty = get_difficulty_level(args.difficulty)
        except KeyError:
            print(f"Error: Invalid difficulty level {args.difficulty}")
            sys.exit(1)
    
    # Start the game
    try:
        play(engine_path=args.engine, difficulty=difficulty)
    except KeyboardInterrupt:
        print("\nGame interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 