from __future__ import annotations

import sys
import time
from typing import Optional, List, NamedTuple
from colorama import Fore, Style

from .board import XiangqiBoard
from .engine import PikafishEngine
from .ui import render
from .difficulty import DifficultyLevel, create_custom_difficulty
from .logging_config import get_logger
from .config import get_config, ConfigError


PROMPT = "(pikafish) > "


class MoveHistoryEntry(NamedTuple):
    """Represents a move in the game history with its evaluation."""
    move: str
    score: int
    is_red_move: bool
    move_number: int


def _clear_screen() -> None:
    """Clear the terminal screen and move cursor to top-left."""
    print("\033[H\033[J", end="", flush=True)


def _transform_move_for_black_player(move: str) -> str:
    """Transform move coordinates from Black player's flipped perspective to internal board coordinates.
    
    When playing as Black, the board is flipped so Black's pieces are at the bottom.
    This means the coordinates the player sees need to be transformed:
    - Files: 1→9, 2→8, 3→7, 4→6, 5→5, 6→4, 7→3, 8→2, 9→1
    - Ranks: 0→9, 1→8, 2→7, 3→6, 4→5, 5→4, 6→3, 7→2, 8→1, 9→0
    """
    if len(move) != 4:
        return move  # Invalid format, return as-is
    
    try:
        # Parse the move from Black player's perspective
        src_file = int(move[0])  # 1-9
        src_rank = int(move[1])  # 0-9
        dst_file = int(move[2])  # 1-9
        dst_rank = int(move[3])  # 0-9
        
        # Transform coordinates from flipped perspective to internal representation
        # Files: flip horizontally (1↔9, 2↔8, etc.)
        transformed_src_file = 10 - src_file  # 1→9, 2→8, ..., 9→1
        transformed_dst_file = 10 - dst_file
        
        # Ranks: flip vertically (0↔9, 1↔8, etc.)
        transformed_src_rank = 9 - src_rank  # 0→9, 1→8, ..., 9→0
        transformed_dst_rank = 9 - dst_rank
        
        # Return the transformed move
        return f"{transformed_src_file}{transformed_src_rank}{transformed_dst_file}{transformed_dst_rank}"
        
    except (ValueError, IndexError):
        return move  # Invalid format, return as-is


def _display_game_state(board: XiangqiBoard, engine: PikafishEngine, score_display_enabled: bool, 
                       human_is_red: bool, status_message: str = "", last_move: str = "", 
                       move_history: Optional[List[MoveHistoryEntry]] = None, current_score: Optional[int] = None) -> None:
    """Display the current game state with board, score history, and turn information."""
    _clear_screen()
    
    # Display the board with move highlighting, flipped if human plays as Black
    print(render(board.ascii(), last_move=last_move, flip_board=not human_is_red))
    
    # Display score history if enabled
    if score_display_enabled and move_history:
        _display_score_history(engine, board, move_history, current_score, human_is_red)
    
    # Display turn information
    is_red_turn = len(board.move_history) % 2 == 0
    human_turn = (human_is_red and is_red_turn) or (not human_is_red and not is_red_turn)
    
    if human_turn:
        side_name = "Red" if is_red_turn else "Black"
        print(f"\n{side_name} to move (You)")
    else:
        side_name = "Red" if is_red_turn else "Black"
        print(f"\n{side_name} to move (Engine)")
    
    # Display last move information
    if last_move:
        print(f"Last move: {last_move}")
    
    # Display any status message
    if status_message:
        print(f"\n{status_message}")


