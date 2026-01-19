"""
Maia Worker Process - Standalone subprocess for Maia inference
Communicates via stdin/stdout to avoid DLL loading issues in multiprocessing

Uses the REAL Maia-1 (same as maiachess.com) via lc0 engine with Maia weights.
This is NOT the maia2 pip package - this is the actual Maia neural network.
"""
import sys
import json
import random
import os
import chess
import chess.engine


# =============================================================================
# RESEARCH-BASED THINKING TIME MODEL
# Based on analysis of 12+ million Lichess games and academic psychology research
# =============================================================================

# State tracking for move-to-move correlation
class ThinkTimeState:
    """Persistent state for realistic move correlation."""
    def __init__(self):
        self.previous_think_time = 1.5  # Default baseline
        self.consecutive_fast_moves = 0
        self.last_capture_square = None

# Global state (persists across moves within a game)
_think_state = ThinkTimeState()

def reset_think_state():
    """Reset state for a new game."""
    global _think_state
    _think_state = ThinkTimeState()


def _should_premove(
    move_count: int,
    is_recapture: bool,
    num_legal_moves: int,
    consecutive_fast: int
) -> bool:
    """
    Determine if this move should be a premove.

    Research: 21.26% of moves are premoves overall, but varies by context.
    """
    base_premove_prob = 0.2126  # 21.26% from Lichess research

    # Adjust for game phase
    if move_count <= 5:
        # Opening moves are often book/premoved
        phase_modifier = 1.5
    elif move_count <= 10:
        phase_modifier = 1.2
    elif move_count <= 35:
        # Middlegame: fewer premoves
        phase_modifier = 0.5
    else:
        # Endgame: more premoves (time pressure simulation)
        phase_modifier = 1.3

    # Recaptures are very often premoved
    if is_recapture:
        phase_modifier *= 2.5

    # Fewer legal moves = higher premove probability
    if num_legal_moves == 1:
        phase_modifier *= 3.0  # Forced move
    elif num_legal_moves <= 3:
        phase_modifier *= 1.5

    # Consecutive fast moves increase premove likelihood (momentum)
    if consecutive_fast >= 2:
        phase_modifier *= 1.2
    if consecutive_fast >= 4:
        phase_modifier *= 1.3

    adjusted_prob = min(0.75, base_premove_prob * phase_modifier)

    return random.random() < adjusted_prob


def _generate_premove_time() -> float:
    """
    Generate time for a premove (near-instant).

    Human reaction time ~150ms plus network latency variance.
    """
    base_reaction = 0.15
    # Exponential tail for occasional slightly slower "premoves"
    variance = random.expovariate(10)  # Mean = 0.1s
    return base_reaction + min(variance, 0.4)  # Cap at ~550ms


def _get_phase_base_time(move_count: int) -> float:
    """
    Calculate base think time based on game phase.

    Research: Inverted U-shape with peak around moves 15-25.
    """
    import math

    if move_count <= 3:
        # Very early opening - often prepared
        return 0.5
    elif move_count <= 10:
        # Opening phase - moderate speed, gradually increasing
        progress = (move_count - 3) / 7
        return 0.5 + progress * 1.5  # 0.5s -> 2.0s
    elif move_count <= 20:
        # Rising to middlegame peak
        progress = (move_count - 10) / 10
        return 2.0 + math.sin(progress * math.pi / 2) * 2.0  # 2.0s -> 4.0s
    elif move_count <= 35:
        # Declining from peak
        progress = (move_count - 20) / 15
        return 4.0 - progress * 2.0  # 4.0s -> 2.0s
    else:
        # Endgame - faster play with exponential decay
        moves_into_endgame = move_count - 35
        decay = math.exp(-moves_into_endgame / 15)
        return max(0.8, 2.0 * decay)


def _get_complexity_factor(num_legal_moves: int, is_capture: bool, gives_check: bool) -> float:
    """
    Adjust think time based on position complexity.
    """
    import math

    # Legal moves as complexity proxy (sqrt relationship from research)
    if num_legal_moves <= 5:
        factor = 0.7
    elif num_legal_moves <= 15:
        factor = 0.85
    elif num_legal_moves <= 30:
        factor = 1.0
    elif num_legal_moves <= 45:
        factor = 1.15
    else:
        factor = 1.3

    # Captures and checks need verification
    if is_capture:
        factor *= 1.05
    if gives_check:
        factor *= 1.1

    return factor


def _get_variability_coeffs(elo: int) -> tuple:
    """
    Get ELO-based variability coefficients.

    Research formula: SD = a + b * Mean
    Low ELO (<1400):  a=0.1, b=0.91
    High ELO (>1900): a=0.6, b=1.36
    """
    if elo < 1400:
        return (0.1, 0.91)
    elif elo > 1900:
        return (0.6, 1.36)
    else:
        # Interpolate
        t = (elo - 1400) / 500
        a = 0.1 + t * 0.5
        b = 0.91 + t * 0.45
        return (a, b)


