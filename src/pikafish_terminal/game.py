from __future__ import annotations

import sys
from typing import Optional

from .board import XiangqiBoard
from .engine import PikafishEngine
from .ui import render
from .difficulty import DifficultyLevel, create_custom_difficulty
from .logging_config import get_logger
from .config import get_config, ConfigError


PROMPT = "(pikafish) > "


def play(engine_path: Optional[str] = None, difficulty: Optional[DifficultyLevel] = None, 
         depth: Optional[int] = None, time_limit_ms: Optional[int] = None, show_score: bool = False) -> None:
    """Run an interactive terminal game of Xiangqi against Pikafish.
    
    Args:
        engine_path: Path to Pikafish engine binary (auto-download if not specified)
        difficulty: Predefined difficulty level (mutually exclusive with depth/time_limit_ms)
        depth: Custom search depth (1-50, higher = stronger)
        time_limit_ms: Custom thinking time per move in milliseconds (100-300000)
        show_score: Whether to display position evaluation scores during the game
    """
    logger = get_logger('pikafish.game')
    board = XiangqiBoard()
    
    try:
        config = get_config()
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Configuration error: {e}")
        raise
    
    # Use config defaults if not specified
    if not show_score:
        show_score = config.get_required('game.show_score')
    
    score_display_enabled = show_score  # Track score display state

    print("Initializing game engine...")
    
    try:
        # Get engine path from config if not specified
        engine_path = engine_path or config.get('engine.path')
        
        # Initialize engine first to download/test binary before asking for difficulty
        temp_engine = PikafishEngine(engine_path, difficulty=None)
        temp_engine.quit()  # Close the temporary engine
        print("Engine initialized successfully!")
        
    except Exception as e:
        logger.error(f"Engine initialization error: {e}")
        print(f"Error initializing engine: {e}")
        raise

    # Handle difficulty parameters
    if difficulty is not None and (depth is not None or time_limit_ms is not None):
        raise ValueError("Cannot specify both difficulty and custom parameters (depth/time_limit_ms)")
    
    if depth is not None or time_limit_ms is not None:
        # Create custom difficulty from parameters
        if depth is None:
            raise ValueError("Depth must be specified when using custom difficulty")
        
        difficulty = create_custom_difficulty(
            depth=depth,
            time_limit_ms=time_limit_ms
        )
    elif difficulty is None:
        # Try to use default difficulty from config
        default_level = config.get_required('game.default_difficulty')
        difficulty_config = config.get_difficulty(default_level)
        if difficulty_config:
            from .difficulty import DifficultyLevel
            difficulty = DifficultyLevel(
                name=difficulty_config['name'],
                description=difficulty_config['description'],
                depth=difficulty_config['depth'],
                time_limit_ms=difficulty_config.get('time_limit_ms'),
                uci_options=difficulty_config.get('uci_options', {})
            )
            print(f"Using default difficulty level {default_level} from configuration")
        else:
            # Fall back to creating a basic difficulty
            difficulty = create_custom_difficulty(depth=5, time_limit_ms=1000)
            print("Using fallback difficulty: Medium")

    print(f"\nStarting game with difficulty: {difficulty.name}")
    if difficulty.time_limit_ms is not None:
        print(f"AI will think for up to {difficulty.time_limit_ms/1000:.1f} seconds per move")
    else:
        print(f"AI will search to depth {difficulty.depth}")
    
    if score_display_enabled:
        print("Score display is enabled. Use 's' to toggle score display during the game.")
    else:
        print("Score display is disabled. Use 's' to toggle score display during the game.")
    
    try:
        engine = PikafishEngine(engine_path, difficulty=difficulty)
        print("Engine initialized successfully!")
        
        # Ensure output is flushed before prompting for input
        sys.stdout.flush()
        print("\nChoose your side ([r]ed / [b]lack): ", end="", flush=True)
        side_choice = input().strip().lower()
        human_is_red = side_choice != "b"
        
        logger.info(f"Human playing as {'Red' if human_is_red else 'Black'}")
        engine.new_game()

        while True:
            print(render(board.ascii()))
            
            # Display score if enabled
            if score_display_enabled:
                _display_position_score(engine, board)
            
            # Check if game is over before each turn
            # First check for king capture (immediate game end)
            current_fen = board.board_to_fen()
            if 'k' not in current_fen and 'K' not in current_fen:
                print(f"\nGame Over: Both kings missing!")
                break
            elif 'k' not in current_fen:
                print(f"\nGame Over: Red wins! Black king captured.")
                break
            elif 'K' not in current_fen:
                print(f"\nGame Over: Black wins! Red king captured.")
                break
            
            # Then check for other game end conditions
            is_over, reason = engine.is_game_over(current_fen, board.move_history)
            if is_over:
                print(f"\nGame Over: {reason}")
                break
            
            is_red_turn = len(board.move_history) % 2 == 0
            human_turn = (human_is_red and is_red_turn) or (not human_is_red and not is_red_turn)
            if human_turn:
                move = _prompt_user_move()
                if move is None:
                    break
                
                # Handle hint request
                if move.startswith("HINT:"):
                    try:
                        num_hints = int(move.split(":")[1])
                        _display_hints(engine, board, human_is_red, max_moves=num_hints)
                    except (ValueError, IndexError):
                        # Use default from config
                        default_hints = config.get_required('hints.default_count')
                        _display_hints(engine, board, human_is_red, max_moves=default_hints)
                    continue
                
                # Handle score toggle
                if move == "SCORE":
                    score_display_enabled = not score_display_enabled
                    status = "enabled" if score_display_enabled else "disabled"
                    print(f"Score display {status}.")
                    continue
                
                # Convert move to engine format for validation
                engine_move = board._convert_to_engine_format(move)
                logger.debug(f"Testing move {move} (engine format: {engine_move})")
                
                # First check if the move is legal using the engine
                is_legal = engine.is_move_legal(board.board_to_fen(), board.move_history, engine_move)
                logger.debug(f"Engine says move is legal: {is_legal}")
                
                if not is_legal:
                    print(f"Illegal move: {move} - This move violates xiangqi rules!")
                    continue
                    
                try:
                    board.push_move(move)
                except ValueError as e:
                    print(f"Invalid move: {e}")
                    continue
            else:
                logger.info(f"Engine thinking ({difficulty.name})...")
                best = engine.best_move(board.board_to_fen(), board.move_history)
                display_move = board._convert_from_engine_format(best)
                print(f"Engine plays {display_move}")
                board.push_move(display_move)
    except Exception as e:
        logger.error(f"Game error: {e}")
        print(f"Error starting game: {e}")
        raise
    finally:
        try:
            engine.quit()
        except (NameError, AttributeError):
            # Engine wasn't created successfully
            pass


