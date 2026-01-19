import multiprocess
from stockfish import Stockfish
import pyautogui
pyautogui.FAILSAFE = False  # Disable fail-safe to prevent crashes when mouse is in corner
import time
import sys
import os
import chess
import re
from selenium.common.exceptions import StaleElementReferenceException
from grabbers.chesscom_grabber import ChesscomGrabber
from grabbers.lichess_grabber import LichessGrabber
from utilities import char_to_num
import keyboard
# Note: maia_manager imported lazily inside run() to avoid DLL issues on Windows


class StockfishBot(multiprocess.Process):
    def __init__(self, chrome_url, chrome_session_id, website, pipe, overlay_queue, stockfish_path, enable_manual_mode, enable_non_stop_matches, mouse_latency, slow_mover, skill_level, stockfish_depth, memory, cpu_threads, enable_human_mode=False, maia_elo=1500, maia_time_control="rapid", maia_use_gpu=True):
        multiprocess.Process.__init__(self)

        self.chrome_url = chrome_url
        self.chrome_session_id = chrome_session_id
        self.website = website
        self.pipe = pipe
        self.overlay_queue = overlay_queue
        self.stockfish_path = stockfish_path
        self.enable_manual_mode = enable_manual_mode
        self.enable_non_stop_matches = enable_non_stop_matches
        self.mouse_latency = mouse_latency
        self.slow_mover = slow_mover
        self.skill_level = skill_level
        self.stockfish_depth = stockfish_depth
        self.grabber = None
        self.memory = memory
        self.cpu_threads = cpu_threads
        self.is_white = None
        self.enable_human_mode = enable_human_mode
        self.maia_elo = maia_elo
        self.maia_time_control = maia_time_control
        self.maia_use_gpu = maia_use_gpu
        self.maia_model = None
        self.maia_prepared = None
        self._last_game_id = None

    # Converts a move to screen coordinates
    # Example: "a1" -> (x, y)
    def move_to_screen_pos(self, move):
        # Get the absolute top left corner of the website
        canvas_x_offset, canvas_y_offset = self.grabber.get_top_left_corner()

        # Get the absolute board position
        board_x = canvas_x_offset + self.grabber.get_board().location["x"]
        board_y = canvas_y_offset + self.grabber.get_board().location["y"]

        # Get the square size
        square_size = self.grabber.get_board().size['width'] / 8

        # Depending on the player color, the board is flipped, so the coordinates need to be adjusted
        if self.is_white:
            x = board_x + square_size * (char_to_num(move[0]) - 1) + square_size / 2
            y = board_y + square_size * (8 - int(move[1])) + square_size / 2
        else:
            x = board_x + square_size * (8 - char_to_num(move[0])) + square_size / 2
            y = board_y + square_size * (int(move[1]) - 1) + square_size / 2

        return x, y

    def get_move_pos(self, move):  # sourcery skip: remove-redundant-slice-index
        # Get the start and end position screen coordinates
        start_pos_x, start_pos_y = self.move_to_screen_pos(move[0:2])
        end_pos_x, end_pos_y = self.move_to_screen_pos(move[2:4])

        return (start_pos_x, start_pos_y), (end_pos_x, end_pos_y)


    def make_move(self, move):  # sourcery skip: extract-method
        # Get the start and end position screen coordinates
        start_pos, end_pos = self.get_move_pos(move)

        # Drag the piece from the start to the end position
        pyautogui.moveTo(start_pos[0], start_pos[1])
        time.sleep(self.mouse_latency)
        pyautogui.dragTo(end_pos[0], end_pos[1])

        # Check for promotion. If there is a promotion,
        # promote to the corresponding piece type
        if len(move) == 5:
            time.sleep(0.1)
            piece = move[4].lower()
            offset_map = {"q": 0, "r": 1, "b": 2, "n": 3}
            offset = offset_map.get(piece)
            if offset is not None:
                direction = -1 if self.is_white else 1
                target_rank = int(move[3]) + direction * offset
                if 1 <= target_rank <= 8:
                    end_pos_x, end_pos_y = self.move_to_screen_pos(move[2] + str(target_rank))
                else:
                    end_pos_x, end_pos_y = self.move_to_screen_pos(move[2:4])
                pyautogui.moveTo(x=end_pos_x, y=end_pos_y)
                pyautogui.click(button='left')

    def wait_for_gui_to_delete(self):
        while self.pipe.recv() != "DELETE":
            pass

    def move_list_has_result(self, move_list):
        if not move_list:
            return False
        for move in move_list:
            move = move.strip()
            if re.match(r"^(1-0|0-1|1/2-1/2|0.5-0.5)$", move):
                return True
        return False

    def _sanitize_san(self, move_san):
        if not move_san:
            return move_san
        move_san = move_san.strip()
        move_san = move_san.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
        move_san = move_san.replace(" e.p.", "")
        move_san = re.sub(r"[!?]+$", "", move_san)
        return move_san

    def _normalize_san(self, move_san):
        if not move_san:
            return ""
        move_san = move_san.strip()
        move_san = move_san.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
        move_san = move_san.rstrip("+#!?")
        move_san = move_san.replace("=", "")
        return move_san.lower()

    def _san_matches(self, expected, actual):
        return self._normalize_san(expected) == self._normalize_san(actual)

    def _is_san_legal(self, board, move_san):
        if not move_san:
            return False
        try:
            board.parse_san(self._sanitize_san(move_san))
            return True
        except Exception:
            return False

    def wait_for_move_confirmation(self, expected_san, previous_move_list, timeout=5.0):
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_move_list = self.grabber.get_move_list()
            if current_move_list is None:
                time.sleep(0.1)
                continue

            if len(current_move_list) >= len(previous_move_list) + 1:
                candidate = current_move_list[len(previous_move_list)]
                if self._san_matches(expected_san, candidate):
                    return True, current_move_list, candidate
                print(f"[DEBUG] Move list updated with unexpected SAN: expected={expected_san}, got={candidate}")
                return True, current_move_list, candidate

            time.sleep(0.1)

        return False, None, None

    def _try_build_board_from_moves(self, move_list):
        try:
            board = chess.Board()
            for move in move_list:
                board.push_san(self._sanitize_san(move))
            return board
        except Exception as e:
            print(f"[DEBUG] Error parsing moves: {e}")
            return None

    def _resync_move_list_state(self, stockfish, white_moves, white_best_moves, black_moves, black_best_moves, reason, expected_move_count=None, max_attempts=10):
        print(f"[DEBUG] Resyncing move list ({reason})")
        for attempt in range(max_attempts):
            self.grabber.reset_moves_list()
            fresh_move_list = self.grabber.get_move_list()
            if fresh_move_list is None:
                time.sleep(0.1)
                continue

            if self.move_list_has_result(fresh_move_list):
                print("[DEBUG] Resync saw game result in move list, waiting for new game...")
                time.sleep(0.2)
                continue

            if expected_move_count is not None:
                extra_allowance = 2 if expected_move_count <= 2 else 4
                max_allowed = expected_move_count + extra_allowance
                if len(fresh_move_list) > max_allowed:
                    print(f"[DEBUG] Resync move list too long ({len(fresh_move_list)} > {max_allowed}), waiting...")
                    time.sleep(0.2)
                    continue

            is_starting = None
            if hasattr(self.grabber, "is_starting_position"):
                try:
                    is_starting = self.grabber.is_starting_position()
                except StaleElementReferenceException:
                    print("[DEBUG] Stale element while checking starting position, retrying...")
                    ready_streak = 0
                    time.sleep(poll_delay)
                    continue
                except Exception:
                    is_starting = None

            if is_starting:
                if fresh_move_list:
                    print("[DEBUG] Board is at starting position, clearing stale move list")
                    self.grabber.reset_moves_list()
                    fresh_move_list = []
                board = chess.Board()
                stockfish.set_position([])
                detected_white = self.grabber.is_white()
                if detected_white is not None:
                    self.is_white = detected_white
            else:
                board = self._try_build_board_from_moves(fresh_move_list)
                if board is None:
                    time.sleep(0.2)
                    continue
                stockfish.set_position([move.uci() for move in board.move_stack])

            white_moves.clear()
            white_best_moves.clear()
            black_moves.clear()
            black_best_moves.clear()

            self.pipe.send("M_MOVE" + ",".join(fresh_move_list))
            return board, fresh_move_list

        return None, None

    def _wait_for_active_game(self, max_wait_seconds=30, poll_delay=0.5, previous_game_id=None, skip_modal_check=False):
        start_time = time.time()
        last_move_list_len = None
        ready_streak = 0
        unknown_starting_streak = 0
        stable_required = 3 if previous_game_id is not None else 2
        starting_unknown_required = 10 if previous_game_id is not None else 6
        has_starting_check = hasattr(self.grabber, "is_starting_position")
        debug_counter = 0

        print(f"[DEBUG] _wait_for_active_game: Starting wait (max={max_wait_seconds}s, previous_game_id={previous_game_id}, skip_modal_check={skip_modal_check})")

        while True:
            debug_counter += 1
            elapsed = time.time() - start_time
            if elapsed > max_wait_seconds:
                print(f"[DEBUG] _wait_for_active_game: Timed out after {elapsed:.1f}s")
                return None, None

            try:
                # Re-update board element in case page changed
                self.grabber.update_board_elem()
                if self.grabber.get_board() is None:
                    if debug_counter % 10 == 1:
                        print(f"[DEBUG] _wait_for_active_game: No board element found ({elapsed:.1f}s)")
                    time.sleep(poll_delay)
                    continue
            except StaleElementReferenceException:
                print("[DEBUG] Stale element while updating board, retrying...")
                ready_streak = 0
                time.sleep(poll_delay)
                continue

            current_game_id = None
            id_changed = True
            if previous_game_id is not None and hasattr(self.grabber, "get_current_game_id"):
                try:
                    current_game_id = self.grabber.get_current_game_id()
                except Exception:
                    current_game_id = None
                if current_game_id is None or current_game_id == previous_game_id:
                    id_changed = False
                    if debug_counter % 10 == 1:
                        print(f"[DEBUG] _wait_for_active_game: Game ID unchanged (current={current_game_id}, previous={previous_game_id}, {elapsed:.1f}s)")

            # Refresh player color (board may flip between games)
            try:
                self.is_white = self.grabber.is_white()
            except StaleElementReferenceException:
                print("[DEBUG] Stale element while reading player color, retrying...")
                ready_streak = 0
                time.sleep(poll_delay)
                continue
            if self.is_white is None:
                if debug_counter % 10 == 1:
                    print(f"[DEBUG] _wait_for_active_game: Player color unknown ({elapsed:.1f}s)")
                time.sleep(poll_delay)
                continue

            # Check board position first - if at starting position, skip modal check
            # (modal detection can be unreliable after clicking "New Game")
            is_starting = None
            if hasattr(self.grabber, "is_starting_position"):
                try:
                    is_starting = self.grabber.is_starting_position()
                except Exception:
                    is_starting = None

            # If a game-over modal is visible, wait for it to clear
            # BUT skip this check if:
            # - skip_modal_check=True (we just clicked "New Game" and know we're transitioning)
            # - board is clearly at starting position (new game started)
            if not skip_modal_check:
                try:
                    if hasattr(self.grabber, 'is_game_over') and self.grabber.is_game_over():
                        if is_starting is True:
                            # Board is at starting position - modal detection is likely stale, skip
                            if debug_counter % 10 == 1:
                                print(f"[DEBUG] _wait_for_active_game: Modal detected but board at starting position, ignoring modal ({elapsed:.1f}s)")
                        else:
                            if debug_counter % 10 == 1:
                                print(f"[DEBUG] _wait_for_active_game: Game-over modal still visible ({elapsed:.1f}s)")
                            time.sleep(poll_delay)
                            continue
                except StaleElementReferenceException:
                    print("[DEBUG] Stale element while checking game-over state, retrying...")
                    ready_streak = 0
                    time.sleep(poll_delay)
                    continue
                except Exception:
                    pass

            try:
                move_list = self.grabber.get_move_list()
            except StaleElementReferenceException:
                print("[DEBUG] Stale element while reading move list, retrying...")
                ready_streak = 0
                time.sleep(poll_delay)
                continue
            if move_list is None:
                time.sleep(poll_delay)
                continue

            # is_starting already checked above, no need to check again
            if is_starting is None and hasattr(self.grabber, "is_starting_position"):
                try:
                    is_starting = self.grabber.is_starting_position()
                except Exception:
                    is_starting = None

            if len(move_list) == 0:
                if is_starting is True:
                    unknown_starting_streak = 0
                else:
                    ready_streak = 0
                    if has_starting_check:
                        if is_starting is None:
                            print("[DEBUG] Board starting position unknown, waiting...")
                        else:
                            print("[DEBUG] Board not at starting position yet, waiting...")
                        time.sleep(poll_delay)
                        continue

                    unknown_starting_streak += 1
                    if unknown_starting_streak < starting_unknown_required:
                        print("[DEBUG] Board starting position unknown, waiting...")
                        time.sleep(poll_delay)
                        continue
            else:
                unknown_starting_streak = 0

            if last_move_list_len is not None and len(move_list) < last_move_list_len:
                print(f"[DEBUG] Move list shrank ({last_move_list_len} -> {len(move_list)}), waiting for new game...")
                self.grabber.reset_moves_list()
                last_move_list_len = None
                time.sleep(poll_delay)
                continue
            last_move_list_len = len(move_list)

            if self.move_list_has_result(move_list):
                if is_starting:
                    print("[DEBUG] Board is at starting position, resetting stale move list")
                    self.grabber.reset_moves_list()
                    move_list = []
                    board = chess.Board()
                    return board, move_list

                print(f"[DEBUG] Game result detected in move list ({move_list[-1]}) - waiting for new game...")
                time.sleep(poll_delay)
                continue

            # Build board to check if game is over
            board = self._try_build_board_from_moves(move_list)
            if board is None:
                self.grabber.reset_moves_list()
                time.sleep(poll_delay)
                continue

            # Check if we're looking at a finished game
            if board.is_game_over():
                if is_starting:
                    print("[DEBUG] Board is at starting position, resetting stale move list")
                    self.grabber.reset_moves_list()
                    move_list = []
                    board = chess.Board()
                    return board, move_list

                print(f"[DEBUG] Board shows game over ({board.result()}) - waiting for new game...")
                time.sleep(poll_delay)
                continue

            # Sanity check: if we have many moves, this might be an old game
            # Only apply this check when transitioning between games (previous_game_id is set)
            # When starting fresh (previous_game_id is None), allow joining mid-game
            if previous_game_id is not None:
                expected_max_moves = 1 if not self.is_white else 0
                if len(move_list) > expected_max_moves + 5:
                    if is_starting:
                        print("[DEBUG] Board is at starting position, resetting stale move list")
                        self.grabber.reset_moves_list()
                        move_list = []
                        board = chess.Board()
                        return board, move_list

                    print(f"[DEBUG] Found {len(move_list)} moves but expected ~{expected_max_moves} for a new game, waiting...")
                    time.sleep(poll_delay)
                    continue

            if previous_game_id is not None and not id_changed:
                allow_without_id = is_starting or len(move_list) <= expected_max_moves + 1
                if not allow_without_id:
                    if debug_counter % 10 == 1:
                        print(f"[DEBUG] _wait_for_active_game: Game ID unchanged and not starting position, moves={len(move_list)} ({elapsed:.1f}s)")
                    ready_streak = 0
                    time.sleep(poll_delay)
                    continue

            # Game looks valid - require a stable streak before returning
            ready_streak += 1
            if debug_counter % 5 == 1:
                print(f"[DEBUG] _wait_for_active_game: Ready streak {ready_streak}/{stable_required}, moves={len(move_list)}, is_starting={is_starting}")
            if ready_streak >= stable_required:
                print(f"[DEBUG] Game appears valid with {len(move_list)} moves")
                return board, move_list
            time.sleep(poll_delay)

    def _start_game_session(self, stockfish, previous_game_id=None, skip_modal_check=False):
        max_wait_seconds = 60 if previous_game_id is not None else 30
        board, move_list = self._wait_for_active_game(
            max_wait_seconds=max_wait_seconds,
            previous_game_id=previous_game_id,
            skip_modal_check=skip_modal_check
        )
        if board is None:
            self.pipe.send("ERR_RUNTIME|Timed out waiting for a new game. Make sure your new game is visible and try again.")
            return None
        if hasattr(self.grabber, "get_current_game_id"):
            try:
                self._last_game_id = self.grabber.get_current_game_id()
            except Exception:
                pass

        move_list_uci = [move.uci() for move in board.move_stack]
        stockfish.set_position(move_list_uci)

        white_moves = []
        white_best_moves = []
        black_moves = []
        black_best_moves = []

        print("[DEBUG] Sending initial eval data...")
        self.send_eval_data(stockfish, board)

        print("[DEBUG] Sending START signal...")
        self.pipe.send("START")
        print("[DEBUG] START signal sent, entering game loop...")

        if move_list:
            self.pipe.send("M_MOVE" + ",".join(move_list))

        return board, move_list, white_moves, white_best_moves, black_moves, black_best_moves

    def find_new_online_match(self):
        """Start a new online match after game ends."""
        # Wait for game-over modal to fully appear
        time.sleep(1.5)

        # Try to click "New Game" button with retries
        click_success = self.grabber.click_game_next()

        if not click_success:
            print("[DEBUG] find_new_online_match: Click failed, waiting longer...")
            time.sleep(2.0)
            self.grabber.click_game_next()  # Try once more

        # Wait for modal to fully disappear before continuing
        print("[DEBUG] find_new_online_match: Waiting for game-over modal to disappear...")
        modal_wait_start = time.time()
        while time.time() - modal_wait_start < 15:
            try:
                if not self.grabber.is_game_over():
                    print("[DEBUG] find_new_online_match: Modal disappeared")
                    break
            except Exception:
                break
            time.sleep(0.5)
        else:
            print("[DEBUG] find_new_online_match: Modal still visible after 15s, continuing anyway...")

        # Wait for new game to start loading
        time.sleep(1.0)

        # Reset grabber state to clear stale moves from previous game
        print("[DEBUG] find_new_online_match: Resetting grabber moves list...")
        self.grabber.reset_moves_list()

        # Notify GUI to clear state
        self.pipe.send("RESTART")
        self.wait_for_gui_to_delete()
        print("[DEBUG] find_new_online_match: GUI cleared, ready for new game")

    def run(self):
        # sourcery skip: extract-duplicate-method, switch, use-fstring-for-concatenation
        print("[DEBUG] StockfishBot.run() started")

        if self.website == "chesscom":
            self.grabber = ChesscomGrabber(self.chrome_url, self.chrome_session_id)
        else:
            self.grabber = LichessGrabber(self.chrome_url, self.chrome_session_id)
            
        # Reset the grabber's moves list to ensure a clean start
        self.grabber.reset_moves_list()

        # Initialize Stockfish
        parameters = {
            "Threads": self.cpu_threads,
            "Hash": self.memory,
            "Ponder": "true",
            "Slow Mover": self.slow_mover,
            "Skill Level": self.skill_level
        }
        try:
            stockfish = Stockfish(path=self.stockfish_path, depth=self.stockfish_depth, parameters=parameters)
        except PermissionError:
            self.pipe.send("ERR_PERM")
            return
        except OSError:
            self.pipe.send("ERR_EXE")
            return

        # Initialize Maia if Human Mode is enabled
        if self.enable_human_mode:
            try:
                print("[DEBUG] Initializing Maia...")
                # Import here to avoid DLL loading issues on Windows multiprocessing
                from maia_manager import initialize_maia, get_maia_move
                self.get_maia_move = get_maia_move  # Store for later use

                device = "gpu" if self.maia_use_gpu else "cpu"
                self.maia_model, self.maia_prepared = initialize_maia(
                    elo=self.maia_elo,
                    time_control=self.maia_time_control,
                    device=device
                )
                print("[DEBUG] Maia initialized successfully")
            except Exception as e:
                print(f"[DEBUG] Maia initialization failed: {e}")
                self.pipe.send(f"ERR_RUNTIME|Failed to initialize Maia: {e}")
                return

        try:
            # Brief pause to let page fully load after starting bot
            time.sleep(0.5)

            # Try to detect board and player color (can be None during page transitions)
            print("[DEBUG] Updating board element...")
            self.grabber.update_board_elem()
            self.is_white = self.grabber.is_white()
            print(f"[DEBUG] Player is white: {self.is_white}")

            # Skip modal check on initial start - user can dismiss game-over modal themselves if needed
            game_state = self._start_game_session(stockfish, skip_modal_check=True)
            if game_state is None:
                return
            board, move_list, white_moves, white_best_moves, black_moves, black_best_moves = game_state

            # Start the game loop
            loop_count = 0
            parse_error_count = 0  # Track consecutive parse errors to prevent infinite loops
            max_parse_errors = 10  # Max consecutive errors before giving up on current game
            while True:
                loop_count += 1
                if loop_count <= 3:
                    print(f"[DEBUG] Game loop iteration {loop_count}, is_white={self.is_white}, board.turn={'WHITE' if board.turn == chess.WHITE else 'BLACK'}, move_stack_len={len(board.move_stack)}")

                # Check if we've hit too many parse errors
                if parse_error_count >= max_parse_errors:
                    print(f"[DEBUG] Too many parse errors ({parse_error_count}), checking for game over or starting new match")
                    parse_error_count = 0
                    if self.enable_non_stop_matches:
                        print("[DEBUG] Attempting to start new match due to parse errors...")
                        previous_game_id = self._last_game_id
                        self.find_new_online_match()
                        game_state = self._start_game_session(stockfish, previous_game_id=previous_game_id, skip_modal_check=True)
                        if game_state is None:
                            return
                        board, move_list, white_moves, white_best_moves, black_moves, black_best_moves = game_state
                        loop_count = 0
                        continue
                    return

                # Detect end-of-game UI (resign/abandonment may not update move list)
                try:
                    if hasattr(self.grabber, "is_game_over") and self.grabber.is_game_over():
                        print("[DEBUG] Game over modal detected")
                        if self.enable_non_stop_matches:
                            print("[DEBUG] Non-stop matches enabled, starting next match...")
                            previous_game_id = self._last_game_id
                            self.find_new_online_match()
                            game_state = self._start_game_session(stockfish, previous_game_id=previous_game_id, skip_modal_check=True)
                            if game_state is None:
                                return
                            board, move_list, white_moves, white_best_moves, black_moves, black_best_moves = game_state
                            loop_count = 0
                            continue
                        time.sleep(1)
                        continue
                except Exception:
                    pass

                # Check if game is over before trying to move
                if board.is_game_over():
                    print(f"[DEBUG] Game is over: {board.result()}")
                    if self.enable_non_stop_matches:
                        print("[DEBUG] Non-stop matches enabled, starting next match...")
                        previous_game_id = self._last_game_id
                        self.find_new_online_match()
                        game_state = self._start_game_session(stockfish, previous_game_id=previous_game_id, skip_modal_check=True)
                        if game_state is None:
                            return
                        board, move_list, white_moves, white_best_moves, black_moves, black_best_moves = game_state
                        loop_count = 0
                        continue
                    time.sleep(1)  # Wait a bit before checking again
                    continue

                # Detect resignation/abandonment via move list result
                try:
                    result_move_list = self.grabber.get_move_list()
                except Exception:
                    result_move_list = None
                if result_move_list and self.move_list_has_result(result_move_list):
                    print(f"[DEBUG] Move list shows game result ({result_move_list[-1]})")
                    if self.enable_non_stop_matches:
                        print("[DEBUG] Non-stop matches enabled, starting next match...")
                        previous_game_id = self._last_game_id
                        self.find_new_online_match()
                        game_state = self._start_game_session(stockfish, previous_game_id=previous_game_id, skip_modal_check=True)
                        if game_state is None:
                            return
                        board, move_list, white_moves, white_best_moves, black_moves, black_best_moves = game_state
                        loop_count = 0
                        continue
                    time.sleep(1)
                    continue

                # Act if it is the player's turn
                if (self.is_white and board.turn == chess.WHITE) or (not self.is_white and board.turn == chess.BLACK):
                    # Think of a move
                    move = None
                    think_time = 0
                    move_count = len(board.move_stack)
                    if self.enable_human_mode:
                        current_fen = board.fen()
                        print(f"[DEBUG] Maia request - FEN: {current_fen}")
                        print(f"[DEBUG] Maia request - ELO: {self.maia_elo}, move_count: {move_count}")
                        move, think_time = self.get_maia_move(
                            self.maia_model, self.maia_prepared,
                            current_fen, self.maia_elo, self.maia_elo,
                            move_count=move_count
                        )
                        print(f"[DEBUG] Maia response - move: {move}, think_time: {think_time:.2f}s")
                    else:
                        move = stockfish.get_best_move()

                    # Apply human-like thinking delay (Human Mode only)
                    if self.enable_human_mode and think_time > 0:
                        time.sleep(think_time)

                    mover_is_white = board.turn == chess.WHITE
                    best_move = move
                    move_san = None

                    # Wait for keypress or player movement if in manual mode
                    self_moved = False
                    if self.enable_manual_mode:
                        # Store best move for accuracy calculation once per turn
                        if mover_is_white:
                            white_best_moves.append(best_move)
                        else:
                            black_best_moves.append(best_move)
                        move_start_pos, move_end_pos = self.get_move_pos(move)
                        self.overlay_queue.put([
                            ((int(move_start_pos[0]), int(move_start_pos[1])), (int(move_end_pos[0]), int(move_end_pos[1]))),
                        ])
                        while True:
                            if keyboard.is_pressed("3"):
                                break

                            current_move_list = self.grabber.get_move_list()
                            if current_move_list is None:
                                time.sleep(0.1)
                                continue
                            if len(move_list) != len(current_move_list):
                                self_moved = True
                                move_list = current_move_list
                                move_san = move_list[-1] if move_list else None
                                if not move_san:
                                    resynced = self._resync_move_list_state(
                                        stockfish, white_moves, white_best_moves,
                                        black_moves, black_best_moves,
                                        "manual move list empty",
                                        expected_move_count=len(board.move_stack) + 1
                                    )
                                    if resynced[0] is None:
                                        time.sleep(0.2)
                                        continue
                                    board, move_list = resynced
                                    move_san = move_list[-1] if move_list else None
                                    break
                                try:
                                    move = board.parse_san(self._sanitize_san(move_san)).uci()
                                except Exception as e:
                                    print(f"[DEBUG] Illegal SAN in manual mode: {move_san} ({e})")
                                    resynced = self._resync_move_list_state(
                                        stockfish, white_moves, white_best_moves,
                                        black_moves, black_best_moves,
                                        "manual move parse failed",
                                        expected_move_count=len(board.move_stack) + 1
                                    )
                                    if resynced[0] is None:
                                        time.sleep(0.2)
                                        continue
                                    board, move_list = resynced
                                    move_san = move_list[-1] if move_list else None
                                    break
                                # Store actual move for accuracy calculation
                                if board.turn == chess.WHITE:
                                    white_moves.append(move)
                                else:
                                    black_moves.append(move)
                                board.push_uci(move)
                                stockfish.make_moves_from_current_position([move])
                                break

                    if not self_moved:
                        move_san = board.san(chess.Move(chess.parse_square(move[0:2]), chess.parse_square(move[2:4])))
                        move_confirmed = False
                        current_move_list = None
                        confirmed_move_san = move_san

                        for attempt in range(3):
                            self.grabber.update_board_elem()
                            self.make_move(move)

                            move_confirmed, current_move_list, confirmed_move_san = self.wait_for_move_confirmation(
                                move_san,
                                move_list,
                                timeout=5.0
                            )
                            if move_confirmed:
                                break

                            time.sleep(0.2)

                        if not move_confirmed:
                            self.pipe.send("ERR_RUNTIME|Failed to register move on the board. Make sure the game has started and the move list is visible.")
                            return

                        if not self.enable_manual_mode:
                            # Get Stockfish's best move for accuracy comparison
                            # This is meaningful for Human Mode where bot plays Maia moves
                            stockfish_best = stockfish.get_best_move_time(300)
                            if mover_is_white:
                                white_best_moves.append(stockfish_best if stockfish_best else best_move)
                            else:
                                black_best_moves.append(stockfish_best if stockfish_best else best_move)

                        if current_move_list and len(current_move_list) >= len(move_list) + 1:
                            move_list = current_move_list[:len(move_list) + 1]
                            move_san = confirmed_move_san
                        else:
                            move_list.append(confirmed_move_san)
                            move_san = confirmed_move_san

                        prev_board = board.copy()
                        parsed_move = None
                        if move_san:
                            try:
                                parsed_move = prev_board.parse_san(self._sanitize_san(move_san))
                                parse_error_count = 0  # Reset on successful parse
                            except Exception as e:
                                parse_error_count += 1
                                print(f"[DEBUG] Failed to parse confirmed SAN '{move_san}': {e} (error #{parse_error_count})")
                                resynced = self._resync_move_list_state(
                                    stockfish, white_moves, white_best_moves,
                                    black_moves, black_best_moves,
                                    "confirmed move parse failed",
                                    expected_move_count=len(board.move_stack) + 1
                                )
                                if resynced[0] is not None:
                                    board, move_list = resynced
                                    move_san = move_list[-1] if move_list else None
                                    continue
                                else:
                                    # Resync failed - try to use the original UCI move as fallback
                                    print(f"[DEBUG] Resync failed, attempting to use original UCI move: {move}")
                                    try:
                                        parsed_move = chess.Move.from_uci(move)
                                        if parsed_move in prev_board.legal_moves:
                                            print(f"[DEBUG] UCI move {move} is legal, using it")
                                            parse_error_count = 0  # Reset on successful fallback
                                        else:
                                            print(f"[DEBUG] UCI move {move} is not legal, waiting...")
                                            time.sleep(0.5)
                                            continue
                                    except Exception as e2:
                                        print(f"[DEBUG] Failed to parse UCI move {move}: {e2}, waiting...")
                                        time.sleep(0.5)
                                        continue
                        if parsed_move and parsed_move.uci() != move:
                            resynced = self._resync_move_list_state(
                                stockfish, white_moves, white_best_moves,
                                black_moves, black_best_moves,
                                "confirmed move mismatch",
                                expected_move_count=len(board.move_stack) + 1
                            )
                            if resynced[0] is None:
                                time.sleep(0.2)
                                continue
                            board, move_list = resynced
                            move_san = move_list[-1] if move_list else None
                            continue
                        if parsed_move:
                            move_uci = parsed_move.uci()
                            board.push(parsed_move)
                        else:
                            move_uci = move
                            board.push_uci(move)

                        # Store actual move for accuracy calculation
                        if mover_is_white:
                            white_moves.append(move_uci)
                        else:
                            black_moves.append(move_uci)

                        stockfish.make_moves_from_current_position([move_uci])

                    self.overlay_queue.put([])

                    # Send evaluation, WDL, and material data to GUI
                    self.send_eval_data(stockfish, board, white_moves, white_best_moves, black_moves, black_best_moves)

                    # Send the move to the GUI
                    if move_san:
                        self.pipe.send("S_MOVE" + move_san)

                    # Check if the game is over
                    if board.is_checkmate():
                        # Send restart message to GUI
                        if self.enable_non_stop_matches:
                            print("[DEBUG] Checkmate! Bot wins. Starting next match...")
                            previous_game_id = self._last_game_id
                            self.find_new_online_match()
                            game_state = self._start_game_session(stockfish, previous_game_id=previous_game_id, skip_modal_check=True)
                            if game_state is None:
                                return
                            board, move_list, white_moves, white_best_moves, black_moves, black_best_moves = game_state
                            loop_count = 0
                            continue
                        return

                    time.sleep(0.1)

                # Wait for a response from the opponent
                # by finding the differences between
                # the previous and current position
                previous_move_list = move_list.copy()
                new_game_started = False
                restart_requested = False
                restart_previous_game_id = None
                resynced_in_wait = False
                while True:
                    if self.grabber.is_game_over():
                        # Send restart message to GUI
                        if self.enable_non_stop_matches:
                            print("[DEBUG] Non-stop matches enabled, starting next match...")
                            self.find_new_online_match()
                            restart_requested = True
                            restart_previous_game_id = self._last_game_id
                            break
                        return

                    # Get fresh move list from the grabber and check if it's a new game
                    new_move_list = self.grabber.get_move_list()
                    if new_move_list is None:
                        return

                    if self.move_list_has_result(new_move_list):
                        print(f"[DEBUG] Move list shows game result ({new_move_list[-1]})")
                        if self.enable_non_stop_matches:
                            print("[DEBUG] Non-stop matches enabled, starting next match...")
                            previous_game_id = self._last_game_id
                            self.find_new_online_match()
                            restart_requested = True
                            restart_previous_game_id = previous_game_id
                            break
                        time.sleep(1)
                        continue

                    # Detect new game if the move list shrank
                    if len(new_move_list) < len(previous_move_list):
                        new_game_started = True
                        break

                    if len(new_move_list) > len(previous_move_list) + 1:
                        resynced = self._resync_move_list_state(
                            stockfish, white_moves, white_best_moves,
                            black_moves, black_best_moves,
                            "move list jumped",
                            expected_move_count=len(board.move_stack) + 1
                        )
                        if resynced[0] is None:
                            time.sleep(0.2)
                            continue
                        board, move_list = resynced
                        resynced_in_wait = True
                        break

                    # Normal case - opponent made a single move
                    if len(new_move_list) > len(previous_move_list):
                        candidate_index = len(previous_move_list)
                        candidate = new_move_list[candidate_index] if len(new_move_list) > candidate_index else None
                        if not self._is_san_legal(board, candidate):
                            print(f"[DEBUG] Ignoring illegal SAN candidate: {candidate}")
                            time.sleep(0.2)
                            continue
                        move_list = new_move_list
                        break

                    time.sleep(0.1)

                if new_game_started:
                    # Reset everything for the new game
                    self.grabber.reset_moves_list()
                    fresh_move_list = self.grabber.get_move_list() or []
                    board = self._try_build_board_from_moves(fresh_move_list)
                    if board is None:
                        fresh_move_list = []
                        board = chess.Board()

                    stockfish.set_position([move.uci() for move in board.move_stack])

                    # Reset accuracy tracking
                    white_moves = []
                    white_best_moves = []
                    black_moves = []
                    black_best_moves = []
                    # Find out what color the player has for the new game
                    self.is_white = self.grabber.is_white()
                    self.pipe.send("RESTART")
                    self.wait_for_gui_to_delete()
                    # Send initial evaluation, WDL, and material data to GUI
                    self.send_eval_data(stockfish, board)
                    self.pipe.send("START")
                    if fresh_move_list:
                        self.pipe.send("M_MOVE" + ",".join(fresh_move_list))

                    move_list = fresh_move_list
                    continue
                if resynced_in_wait:
                    continue
                if restart_requested:
                    game_state = self._start_game_session(
                        stockfish,
                        previous_game_id=restart_previous_game_id if restart_previous_game_id is not None else self._last_game_id,
                        skip_modal_check=True
                    )
                    if game_state is None:
                        return
                    board, move_list, white_moves, white_best_moves, black_moves, black_best_moves = game_state
                    loop_count = 0
                    continue

                # Get the move that the opponent made
                move = move_list[-1]
                # Get UCI version of the move for accuracy tracking
                prev_board = board.copy()
                try:
                    move_obj = prev_board.parse_san(self._sanitize_san(move))
                    parse_error_count = 0  # Reset on successful parse
                except Exception as e:
                    parse_error_count += 1
                    print(f"[DEBUG] Illegal SAN from move list: {move} ({e}) (error #{parse_error_count})")
                    resynced = self._resync_move_list_state(
                        stockfish, white_moves, white_best_moves,
                        black_moves, black_best_moves,
                        "opponent move parse failed",
                        expected_move_count=len(board.move_stack) + 1
                    )
                    if resynced[0] is None:
                        # Resync failed - check if game is over or try to recover
                        print("[DEBUG] Resync failed, checking for game over or waiting...")
                        if self.grabber.is_game_over():
                            print("[DEBUG] Game appears to be over, handling end of game")
                            if self.enable_non_stop_matches:
                                print("[DEBUG] Non-stop matches enabled, starting next match...")
                                previous_game_id = self._last_game_id
                                self.find_new_online_match()
                                game_state = self._start_game_session(stockfish, previous_game_id=previous_game_id, skip_modal_check=True)
                                if game_state is None:
                                    return
                                board, move_list, white_moves, white_best_moves, black_moves, black_best_moves = game_state
                                loop_count = 0
                                parse_error_count = 0
                                continue
                            return
                        time.sleep(0.5)
                        continue
                    board, move_list = resynced
                    continue
                board.push(move_obj)
                move_uci = move_obj.uci()

                # Store actual move for accuracy calculation
                if prev_board.turn == chess.WHITE:
                    white_moves.append(move_uci)
                else:
                    black_moves.append(move_uci)

                # Get and store the best move that should have been played
                best_move = stockfish.get_best_move_time(300)  # Get best move with 300ms of thinking time
                if prev_board.turn == chess.WHITE:
                    white_best_moves.append(best_move)
                else:
                    black_best_moves.append(best_move)

                # Send evaluation, WDL, and material data to GUI
                stockfish.make_moves_from_current_position([str(board.peek())])
                self.send_eval_data(stockfish, board, white_moves, white_best_moves, black_moves, black_best_moves)

                # Send the move to the GUI
                self.pipe.send("S_MOVE" + move)

                if board.is_checkmate():
                    # Send restart message to GUI
                    if self.enable_non_stop_matches:
                        print("[DEBUG] Checkmate! Opponent wins. Starting next match...")
                        previous_game_id = self._last_game_id
                        self.find_new_online_match()
                        game_state = self._start_game_session(stockfish, previous_game_id=previous_game_id, skip_modal_check=True)
                        if game_state is None:
                            return
                        board, move_list, white_moves, white_best_moves, black_moves, black_best_moves = game_state
                        loop_count = 0
                        continue
                    return
        except Exception as e:
            # Log the error details
            print(f"StockfishBot Error: {e}")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(f"  Type: {exc_type}, File: {fname}, Line: {exc_tb.tb_lineno}")
            # Notify the GUI about the error
            try:
                self.pipe.send(f"ERR_RUNTIME|{str(e)}")
            except (BrokenPipeError, OSError):
                pass
        finally:
            # Clean up Maia subprocess if it was started
            if self.maia_model is not None:
                try:
                    self.maia_model.stop()
                except:
                    pass

    def send_eval_data(self, stockfish, board, white_moves=None, white_best_moves=None, black_moves=None, black_best_moves=None):
        """Send evaluation, WDL, and material data to GUI"""
        try:
            # Get evaluation
            eval_data = stockfish.get_evaluation()
            eval_type = eval_data['type']
            eval_value = eval_data['value']
            
            # Convert evaluation to player's perspective if playing as black
            # Stockfish eval is always from white's perspective (+ve for white, -ve for black)
            player_perspective_eval_value = eval_value
            if not self.is_white:
                player_perspective_eval_value = -eval_value  # Negate to get black's perspective
            
            # Get WDL stats if available
            try:
                wdl_stats = stockfish.get_wdl_stats()
                if wdl_stats is None:
                    wdl_stats = [0, 0, 0]
            except (AttributeError, KeyError, TypeError, ValueError):
                wdl_stats = [0, 0, 0]
                
            # Calculate material advantage (basic version)
            material = self.calculate_material_advantage(board)
            
            # Calculate accuracy if enough moves
            white_accuracy = "-"
            black_accuracy = "-"
            if white_moves and white_best_moves and len(white_moves) > 0 and len(white_moves) == len(white_best_moves):
                matches = sum(1 for a, b in zip(white_moves, white_best_moves) if a == b)
                white_accuracy = f"{matches / len(white_moves) * 100:.1f}%"
            
            if black_moves and black_best_moves and len(black_moves) > 0 and len(black_moves) == len(black_best_moves):
                matches = sum(1 for a, b in zip(black_moves, black_best_moves) if a == b)
                black_accuracy = f"{matches / len(black_moves) * 100:.1f}%"
            
            # Format evaluation string from player's perspective
            if eval_type == "cp":
                eval_str = f"{player_perspective_eval_value/100:.2f}"
                # Convert centipawns to decimal value for the eval bar
                eval_value_decimal = player_perspective_eval_value/100
            else:  # mate
                eval_str = f"M{player_perspective_eval_value}"
                eval_value_decimal = player_perspective_eval_value  # Keep mate score as is
            
            # Format WDL string (win/draw/loss percentages)
            total = sum(wdl_stats)
            if total > 0:
                # WDL from Stockfish is from perspective of player to move
                # Need to invert if it's opponent's turn
                is_bot_turn = (self.is_white and board.turn == chess.WHITE) or (not self.is_white and board.turn == chess.BLACK)
                
                if is_bot_turn:
                    win_pct = wdl_stats[0] / total * 100
                    draw_pct = wdl_stats[1] / total * 100
                    loss_pct = wdl_stats[2] / total * 100
                else:
                    # Invert the win/loss when it's opponent's turn
                    win_pct = wdl_stats[2] / total * 100
                    draw_pct = wdl_stats[1] / total * 100
                    loss_pct = wdl_stats[0] / total * 100
                
                wdl_str = f"{win_pct:.1f}/{draw_pct:.1f}/{loss_pct:.1f}"
            else:
                wdl_str = "?/?/?"
            
            # Determine bot and opponent accuracies based on bot's color
            bot_accuracy = white_accuracy if self.is_white else black_accuracy
            opponent_accuracy = black_accuracy if self.is_white else white_accuracy
            
            # Send data to GUI
            data = f"EVAL|{eval_str}|{wdl_str}|{material}|{bot_accuracy}|{opponent_accuracy}"
            self.pipe.send(data)
            
            # Send evaluation data to overlay
            overlay_data = {
                "eval": eval_value_decimal,
                "eval_type": eval_type
            }
            
            # Add board position and dimensions for the eval bar positioning
            board_elem = self.grabber.get_board()
            if board_elem:
                # Get the absolute top left corner of the website
                canvas_x_offset, canvas_y_offset = self.grabber.get_top_left_corner()
                
                # Calculate absolute board position and dimensions
                overlay_data["board_position"] = {
                    'x': canvas_x_offset + board_elem.location['x'],
                    'y': canvas_y_offset + board_elem.location['y'],
                    'width': board_elem.size['width'],
                    'height': board_elem.size['height']
                }
                
            # Always include the bot's color
            overlay_data["is_white"] = self.is_white
            
            self.overlay_queue.put(overlay_data)
            
        except Exception as e:
            print(f"Error sending evaluation: {e}")
    
    def calculate_material_advantage(self, board):
        """Calculate material advantage in the position"""
        piece_values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9
        }
        
        white_material = 0
        black_material = 0
        
        for piece_type in piece_values:
            white_material += len(board.pieces(piece_type, chess.WHITE)) * piece_values[piece_type]
            black_material += len(board.pieces(piece_type, chess.BLACK)) * piece_values[piece_type]
        
        advantage = white_material - black_material
        if advantage > 0:
            return f"+{advantage}"
        elif advantage < 0:
            return str(advantage)
        else:
            return "0"