def _sample_log_normal(mean_time: float, elo: int) -> float:
    """
    Sample from log-normal distribution for heavy-tailed behavior.

    Research: Human thinking times are NOT Gaussian - they have long tails.
    """
    import math

    if mean_time <= 0:
        return 0.3

    # Get ELO-based variability
    a, b = _get_variability_coeffs(elo)

    # Calculate standard deviation: SD = a + b * Mean
    std_dev = a + b * mean_time

    # Coefficient of variation
    cv = std_dev / mean_time

    # Convert to log-normal parameters
    sigma_squared = math.log(1 + cv * cv)
    sigma = math.sqrt(sigma_squared)
    mu = math.log(mean_time) - sigma_squared / 2

    return random.lognormvariate(mu, sigma)


def calculate_think_time(
    board: chess.Board,
    move: chess.Move,
    move_count: int,
    num_legal_moves: int,
    elo: int = 1500,
    time_control: str = "blitz"
) -> float:
    """
    Calculate human-like thinking time based on 12M+ Lichess games research.

    Key research findings implemented:
    - 21.26% of moves are premoves (near-instant)
    - Distribution is log-normal (heavy-tailed), NOT Gaussian
    - Inverted U-shape: Opening fast, middlegame slow, endgame fast
    - Move-to-move correlation (AR(1) model, rho=0.4)
    - ELO-based variability: SD = a + b * Mean
    """
    global _think_state

    # Time control parameters
    time_scales = {"bullet": 0.4, "blitz": 1.0, "rapid": 2.5}
    min_times = {"bullet": 0.15, "blitz": 0.2, "rapid": 0.3}
    max_times = {"bullet": 5.0, "blitz": 12.0, "rapid": 30.0}

    time_scale = time_scales.get(time_control, 1.0)
    min_time = min_times.get(time_control, 0.2)
    max_time = max_times.get(time_control, 12.0)

    # Detect move characteristics
    is_recapture = False
    if board.move_stack:
        last_move = board.move_stack[-1]
        if board.is_capture(last_move) and move.to_square == last_move.to_square:
            is_recapture = True

    is_capture = board.is_capture(move)

    # Check if move gives check
    board.push(move)
    gives_check = board.is_check()
    board.pop()

    is_castling = board.is_castling(move)

    # === Step 1: Check for premove (21.26% base probability) ===
    if _should_premove(move_count, is_recapture, num_legal_moves, _think_state.consecutive_fast_moves):
        premove_time = _generate_premove_time()
        # Update state
        _think_state.previous_think_time = premove_time
        _think_state.consecutive_fast_moves += 1
        return premove_time

    # === Step 2: Get base time from game phase (inverted U) ===
    base_time = _get_phase_base_time(move_count)

    # === Step 3: Apply complexity multiplier ===
    complexity = _get_complexity_factor(num_legal_moves, is_capture, gives_check)

    # === Step 4: Apply move type modifiers ===
    if is_recapture:
        type_modifier = 0.3
    elif is_castling:
        type_modifier = 0.5
    elif num_legal_moves == 1:
        type_modifier = 0.35  # Forced move
    elif num_legal_moves <= 3:
        type_modifier = 0.55
    else:
        type_modifier = 1.0

    # === Step 5: Apply time control scaling ===
    mean_time = base_time * complexity * type_modifier * time_scale

    # === Step 6: Apply move correlation (AR(1) model) ===
    # Research: successive moves are correlated, rho ≈ 0.4
    rho = 0.4
    mean_time = rho * _think_state.previous_think_time + (1 - rho) * mean_time

    # Momentum: if in "fast mode", stay faster
    if _think_state.consecutive_fast_moves >= 3:
        mean_time *= 0.85

    # === Step 7: Sample from log-normal distribution ===
    think_time = _sample_log_normal(mean_time, elo)

    # === Step 8: Apply constraints ===
    think_time = max(min_time, min(max_time, think_time))

    # === Update state for next move ===
    _think_state.previous_think_time = think_time
    if think_time < 0.8:
        _think_state.consecutive_fast_moves += 1
    else:
        _think_state.consecutive_fast_moves = 0

    return think_time


def get_weights_path(elo: int) -> str:
    """Get the path to Maia weights for the given ELO rating."""
    # Round to nearest 100 and clamp to valid range
    elo_rounded = round(elo / 100) * 100
    elo_rounded = max(1100, min(1900, elo_rounded))

    # Get the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    weights_path = os.path.join(
        project_dir, "maia_original", "maia_weights", f"maia-{elo_rounded}.pb.gz"
    )

    return weights_path


