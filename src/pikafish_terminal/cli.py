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
from .downloader import cleanup_data_directory, get_downloaded_files_info


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
  pikafish --info             # Show info about downloaded files
  pikafish --cleanup          # Remove all downloaded files
  
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
    
    parser.add_argument(
        "--cleanup",
        action="store_true", 
        help="Remove all downloaded game files (engine and neural network) and exit"
    )
    
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show information about downloaded files and exit"
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
    
    if args.info:
        info = get_downloaded_files_info()
        if not info["exists"]:
            print(f"No downloaded files found.")
            print(f"Files would be stored in: {info['path']}")
        else:
            print(f"Downloaded files location: {info['path']}")
            print(f"Total files: {len(info['files'])}")
            print(f"Total size: {info['total_size'] / (1024*1024):.1f} MB")
            print("\nFiles:")
            for file in info["files"]:
                print(f"  {file['name']} ({file['size'] / (1024*1024):.1f} MB)")
        sys.exit(0)
    
    if args.cleanup:
        info = get_downloaded_files_info()
        if not info["exists"]:
            print("No downloaded files found - nothing to clean up.")
            sys.exit(0)
        
        print(f"This will remove all downloaded Pikafish files from:")
        print(f"  {info['path']}")
        print(f"Total size: {info['total_size'] / (1024*1024):.1f} MB")
        
        try:
            confirm = input("\nAre you sure? (y/N): ").strip().lower()
            if confirm in ('y', 'yes'):
                cleanup_data_directory()
                print("Successfully removed all downloaded files.")
            else:
                print("Cleanup cancelled.")
        except KeyboardInterrupt:
            print("\nCleanup cancelled.")
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