def _prompt_user_move() -> Optional[str]:
    """Prompt until a move string is received or the user quits."""
    config = get_config()
    prompt_style = config.get_required('ui.prompt_style')
    default_hints = config.get_required('hints.default_count')
    
    while True:
        raw = input(prompt_style).strip().lower()
        if raw in {"quit", "exit", "q"}:
            return None
        if raw in {"h", "help", "hint"}:
            return f"HINT:{default_hints}"  # Use config default
        if raw.startswith("hint "):
            # Parse "hint n" format
            parts = raw.split()
            if len(parts) == 2:
                try:
                    num_hints = int(parts[1])
                    max_hints = config.get_required('hints.max_count')
                    if 1 <= num_hints <= max_hints:
                        return f"HINT:{num_hints}"
                    else:
                        print(f"Please specify a number between 1 and {max_hints} for hints.")
                        continue
                except ValueError:
                    print("Invalid number format. Use 'hint 5' to get 5 hints.")
                    continue
        if raw in {"s", "score"}:
            return "SCORE"  # Special return value for score toggle
        if len(raw) == 4 and all(ch.isalnum() for ch in raw):
            return raw
        print("Please enter moves like '1013' (file1-rank0 to file1-rank3), 'h' or 'hint N' for hints, 's' for score toggle, or 'quit' to exit.")


def _display_hints(engine: PikafishEngine, board: XiangqiBoard, human_is_red: bool, max_moves: int = 3) -> None:
    """Display the top move suggestions from the engine."""
    config = get_config()
    show_hint_scores = config.get_required('hints.show_scores')
    
    try:
        print(f"\nGetting top {max_moves} hints from engine...")
        candidate_moves = engine.get_candidate_moves(board.board_to_fen(), board.move_history, max_moves=max_moves)
        
        if not candidate_moves:
            print("No hints available at this position.")
            return
        
        print(f"\nTop {len(candidate_moves)} move suggestions:")
        for i, (engine_move, score) in enumerate(candidate_moves, 1):
            try:
                # Convert engine move to display format
                display_move = board._convert_from_engine_format(engine_move)
                
                if show_hint_scores:
                    # Format the score for display
                    if score > 9000:
                        score_str = f"Mate in {10000 - score}"
                    elif score < -9000:
                        score_str = f"Mated in {-10000 - score}"
                    else:
                        score_str = f"{score:+d} cp"
                    
                    print(f"  {i}. {display_move} ({score_str})")
                else:
                    print(f"  {i}. {display_move}")
            except Exception as e:
                # If conversion fails, show the raw engine move
                if show_hint_scores:
                    print(f"  {i}. {engine_move} (evaluation: {score:+d})")
                else:
                    print(f"  {i}. {engine_move}")
    
    except Exception as e:
        print(f"Error getting hints: {e}")
        print("Hint feature temporarily unavailable.")


def _display_position_score(engine: PikafishEngine, board: XiangqiBoard) -> None:
    """Display the current position evaluation score."""
    try:
        # Get the best move with evaluation
        candidate_moves = engine.get_candidate_moves(board.board_to_fen(), board.move_history, max_moves=1)
        
        if not candidate_moves:
            print("Position evaluation unavailable.")
            return
        
        _, score = candidate_moves[0]
        
        # Format the score for display (simple centipawn format)
        if score > 9000:
            score_str = f"Mate in {10000 - score} for Red"
        elif score < -9000:
            score_str = f"Mate in {-10000 - score} for Black"
        else:
            if score > 0:
                score_str = f"Red +{score} cp"
            elif score < 0:
                score_str = f"Black +{abs(score)} cp"
            else:
                score_str = "Even position"
        
        print(f"Position evaluation: {score_str}")
    
    except Exception as e:
        print(f"Error getting position evaluation: {e}")