def _display_score_history(engine: PikafishEngine, board: XiangqiBoard, move_history: List[MoveHistoryEntry], 
                          current_score: Optional[int] = None, human_is_red: bool = True) -> None:
    """Display the move history with scores, color-coded by player."""
    try:
        config = get_config()
        history_length_raw = config.get_required('game.move_history_length')
        history_length = int(history_length_raw) if isinstance(history_length_raw, (int, float, str)) else 6
        
        # Use cached score if provided, otherwise calculate it
        if current_score is None:
            current_score = engine.get_position_evaluation(board.board_to_fen(), board.move_history)
        
        # Flip scores for Black player perspective
        display_current_score = current_score if human_is_red else -current_score
        
        # Format current score
        if display_current_score > 9000:
            player_name = "Red" if human_is_red else "Black"
            current_str = f"Mate in {10000 - display_current_score} for {player_name}"
        elif display_current_score < -9000:
            opponent_name = "Black" if human_is_red else "Red"
            current_str = f"Mate in {-10000 - display_current_score} for {opponent_name}"
        else:
            if display_current_score > 0:
                current_str = f"+{display_current_score} cp"
            elif display_current_score < 0:
                current_str = f"{display_current_score} cp"
            else:
                current_str = "0 cp"
        
        print(f"Current position: {current_str}")
        
        # Display move history if we have moves
        if move_history:
            print(f"\nLast {min(len(move_history), history_length)} moves:")
            
            # Show the last N moves in reverse order (most recent first)
            recent_moves = move_history[-history_length:] if len(move_history) > history_length else move_history
            
            for entry in reversed(recent_moves):
                # Flip score for Black player perspective
                display_score = entry.score if human_is_red else -entry.score
                
                # Format the score
                if display_score > 9000:
                    player_name = "Red" if human_is_red else "Black"
                    score_str = f"Mate in {10000 - display_score} for {player_name}"
                elif display_score < -9000:
                    opponent_name = "Black" if human_is_red else "Red"
                    score_str = f"Mate in {-10000 - display_score} for {opponent_name}"
                else:
                    if display_score > 0:
                        score_str = f"+{display_score} cp"
                    elif display_score < 0:
                        score_str = f"{display_score} cp"
                    else:
                        score_str = "0 cp"
                
                # Color-code by player
                if entry.is_red_move:
                    color = Fore.RED
                    player = "Red"
                else:
                    color = Fore.GREEN  
                    player = "Black"
                
                print(f"  {entry.move_number}. {color}{player}{Style.RESET_ALL}: {entry.move} {score_str}")
    
    except Exception as e:
        print(f"Error displaying score history: {e}")


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
        show_score = bool(config.get_required('game.show_score'))
    
    score_display_enabled = show_score  # Track score display state

    print("Initializing game engine...")
    
    try:
        # Get engine path from config if not specified
        if engine_path is None:
            engine_path_config = config.get('engine.path')
            engine_path = str(engine_path_config) if engine_path_config is not None else None
        
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
        default_level_raw = config.get_required('game.default_difficulty')
        default_level = str(default_level_raw) if default_level_raw is not None else "1"
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
        if not human_is_red:
            print("Playing as Black - board will be flipped to show Black pieces at the bottom.")
        else:
            print("Playing as Red - board will show Red pieces at the bottom.")
        engine.new_game()

        # Track move history with scores for display
        move_history: List[MoveHistoryEntry] = []
        last_move = ""
        cached_score: Optional[int] = None  # Cache current position score

        while True:
            # Calculate score only once per position if score display is enabled
            if score_display_enabled and cached_score is None:
                raw_score = engine.get_position_evaluation(board.board_to_fen(), board.move_history)
                # Convert to Red's perspective
                is_red_turn_now = len(board.move_history) % 2 == 0
                if is_red_turn_now:
                    cached_score = raw_score
                else:
                    cached_score = -raw_score
            
            _display_game_state(board, engine, score_display_enabled, human_is_red, 
                              last_move=last_move, move_history=move_history, current_score=cached_score)
            
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
                        default_hints_raw = config.get_required('hints.default_count')
                        default_hints = int(default_hints_raw) if isinstance(default_hints_raw, (int, float, str)) else 3
                        _display_hints(engine, board, human_is_red, max_moves=default_hints)
                    
                    # Pause to let user read hints, then continue
                    input("\nPress Enter to continue...")
                    continue
                
                # Handle score toggle
                if move == "SCORE":
                    score_display_enabled = not score_display_enabled
                    status = "enabled" if score_display_enabled else "disabled"
                    # Recalculate cached score if enabling score display
                    if score_display_enabled and cached_score is None:
                        raw_score = engine.get_position_evaluation(board.board_to_fen(), board.move_history)
                        is_red_turn_now = len(board.move_history) % 2 == 0
                        cached_score = raw_score if is_red_turn_now else -raw_score
                    _display_game_state(board, engine, score_display_enabled, human_is_red, 
                                       f"Score display {status}.", last_move=last_move, 
                                       move_history=move_history, current_score=cached_score)
                    time.sleep(1)  # Brief pause to show the status
                    continue
                
                # Transform move coordinates if playing as Black (board is flipped)
                if not human_is_red:
                    transformed_move = _transform_move_for_black_player(move)
                    logger.debug(f"Black player move {move} transformed to {transformed_move}")
                    move = transformed_move
                
                # Convert move to engine format for validation
                engine_move = board._convert_to_engine_format(move)
                logger.debug(f"Testing move {move} (engine format: {engine_move})")
                
                # First check if the move is legal using the engine
                is_legal = engine.is_move_legal(board.board_to_fen(), board.move_history, engine_move)
                logger.debug(f"Engine says move is legal: {is_legal}")
                
                if not is_legal:
                    _display_game_state(board, engine, score_display_enabled, human_is_red, 
                                       f"Illegal move: {move} - This move violates xiangqi rules!",
                                       last_move=last_move, move_history=move_history, current_score=cached_score)
                    time.sleep(1.5)  # Brief pause to show the error
                    continue
                    
                try:
                    board.push_move(move)
                    last_move = move  # Update last move
                    cached_score = None  # Invalidate cache after move
                    
                    # Get score after the move for history tracking
                    if score_display_enabled:
                        # Determine whose move this was (Red or Black)
                        is_red_move = human_is_red  # This was a human move
                        
                        # Get the score from engine (from perspective of current turn)
                        raw_score = engine.get_position_evaluation(board.board_to_fen(), board.move_history)
                        
                        # Convert to Red's perspective
                        is_red_turn_now = len(board.move_history) % 2 == 0  # Whose turn is it now?
                        if is_red_turn_now:
                            # Red's turn now, score is from Red's perspective already
                            red_perspective_score = raw_score
                        else:
                            # Black's turn now, score is from Black's perspective, so negate it
                            red_perspective_score = -raw_score
                        
                        move_history.append(MoveHistoryEntry(move, red_perspective_score, is_red_move, len(move_history) + 1))
                        cached_score = red_perspective_score  # Cache the new score
                except ValueError as e:
                    _display_game_state(board, engine, score_display_enabled, human_is_red, 
                                       f"Invalid move: {e}", last_move=last_move, 
                                       move_history=move_history, current_score=cached_score)
                    time.sleep(1.5)  # Brief pause to show the error
                    continue
            else:
                logger.info(f"Engine thinking ({difficulty.name})...")
                # Show "thinking" message using cached score (no recalculation)
                _display_game_state(board, engine, score_display_enabled, human_is_red, 
                                   f"Engine thinking ({difficulty.name})...",
                                   last_move=last_move, move_history=move_history, current_score=cached_score)
                
                best = engine.best_move(board.board_to_fen(), board.move_history)
                display_move = board._convert_from_engine_format(best)
                board.push_move(display_move)
                last_move = display_move  # Update last move
                cached_score = None  # Invalidate cache after move
                
                # Get score after AI move for history tracking
                if score_display_enabled:
                    # Determine whose move this was (Red or Black)
                    is_red_move = not human_is_red  # This was an AI move
                    
                    # Get the score from engine (from perspective of current turn)
                    raw_score = engine.get_position_evaluation(board.board_to_fen(), board.move_history)
                    
                    # Convert to Red's perspective
                    is_red_turn_now = len(board.move_history) % 2 == 0  # Whose turn is it now?
                    if is_red_turn_now:
                        # Red's turn now, score is from Red's perspective already
                        red_perspective_score = raw_score
                    else:
                        # Black's turn now, score is from Black's perspective, so negate it
                        red_perspective_score = -raw_score
                    
                    move_history.append(MoveHistoryEntry(display_move, red_perspective_score, is_red_move, len(move_history) + 1))
                    cached_score = red_perspective_score  # Cache the new score
                
                # Show engine move with highlighting using cached score (no recalculation)
                _display_game_state(board, engine, score_display_enabled, human_is_red, 
                                   f"Engine plays {display_move}", 
                                   last_move=last_move, move_history=move_history, current_score=cached_score)
                
                # Use configurable pause duration
                pause_duration_raw = config.get_required('ui.ai_move_pause_seconds')
                pause_duration = float(pause_duration_raw) if isinstance(pause_duration_raw, (int, float, str)) else 1.0
                time.sleep(pause_duration)
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
    default_hints_raw = config.get_required('hints.default_count')
    default_hints = int(default_hints_raw) if isinstance(default_hints_raw, (int, float, str)) else 3
    
    while True:
        raw = input(str(prompt_style)).strip().lower()
        if raw in {"quit", "exit", "q"}:
            return None
        if raw in {"h", "help", "hint"}:
            return f"HINT:{default_hints}"
        if raw.startswith("hint "):
            # Parse "hint n" format
            parts = raw.split()
            if len(parts) == 2:
                try:
                    num_hints = int(parts[1])
                    max_hints_raw = config.get_required('hints.max_count')
                    max_hints = int(max_hints_raw) if isinstance(max_hints_raw, (int, float, str)) else 10
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
        print("Note: If playing as Black, enter coordinates as you see them on the flipped board.")


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
                
                # If the human plays as Black, convert the move to the flipped
                # coordinate system so that it matches what the player sees on
                # screen.  The same self-inverse transformation that we use to
                # convert input moves can be reused here.
                if not human_is_red:
                    display_move = _transform_move_for_black_player(display_move)

                # Adjust score sign so positive values always favour the
                # side the human is playing.
                display_score = score if human_is_red else -score

                if show_hint_scores:
                    # Format the score for display
                    if display_score > 9000:
                        score_str = f"Mate in {10000 - display_score}"
                    elif display_score < -9000:
                        score_str = f"Mated in {-10000 - display_score}"
                    else:
                        score_str = f"{display_score:+d} cp"

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


