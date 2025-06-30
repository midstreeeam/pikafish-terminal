from __future__ import annotations

import sys
from typing import Optional

from .board import XiangqiBoard
from .engine import PikafishEngine
from .ui import render
from .difficulty import prompt_difficulty_selection, DifficultyLevel
from .logging_config import get_logger


PROMPT = "(pikafish) > "


def play(engine_path: Optional[str] = None, difficulty: Optional[DifficultyLevel] = None) -> None:
    """Run an interactive terminal game of Xiangqi against Pikafish."""
    logger = get_logger('pikafish.game')
    board = XiangqiBoard()

    if difficulty is None:
        difficulty = prompt_difficulty_selection()

    print(f"\nStarting game with difficulty: {difficulty.name}")
    print(f"AI will think for up to {difficulty.time_limit_ms/1000:.1f} seconds per move")

    engine = PikafishEngine(engine_path, difficulty=difficulty)
    try:
        side_choice = input("\nChoose your side ([r]ed / [b]lack): ").strip().lower()
        human_is_red = side_choice != "b"
        engine.new_game()

        while True:
            print(render(board.ascii()))
            
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
    finally:
        engine.quit()


def _prompt_user_move() -> Optional[str]:
    """Prompt until a move string is received or the user quits."""
    while True:
        raw = input(PROMPT).strip().lower()
        if raw in {"quit", "exit", "q"}:
            return None
        if len(raw) == 4 and all(ch.isalnum() for ch in raw):
            return raw
        print("Please enter moves like '1013' (file1-rank0 to file1-rank3) or type 'quit' to exit.")