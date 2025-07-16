#!/usr/bin/env python3
"""
Command-line interface for Pikafish Terminal.

This module provides the main entry point when the package is installed
and run via `pikafish` or `xiangqi` commands.
"""

import sys
import argparse

from .logging_config import setup_logging
from .game import play
from .difficulty import list_difficulty_levels, create_custom_difficulty
from .downloader import cleanup_data_directory, get_downloaded_files_info
from .config import get_config


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="pikafish",
        description="Play Xiangqi (Chinese Chess) in your terminal against the Pikafish engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  pikafish                      # Start game with default settings
  pikafish --difficulty 3       # Use difficulty from config (by number or name)
  pikafish --difficulty quick_game  # Use named difficulty from config
  pikafish --depth 12           # Custom difficulty with depth 12
  pikafish --time 2.0           # Custom difficulty with 2 second thinking time
  pikafish --depth 15 --time 3  # Custom difficulty with both depth and time
  pikafish --config-list        # List all configuration values
  pikafish --info               # Show info about downloaded files  
  pikafish --cleanup            # Remove all downloaded files
  
{list_difficulty_levels()}

Environment Variables:
  PIKAFISH_LOG_LEVEL    Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  PIKAFISH_LOG_FILE     Save logs to file
        """
    )
    
    parser.add_argument(
        "--engine",
        type=str,
        help="Path to Pikafish engine binary (auto-download if not specified)"
    )
    
    # Difficulty options
    parser.add_argument(
        "--difficulty",
        help="Difficulty from config: number or name (e.g., '3', 'quick_game', 'analysis_mode')"
    )
    
    parser.add_argument(
        "--depth",
        type=int,
        help="Search depth for custom difficulty (1-50)"
    )
    
    parser.add_argument(
        "--time",
        type=float,
        help="Time limit in seconds for custom difficulty (0.1-300)"
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
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (overrides PIKAFISH_LOG_LEVEL environment variable)"
    )
    
    parser.add_argument(
        "--config-list",
        action="store_true",
        help="List all configuration values and exit"
    )
    
    return parser



def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Handle special commands
    if args.list_difficulties:
        print(list_difficulty_levels())
        sys.exit(0)
    
    if args.config_list:
        try:
            config = get_config()
            print("=== Current Configuration ===")
            print(f"Game settings:")
            print(f"  show_score: {config.get('game.show_score')}")
            print(f"  default_difficulty: {config.get('game.default_difficulty')}")
            print(f"  move_history_length: {config.get('game.move_history_length')}")
            print(f"\nScoring settings:")
            print(f"  depth: {config.get('scoring.depth')}")
            print(f"  time_limit_ms: {config.get('scoring.time_limit_ms')}")
            print(f"\nHint settings:")
            print(f"  default_count: {config.get('hints.default_count')}")
            print(f"  max_count: {config.get('hints.max_count')}")
            print(f"  depth: {config.get('hints.depth')}")
            print(f"  time_limit_ms: {config.get('hints.time_limit_ms')}")
            print(f"  show_scores: {config.get('hints.show_scores')}")
            print(f"\nEngine settings:")
            print(f"  path: {config.get('engine.path')}")
            print(f"  startup_timeout: {config.get('engine.startup_timeout')}")
            print(f"  move_timeout: {config.get('engine.move_timeout')}")
            print(f"\nUI settings:")
            print(f"  ai_move_pause_seconds: {config.get('ui.ai_move_pause_seconds')}")
            print(f"\nLogging settings:")
            print(f"  level: {config.get('logging.level')}")
            print(f"  file: {config.get('logging.file')}")
            print(f"\nDifficulties:")
            difficulties = config.get('difficulties', {})
            if isinstance(difficulties, dict):
                for identifier, diff in difficulties.items():
                    if isinstance(diff, dict) and 'name' in diff and 'description' in diff:
                        if isinstance(identifier, int):
                            print(f"  Level {identifier}: {diff['name']} - {diff['description']}")
                        else:
                            print(f"  {identifier}: {diff['name']} - {diff['description']}")
        except Exception as e:
            print(f"Error loading configuration: {e}")
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
    try:
        config = get_config()
        log_level = args.log_level or config.get_required('logging.level')
        setup_logging(log_level=log_level)
    except Exception as e:
        # If config fails, use command line arg or basic logging
        log_level = args.log_level or 'INFO'
        setup_logging(log_level=log_level)
        print(f"Warning: Could not load configuration: {e}")
        print("Continuing with command line arguments only...")
        
        # Create a minimal config for the game
        config = None
    
    # Determine difficulty
    difficulty = None
    depth = None
    time_limit_ms = None
    
    if config:
        show_score_value = config.get_required('game.show_score')
        show_score = bool(show_score_value) if show_score_value is not None else False
    else:
        show_score = False  # Default if no config
    
    # Check for conflicting arguments
    if args.difficulty and (args.depth or args.time):
        print("Error: Cannot use --difficulty with --depth or --time options")
        print("Use either predefined difficulty levels (--difficulty) or custom settings (--depth/--time)")
        sys.exit(1)
    
    # Handle difficulty from config (number or name)
    if args.difficulty:
        if config is None:
            print("Error: Difficulty selection requires a valid config file")
            sys.exit(1)
            
        custom_config = config.get_difficulty(args.difficulty)
        if custom_config is None:
            print(f"Error: Difficulty '{args.difficulty}' not found")
            print("Available difficulties:")
            all_diffs = config.get('difficulties', {})
            if isinstance(all_diffs, dict):
                for identifier in all_diffs.keys():
                    print(f"  {identifier}")
            sys.exit(1)
        
        # Create difficulty from config
        from .difficulty import DifficultyLevel
        difficulty = DifficultyLevel(
            name=custom_config['name'],
            description=custom_config['description'],
            depth=custom_config['depth'],
            time_limit_ms=custom_config.get('time_limit_ms'),
            uci_options=custom_config.get('uci_options', {})
        )
    
    # Handle custom difficulty
    elif args.depth or args.time:
        try:
            depth = args.depth
            
            if args.time is not None:
                if args.time < 0.1 or args.time > 300:
                    print("Error: Time limit must be between 0.1 and 300 seconds")
                    sys.exit(1)
                time_limit_ms = int(args.time * 1000)
            
            if args.depth is not None and (args.depth < 1 or args.depth > 50):
                print("Error: Depth must be between 1 and 50")
                sys.exit(1)
            
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    # Start the game
    try:
        play(engine_path=args.engine, difficulty=difficulty, depth=depth, time_limit_ms=time_limit_ms, show_score=show_score)
    except KeyboardInterrupt:
        print("\nGame interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 