def get_lc0_path() -> str:
    """Get the path to lc0 executable."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    lc0_path = os.path.join(project_dir, "engines", "lc0", "lc0.exe")

    return lc0_path


def main():
    """Main worker loop - reads commands from stdin, writes results to stdout."""
    # Read initialization parameters
    init_line = sys.stdin.readline().strip()
    if not init_line:
        print(json.dumps({"error": "No initialization parameters received"}), flush=True)
        return

    try:
        init_params = json.loads(init_line)
        elo = init_params.get("elo", 1500)
        time_control = init_params.get("time_control", "blitz")  # Used for thinking time calculation
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid init JSON: {e}"}), flush=True)
        return

    # Get paths
    lc0_path = get_lc0_path()
    weights_path = get_weights_path(elo)

    # Verify files exist
    if not os.path.exists(lc0_path):
        print(json.dumps({"error": f"lc0 not found at: {lc0_path}"}), flush=True)
        return

    if not os.path.exists(weights_path):
        print(json.dumps({"error": f"Maia weights not found at: {weights_path}"}), flush=True)
        return

    # Initialize lc0 with Maia weights
    try:
        print(f"Starting lc0 with weights: {weights_path}", file=sys.stderr, flush=True)

        # Start lc0 as UCI engine
        # Use blas backend (CPU) since we downloaded the openblas version
        engine = chess.engine.SimpleEngine.popen_uci(
            [
                lc0_path,
                f"--weights={weights_path}",
                "--threads=1",
                "--backend=blas",
                "--verbose-move-stats"  # Get move probabilities
            ],
            stderr=sys.stderr  # Forward lc0 stderr to our stderr for debugging
        )

        # Configure for Maia-style play (no search, just neural network output)
        # nodes=1 means we use the raw neural network prediction
        limits = chess.engine.Limit(nodes=1)

        print(json.dumps({"status": "ready"}), flush=True)

    except Exception as e:
        print(json.dumps({"error": f"Failed to start lc0: {e}"}), flush=True)
        return

    current_elo = elo
    last_move_count = -1  # Track for new game detection

    # Main loop - process move requests
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        if line == "QUIT":
            break

        try:
            request = json.loads(line)
            fen = request["fen"]
            elo_self = request.get("elo_self", 1500)
            move_count = request.get("move_count", 0)

            # Detect new game (move count dropped significantly)
            if move_count < last_move_count - 2 or (last_move_count > 5 and move_count <= 2):
                print(f"New game detected (move {last_move_count} -> {move_count}), resetting think state", file=sys.stderr, flush=True)
                reset_think_state()
            last_move_count = move_count

            # If ELO changed, we need to reload with different weights
            elo_rounded = round(elo_self / 100) * 100
            elo_rounded = max(1100, min(1900, elo_rounded))

            if elo_rounded != current_elo:
                # Close current engine and restart with new weights
                engine.quit()
                weights_path = get_weights_path(elo_self)
                print(f"Switching to ELO {elo_rounded} weights: {weights_path}", file=sys.stderr, flush=True)

                engine = chess.engine.SimpleEngine.popen_uci(
                    [
                        lc0_path,
                        f"--weights={weights_path}",
                        "--threads=1",
                        "--backend=blas",
                        "--verbose-move-stats"
                    ],
                    stderr=sys.stderr
                )
                current_elo = elo_rounded

            # Create board
            board = chess.Board(fen)

            # Check if game is over
            if board.is_game_over():
                print(json.dumps({"error": "Game is over, no moves available"}), flush=True)
                continue

            # Check if there are legal moves
            legal_moves = list(board.legal_moves)
            if not legal_moves:
                print(json.dumps({"error": "No legal moves available"}), flush=True)
                continue

            # Get move from Maia (lc0 with nodes=1)
            result = engine.play(board, limits, info=chess.engine.INFO_ALL)

            # Handle null/invalid moves from lc0
            if result.move is None:
                print(json.dumps({"error": "Engine returned no move"}), flush=True)
                continue

            best_move = result.move.uci()

            # Check for invalid moves like 'a1a1' (same square)
            if best_move == "0000" or (len(best_move) >= 4 and best_move[:2] == best_move[2:4]):
                # lc0 returned a null/invalid move, pick first legal move as fallback
                best_move = legal_moves[0].uci()
                print(f"Engine returned invalid move, using fallback: {best_move}", file=sys.stderr, flush=True)

            # Calculate human-like think time
            num_legal = len(legal_moves)
            # Parse the chosen move for think time calculation
            chosen_move = chess.Move.from_uci(best_move)
            think_time = calculate_think_time(
                board, chosen_move, move_count, num_legal,
                elo=current_elo, time_control=time_control
            )

            print(json.dumps({
                "move": best_move,
                "think_time": think_time,
                "confidence": 0.0,  # lc0 doesn't give us this directly
                "win_prob": 0.5  # Could extract from lc0 output if needed
            }), flush=True)

        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid request JSON: {e}"}), flush=True)
        except Exception as e:
            print(json.dumps({"error": f"Inference error: {e}"}), flush=True)

    # Cleanup
    try:
        engine.quit()
    except:
        pass


if __name__ == "__main__":
    main()
