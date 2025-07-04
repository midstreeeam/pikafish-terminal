import subprocess
import threading
import queue
import os
import shutil
import time
from typing import List, Optional, Tuple, Dict

from .downloader import get_pikafish_path
from .difficulty import DifficultyLevel
from .logging_config import get_logger
from .config import get_config


class PikafishEngine:
    """Lightweight wrapper around a Pikafish UCI engine process."""

    def __init__(self, path: Optional[str] = None, difficulty: Optional[DifficultyLevel] = None, depth: Optional[int] = None):
        self.logger = get_logger('pikafish.engine')
        
        # Initialize attributes first to avoid AttributeError in __del__ if initialization fails
        self._proc: Optional[subprocess.Popen] = None
        self._stdout_queue: "queue.Queue[str]" = queue.Queue()
        
        if path is None:
            try:
                path = str(get_pikafish_path())
            except (ImportError, FileNotFoundError, ConnectionError, OSError) as e:
                # Only catch recoverable errors, let critical errors (like RuntimeError for incompatibility) propagate
                path = "pikafish"
        
        self.path: str = path
        
        if difficulty is not None:
            self.difficulty = difficulty
            self.depth = difficulty.depth
            self.time_limit_ms = difficulty.time_limit_ms
            self.uci_options = difficulty.uci_options
        else:
            self.depth = depth if depth is not None else 12
            self.time_limit_ms = None
            self.uci_options = {}
            
        self._start()

    def _start(self) -> None:
        """Launch the engine process and prepare it for a new game."""
        if not os.path.isfile(self.path) and not shutil.which(self.path):
            try:
                pikafish_path = get_pikafish_path()
                self.path = str(pikafish_path)
            except Exception as e:
                raise FileNotFoundError(
                    f"Could not find Pikafish binary '{self.path}' and failed to download it automatically. "
                    f"Error: {e}. Make sure it is on your $PATH or pass an explicit path."
                )
        
        self.logger.info("Starting Pikafish engine...")
        try:
            self._proc = subprocess.Popen(
                [self.path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
            )
            self._reader_thread = threading.Thread(target=self._reader, daemon=True)
            self._reader_thread.start()
            
            self.logger.info("Initializing UCI protocol...")
            self._cmd("uci")
            self._wait_for("uciok", timeout=15)
            
            # Set any UCI options
            for option, value in self.uci_options.items():
                self._cmd(f"setoption name {option} value {value}")
            
            self._ready()
            self.logger.info("Engine ready!")
            
        except Exception as e:
            if self._proc:
                self._proc.terminate()
            raise RuntimeError(f"Failed to initialize Pikafish engine: {e}")

    def _reader(self) -> None:
        """Background thread that continuously reads stdout from the engine."""
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            self._stdout_queue.put(line.strip())

    def _cmd(self, text: str) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(text + "\n")
        self._proc.stdin.flush()

    def _wait_for(self, token: str, timeout: int = 10) -> None:
        """Wait for a specific token in engine output with timeout."""
        start_time = time.time()
        while True:
            try:
                line = self._stdout_queue.get(timeout=1)
                self.logger.debug(f"Engine output: {line}")
                if token in line:
                    return
            except queue.Empty:
                if time.time() - start_time > timeout:
                    raise RuntimeError(f"Engine did not respond with '{token}' within {timeout} seconds")
                continue

    def _ready(self) -> None:
        self._cmd("isready")
        self._wait_for("readyok")

    def new_game(self) -> None:
        self._cmd("ucinewgame")
        self._ready()

    def is_move_legal(self, fen: str, moves: List[str], move_to_test: str) -> bool:
        """Check if a move is legal by getting all legal moves from current position."""
        try:
            # Clear the queue first
            while not self._stdout_queue.empty():
                try:
                    self._stdout_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Set the current position (without the test move)
            pos_cmd = f"position fen {fen}"
            if moves:
                pos_cmd += " moves " + " ".join(moves)
            
            self.logger.debug(f"Setting current position: {pos_cmd}")
            self._cmd(pos_cmd)
            
            # Use perft to get all legal moves from this position
            self._cmd("go perft 1")
            
            start_time = time.time()
            legal_moves = set()
            
            while True:
                try:
                    line = self._stdout_queue.get(timeout=3)
                    self.logger.debug(f"Engine response: {line}")
                    
                    # Look for move lines in perft output (format: "move: count")
                    if ": " in line and not line.startswith("info") and not line.startswith("Nodes"):
                        move = line.split(":")[0].strip()
                        if len(move) >= 4:  # Valid move format
                            legal_moves.add(move)
                    
                    # Alternative: if perft doesn't work, fall back to search
                    elif line.startswith("Nodes searched:") or "illegal" in line.lower():
                        break
                        
                except queue.Empty:
                    if time.time() - start_time > 4:
                        self.logger.debug("Engine timeout during perft")
                        break
            
            # If perft didn't work, try alternative method
            if not legal_moves:
                return self._test_with_search(fen, moves, move_to_test)
            
            is_legal = move_to_test in legal_moves
            self.logger.debug(f"Legal moves from perft: {legal_moves}")
            self.logger.debug(f"Testing move {move_to_test}: {is_legal}")
            return is_legal
            
        except Exception as e:
            self.logger.debug(f"Exception in move validation: {e}")
            return False
    
    def _test_with_search(self, fen: str, moves: List[str], move_to_test: str) -> bool:
        """Fallback: test move by doing a shallow search and checking if move appears."""
        try:
            # Clear the queue
            while not self._stdout_queue.empty():
                try:
                    self._stdout_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Set position
            pos_cmd = f"position fen {fen}"
            if moves:
                pos_cmd += " moves " + " ".join(moves)
            
            self._cmd(pos_cmd)
            self._cmd("go depth 2")  # Shallow search to get move info
            
            start_time = time.time()
            legal_moves = set()
            
            while True:
                try:
                    line = self._stdout_queue.get(timeout=3)
                    
                    # Extract moves from search info lines
                    if line.startswith("info") and "pv" in line:
                        parts = line.split()
                        if "pv" in parts:
                            pv_idx = parts.index("pv")
                            if pv_idx + 1 < len(parts):
                                legal_moves.add(parts[pv_idx + 1])
                    
                    elif line.startswith("bestmove"):
                        parts = line.split()
                        if len(parts) > 1 and parts[1] not in ["(none)", "0000"]:
                            legal_moves.add(parts[1])
                        break
                        
                except queue.Empty:
                    if time.time() - start_time > 4:
                        break
            
            is_legal = move_to_test in legal_moves
            self.logger.debug(f"Legal moves from search: {legal_moves}")
            self.logger.debug(f"Testing move {move_to_test}: {is_legal}")
            return is_legal
            
        except Exception as e:
            self.logger.debug(f"Exception in search fallback: {e}")
            return False

    def best_move(self, fen: str, moves: List[str]) -> str:
        """Return engine best move in long algebraic (e.g. a0a3) notation."""
        pos_cmd = f"position fen {fen}"
        if moves:
            pos_cmd += " moves " + " ".join(moves)
        self._cmd(pos_cmd)
        
        if self.time_limit_ms is not None:
            go_cmd = f"go movetime {self.time_limit_ms}"
        else:
            go_cmd = f"go depth {self.depth}"
        
        self._cmd(go_cmd)
            
        timeout = (self.time_limit_ms / 1000 + 5) if self.time_limit_ms else 30
        start_time = time.time()
        
        while True:
            try:
                line = self._stdout_queue.get(timeout=1)
                if line.startswith("bestmove"):
                    best_move_result = line.split()[1]
                    return best_move_result
            except queue.Empty:
                if time.time() - start_time > timeout:
                    raise RuntimeError(f"Engine did not respond within {timeout} seconds")

    def get_candidate_moves(self, fen: str, moves: List[str], max_moves: int = 3) -> List[Tuple[str, int]]:
        """Get top candidate moves with their scores for hints.
        
        Returns:
            List of (move, score) tuples, sorted by score (best first)
        """
        config = get_config()
        
        # Clear the queue first
        while not self._stdout_queue.empty():
            try:
                self._stdout_queue.get_nowait()
            except queue.Empty:
                break
        
        pos_cmd = f"position fen {fen}"
        if moves:
            pos_cmd += " moves " + " ".join(moves)
        self._cmd(pos_cmd)
        
        # Try to use MultiPV (Multiple Principal Variations) for better candidate moves
        # This tells the engine to show multiple best moves
        max_moves = min(max_moves, config.get_required('hints.max_count'))  # Use config limit
        self._cmd(f"setoption name MultiPV value {max_moves}")
        
        # Use config values for hint calculation (independent of engine difficulty)
        hint_depth_config = config.get_required('hints.depth')
        hint_time_config = config.get_required('hints.time_limit_ms')
        
        # Use hint-specific settings, not limited by engine difficulty
        hint_depth = int(hint_depth_config)
        hint_time = int(hint_time_config)
        
        # Always use both depth and time for hints to ensure proper calculation
        go_cmd = f"go depth {hint_depth} movetime {hint_time}"
        
        self._cmd(go_cmd)
        
        candidate_moves: Dict[str, int] = {}  # move -> score
        move_ranks: Dict[str, int] = {}  # move -> rank (for MultiPV)
        timeout_config = config.get_required('engine.move_timeout')
        timeout = int(timeout_config) // 6  # Use fraction of move timeout for hints
        start_time = time.time()
        
        while True:
            try:
                line = self._stdout_queue.get(timeout=0.5)
                
                # Parse "info" lines that contain move evaluations
                if line.startswith("info") and "pv" in line and "score" in line:
                    parts = line.split()
                    try:
                        # Check if this is a MultiPV line
                        multipv_rank = 1  # Default rank
                        if "multipv" in parts:
                            multipv_idx = parts.index("multipv")
                            if multipv_idx + 1 < len(parts):
                                multipv_rank = int(parts[multipv_idx + 1])
                        
                        # Find the principal variation (pv) move
                        pv_idx = parts.index("pv")
                        if pv_idx + 1 < len(parts):
                            move = parts[pv_idx + 1]
                            
                            # Find the score
                            score_idx = parts.index("score")
                            if score_idx + 2 < len(parts):
                                score_type = parts[score_idx + 1]  # "cp" or "mate"
                                score_value = int(parts[score_idx + 2])
                                
                                # Convert mate scores to very high/low values
                                if score_type == "mate":
                                    if score_value > 0:
                                        score = 10000 - score_value  # Mate in N moves
                                    else:
                                        score = -10000 - score_value  # Mated in N moves
                                else:
                                    score = score_value  # Centipawn score
                                
                                # Store the move and its rank
                                candidate_moves[move] = score
                                move_ranks[move] = multipv_rank
                                
                    except (ValueError, IndexError):
                        continue
                
                elif line.startswith("bestmove"):
                    # Final best move
                    parts = line.split()
                    if len(parts) > 1 and parts[1] not in ["(none)", "0000"]:
                        # Ensure the best move is included
                        if parts[1] not in candidate_moves:
                            candidate_moves[parts[1]] = 0  # Default score if not found
                            move_ranks[parts[1]] = 1
                    break
                    
            except queue.Empty:
                if time.time() - start_time > timeout:
                    break
        
        # Reset MultiPV to 1 after getting hints
        self._cmd("setoption name MultiPV value 1")
        
        # Sort by MultiPV rank first (if available), then by score
        if move_ranks and candidate_moves:
            # Sort by MultiPV rank (lower rank = better move)
            sorted_moves = sorted(candidate_moves.items(), 
                                key=lambda x: (move_ranks.get(x[0], 999), -x[1]))
        elif candidate_moves:
            # Fall back to sorting by score only
            sorted_moves = sorted(candidate_moves.items(), key=lambda x: x[1], reverse=True)
        else:
            # No moves found
            return []
        
        return sorted_moves[:max_moves]

    def get_position_evaluation(self, fen: str, moves: List[str]) -> int:
        """Get position evaluation score using configured scoring settings.
        
        Returns:
            Position evaluation score in centipawns (positive = good for Red/White)
        """
        config = get_config()
        
        # Clear the queue first
        while not self._stdout_queue.empty():
            try:
                self._stdout_queue.get_nowait()
            except queue.Empty:
                break
        
        pos_cmd = f"position fen {fen}"
        if moves:
            pos_cmd += " moves " + " ".join(moves)
        self._cmd(pos_cmd)
        
        # Use separate scoring configuration for more precise evaluation
        scoring_depth = config.get_required('scoring.depth')
        scoring_time = config.get_required('scoring.time_limit_ms')
        
        # Use the configured scoring settings
        go_cmd = f"go depth {scoring_depth} movetime {scoring_time}"
        self._cmd(go_cmd)
        
        score = 0  # Default score
        timeout_config = config.get_required('engine.move_timeout')
        timeout = int(timeout_config) // 4  # Use fraction of move timeout for scoring
        start_time = time.time()
        
        while True:
            try:
                line = self._stdout_queue.get(timeout=0.5)
                
                # Parse "info" lines that contain evaluations
                if line.startswith("info") and "score" in line:
                    parts = line.split()
                    try:
                        # Find the score
                        score_idx = parts.index("score")
                        if score_idx + 2 < len(parts):
                            score_type = parts[score_idx + 1]  # "cp" or "mate"
                            score_value = int(parts[score_idx + 2])
                            
                            # Convert mate scores to very high/low values
                            if score_type == "mate":
                                if score_value > 0:
                                    score = 10000 - score_value  # Mate in N moves
                                else:
                                    score = -10000 - score_value  # Mated in N moves
                            else:
                                score = score_value  # Centipawn score
                                
                    except (ValueError, IndexError):
                        continue
                
                elif line.startswith("bestmove"):
                    # Analysis complete
                    break
                    
            except queue.Empty:
                if time.time() - start_time > timeout:
                    break
        
        return score

    def is_game_over(self, fen: str, moves: List[str]) -> Tuple[bool, str]:
        """Check if the game is over (checkmate, stalemate, etc). Returns (is_over, reason)."""
        try:
            # Clear the queue first
            while not self._stdout_queue.empty():
                try:
                    self._stdout_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Set up the current position
            pos_cmd = f"position fen {fen}"
            if moves:
                pos_cmd += " moves " + " ".join(moves)
            
            self._cmd(pos_cmd)
            
            # Try a very shallow search to see if there are any legal moves
            self._cmd("go depth 1")
            
            import time
            start_time = time.time()
            found_move = False
            
            while True:
                try:
                    line = self._stdout_queue.get(timeout=2)
                    
                    if line.startswith("bestmove"):
                        parts = line.split()
                        if len(parts) > 1:
                            move = parts[1]
                            if move != "(none)" and move != "0000":
                                found_move = True
                        break
                        
                except queue.Empty:
                    if time.time() - start_time > 3:
                        break
            
            if not found_move:
                # No legal moves - could be checkmate or stalemate
                # For now, we'll just say the game is over
                return True, "No legal moves available (checkmate or stalemate)"
            
            return False, ""
                        
        except Exception as e:
            self.logger.debug(f"Exception in game over check: {e}")
            return False, ""

    def quit(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._cmd("quit")
                self._proc.communicate(timeout=1)
            except Exception:
                self._proc.kill()

    def __del__(self) -> None:
        self.quit()