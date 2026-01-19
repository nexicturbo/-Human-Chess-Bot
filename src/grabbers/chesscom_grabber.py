from selenium.common import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
import time

from grabbers.grabber import Grabber


class ChesscomGrabber(Grabber):
    def __init__(self, chrome_url, chrome_session_id):
        super().__init__(chrome_url, chrome_session_id)
        # The moves_list is now initialized in the base class
        self._last_board_type = None  # Track board type to detect game switches
        self._current_game_id = None  # Track game ID from URL to detect game switches
        self._empty_visible_moves_count = 0  # Debounce empty move list during UI refreshes

    def update_board_elem(self):
        """Find the active board element, checking visibility to handle page transitions."""
        self._board_elem = None
        current_board_type = None

        # Check board-single first (online/human games) - more common use case
        try:
            elem = self.chrome.find_element(By.XPATH, "//*[@id='board-single']")
            if elem.is_displayed():
                self._board_elem = elem
                current_board_type = "board-single"
        except (NoSuchElementException, StaleElementReferenceException):
            pass

        # Check board-play-computer (bot games)
        if self._board_elem is None:
            try:
                elem = self.chrome.find_element(By.XPATH, "//*[@id='board-play-computer']")
                if elem.is_displayed():
                    self._board_elem = elem
                    current_board_type = "board-play-computer"
            except (NoSuchElementException, StaleElementReferenceException):
                pass

        # Fallback: try board-vs-personality (some bot modes)
        if self._board_elem is None:
            try:
                elem = self.chrome.find_element(By.XPATH, "//*[@id='board-vs-personality']")
                if elem.is_displayed():
                    self._board_elem = elem
                    current_board_type = "board-vs-personality"
            except (NoSuchElementException, StaleElementReferenceException):
                pass

        # If board type changed, reset moves list (switching between game types)
        if current_board_type is not None and self._last_board_type is not None:
            if current_board_type != self._last_board_type:
                print(f"[DEBUG] Board type changed from {self._last_board_type} to {current_board_type}, resetting moves")
                self.reset_moves_list()

        self._last_board_type = current_board_type

    def _square_id_to_coord(self, square_id):
        if not square_id or len(square_id) < 2:
            return None
        try:
            file_num = int(square_id[0])
            rank_num = int(square_id[1])
        except ValueError:
            return None
        if file_num < 1 or file_num > 8 or rank_num < 1 or rank_num > 8:
            return None
        file_char = chr(ord('a') + file_num - 1)
        return f"{file_char}{rank_num}"

    def is_starting_position(self):
        """Return True if the visible board shows the standard starting position."""
        try:
            board = self._board_elem
            if board is None or not board.is_displayed():
                self.update_board_elem()
                board = self._board_elem
            if board is None or not board.is_displayed():
                return None

            pieces = board.find_elements(By.CSS_SELECTOR, ".piece")
        except (NoSuchElementException, StaleElementReferenceException):
            return None

        if not pieces:
            return None

        expected = {
            "a1": "wr", "b1": "wn", "c1": "wb", "d1": "wq", "e1": "wk", "f1": "wb", "g1": "wn", "h1": "wr",
            "a2": "wp", "b2": "wp", "c2": "wp", "d2": "wp", "e2": "wp", "f2": "wp", "g2": "wp", "h2": "wp",
            "a7": "bp", "b7": "bp", "c7": "bp", "d7": "bp", "e7": "bp", "f7": "bp", "g7": "bp", "h7": "bp",
            "a8": "br", "b8": "bn", "c8": "bb", "d8": "bq", "e8": "bk", "f8": "bb", "g8": "bn", "h8": "br",
        }
        piece_classes = set(expected.values())

        found = {}
        for piece in pieces:
            try:
                classes = piece.get_attribute("class").split()
            except StaleElementReferenceException:
                return None
            square_class = next((c for c in classes if c.startswith("square-")), None)
            piece_class = next((c for c in classes if c in piece_classes), None)
            if square_class and piece_class:
                square_id = square_class.split("-")[1]
                coord = self._square_id_to_coord(square_id)
                if coord:
                    found[coord] = piece_class

        if len(found) < len(expected):
            return False

        for square, piece in expected.items():
            if found.get(square) != piece:
                return False

        return True

    def is_white(self):
        # Find the square names list from the VISIBLE board
        square_names = None

        # Try board-single first (human games)
        try:
            board = self.chrome.find_element(By.XPATH, "//*[@id='board-single']")
            if board.is_displayed():
                coordinates = self.chrome.find_elements(By.XPATH, "//*[@id='board-single']//*[name()='svg']")
                coordinates = [x for x in coordinates if x.get_attribute("class") == "coordinates"][0]
                square_names = coordinates.find_elements(By.XPATH, ".//*")
        except (NoSuchElementException, StaleElementReferenceException, IndexError):
            pass

        # Try board-play-computer (bot games)
        if square_names is None:
            try:
                board = self.chrome.find_element(By.XPATH, "//*[@id='board-play-computer']")
                if board.is_displayed():
                    coordinates = self.chrome.find_element(By.XPATH, "//*[@id='board-play-computer']//*[name()='svg']")
                    square_names = coordinates.find_elements(By.XPATH, ".//*")
            except (NoSuchElementException, StaleElementReferenceException):
                pass

        # Try board-vs-personality (some bot modes)
        if square_names is None:
            try:
                board = self.chrome.find_element(By.XPATH, "//*[@id='board-vs-personality']")
                if board.is_displayed():
                    coordinates = self.chrome.find_element(By.XPATH, "//*[@id='board-vs-personality']//*[name()='svg']")
                    square_names = coordinates.find_elements(By.XPATH, ".//*")
            except (NoSuchElementException, StaleElementReferenceException):
                pass

        if square_names is None:
            return None

        # Find the square with the smallest x and biggest y values (bottom left number)
        elem = None
        min_x = None
        max_y = None
        for i in range(len(square_names)):
            name_element = square_names[i]
            x = float(name_element.get_attribute("x"))
            y = float(name_element.get_attribute("y"))

            if i == 0 or (x <= min_x and y >= max_y):
                min_x = x
                max_y = y
                elem = name_element

        # Use this square to determine whether the player is white or black
        num = elem.text
        return num == "1"

    def is_game_over(self):
        """Check if game-over modal is visible by looking for actual game-over content.

        More reliable than just checking for container classes, which may exist
        on the page even when hidden.
        """
        try:
            # Strategy 1: Look for visible "New Game" or "Rematch" buttons
            # These only appear in the game-over modal
            buttons = self.chrome.find_elements(By.CSS_SELECTOR, "button")
            for button in buttons:
                try:
                    if button.is_displayed():
                        text = button.text.lower()
                        # If we see "new" and a time control, or "rematch", game is over
                        if ("new" in text and ("min" in text or "game" in text)) or "rematch" in text:
                            return True
                except StaleElementReferenceException:
                    continue

            # Strategy 2: Look for game-over header text (wins/lost/draw)
            try:
                # Chess.com shows "You won", "You lost", "Draw", etc. in game-over modal
                headers = self.chrome.find_elements(By.CSS_SELECTOR, ".game-over-header-component, .game-over-header-content, [class*='game-over'] h3, [class*='game-over'] h2")
                for header in headers:
                    try:
                        if header.is_displayed():
                            text = header.text.lower()
                            if any(word in text for word in ["won", "win", "lost", "lose", "draw", "checkmate", "resignation", "timeout", "abandoned"]):
                                return True
                    except StaleElementReferenceException:
                        continue
            except NoSuchElementException:
                pass

            # Strategy 3: Check for visible modal with game-over buttons component
            try:
                buttons_component = self.chrome.find_element(By.CLASS_NAME, "game-over-buttons-component")
                if buttons_component.is_displayed():
                    return True
            except (NoSuchElementException, StaleElementReferenceException):
                pass

        except Exception as e:
            print(f"[DEBUG] is_game_over error: {e}")

        return False

    def get_current_game_id(self):
        """Extract game ID from Chess.com URL to detect game changes."""
        try:
            url = self.chrome.current_url
            # Live games: chess.com/game/live/123456789
            if "/game/live/" in url:
                game_id = url.split("/game/live/")[-1].split("?")[0].split("/")[0]
                return f"live_{game_id}"
            # Computer games: chess.com/play/computer
            elif "/play/computer" in url:
                # For computer games, use a timestamp-based ID since URL doesn't change
                # We'll rely on board type changes for these
                return "computer"
            # Bot games with personality: chess.com/play/computer/...
            elif "/computer/" in url:
                return "computer"
        except Exception:
            pass
        return None

    def _get_visible_move_list_container(self):
        """Get the move list container that is actually visible on screen."""
        selectors = [
            "play-controller-scrollable",
            "mode-swap-move-list-wrapper-component"
        ]
        for class_name in selectors:
            try:
                elems = self.chrome.find_elements(By.CLASS_NAME, class_name)
                for elem in elems:
                    try:
                        if elem.is_displayed():
                            return elem
                    except StaleElementReferenceException:
                        continue
            except (NoSuchElementException, StaleElementReferenceException):
                pass
        return None

    def reset_moves_list(self):
        """Reset the moves list when a new game starts"""
        self.moves_list = {}
        self._current_game_id = None  # Clear game ID so next call re-detects
        self._empty_visible_moves_count = 0
        # Also clear data-processed attributes from the DOM to force fresh read
        try:
            self.chrome.execute_script("""
                document.querySelectorAll('[data-processed]').forEach(el => {
                    el.removeAttribute('data-processed');
                });
            """)
        except:
            pass

    def get_move_list(self):
        # Check if game changed via URL (most reliable for live games)
        new_game_id = self.get_current_game_id()
        if new_game_id and self._current_game_id and new_game_id != self._current_game_id:
            print(f"[DEBUG] Game ID changed: {self._current_game_id} -> {new_game_id}, resetting moves")
            self.moves_list = {}  # Direct reset without clearing game ID yet
            # Clear data-processed attributes
            try:
                self.chrome.execute_script("""
                    document.querySelectorAll('[data-processed]').forEach(el => {
                        el.removeAttribute('data-processed');
                    });
                """)
            except:
                pass
        self._current_game_id = new_game_id

        # Find ONLY the visible move list container (not hidden old game containers)
        move_list_elem = self._get_visible_move_list_container()
        if move_list_elem is None:
            return None

        # Get all move nodes from this visible container
        all_moves_in_container = move_list_elem.find_elements(By.CSS_SELECTOR, "div.node[data-node]")

        # Filter to only moves that are actually visible (not hidden old game moves)
        visible_moves = []
        for m in all_moves_in_container:
            try:
                if m.is_displayed():
                    visible_moves.append(m)
            except StaleElementReferenceException:
                continue

        # Check if we're in a new game by looking at the number of visible moves
        # If there are no visible moves but we have moves in our list, we're in a new game
        if len(visible_moves) == 0 and self.moves_list:
            self._empty_visible_moves_count += 1
            if self._empty_visible_moves_count >= 3:
                print(f"[DEBUG] No visible moves for {self._empty_visible_moves_count} checks, resetting")
                self.reset_moves_list()
                self._empty_visible_moves_count = 0
        else:
            self._empty_visible_moves_count = 0

        # Select moves to process
        if not self.moves_list:
            # If the moves list is empty, process all visible moves
            moves = visible_moves
        else:
            # If the moves list is not empty, find only the new unprocessed visible moves
            moves = []
            for m in visible_moves:
                try:
                    if not m.get_attribute("data-processed"):
                        moves.append(m)
                except StaleElementReferenceException:
                    continue

        for move in moves:
            try:
                move_class = move.get_attribute("class")
            except StaleElementReferenceException:
                continue

            # Check if it is indeed a move
            if "white-move" in move_class or "black-move" in move_class:
                # Check if it has a figure - try multiple strategies
                figure = None

                # Strategy 1: Look for data-figurine attribute
                try:
                    figurine_elem = move.find_element(By.CSS_SELECTOR, "[data-figurine]")
                    figure = figurine_elem.get_attribute("data-figurine")
                except (NoSuchElementException, StaleElementReferenceException):
                    pass

                # Strategy 2: Look for piece class on a span (Chess.com sometimes uses this)
                if figure is None:
                    try:
                        piece_span = move.find_element(By.CSS_SELECTOR, "span.piece-wrapper, span[class*='piece']")
                        # Try to get the piece from the span's class or content
                        piece_class = piece_span.get_attribute("class") or ""
                        for piece in ["K", "Q", "R", "B", "N"]:
                            if piece.lower() in piece_class.lower():
                                figure = piece
                                break
                    except (NoSuchElementException, StaleElementReferenceException):
                        pass

                # Strategy 3: Check if move text starts with a piece letter (fallback)
                try:
                    move_text = move.text.strip()
                except StaleElementReferenceException:
                    continue

                if figure is None and move_text:
                    # If move starts with uppercase letter that's a piece, extract it
                    if move_text[0] in "KQRBN":
                        figure = move_text[0]
                        move_text = move_text[1:]  # Remove the piece from move_text

                # Build the final move notation
                if figure is None:
                    # Pawn move or castling
                    final_move = move_text
                elif "=" in move_text:
                    # Promotion - piece goes after the move
                    final_move = move_text + figure
                    # If the move is a check, add the + at the end
                    if "+" in final_move:
                        final_move = final_move.replace("+", "") + "+"
                    if "#" in final_move:
                        final_move = final_move.replace("#", "") + "#"
                else:
                    # Regular piece move - piece goes before
                    final_move = figure + move_text

                # Store the move
                try:
                    node_id = move.get_attribute("data-node")
                    self.moves_list[node_id] = final_move
                except StaleElementReferenceException:
                    continue

                # Mark the move as processed
                try:
                    self.chrome.execute_script("arguments[0].setAttribute('data-processed', 'true')", move)
                except StaleElementReferenceException:
                    pass

        return list(self.moves_list.values())

    def is_game_puzzles(self):
        return False

    def click_puzzle_next(self):
        pass

    def click_game_next(self):
        """Click the 'New Game' button after a game ends on Chess.com.
        Returns True if click succeeded, False otherwise.
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                time.sleep(0.5)  # Wait for modal to stabilize

                # Try multiple button finding strategies
                new_game_button = None

                # Strategy 1: Buttons with "New" text
                try:
                    buttons = self.chrome.find_elements(By.CSS_SELECTOR, "button")
                    for button in buttons:
                        try:
                            if button.is_displayed():
                                text = button.text.lower()
                                if "new" in text and "rematch" not in text:
                                    new_game_button = button
                                    break
                        except StaleElementReferenceException:
                            continue
                except NoSuchElementException:
                    pass

                # Strategy 2: Game-over modal buttons
                if new_game_button is None:
                    try:
                        modal = self.chrome.find_element(By.CLASS_NAME, "board-modal-container")
                        if modal.is_displayed():
                            buttons = modal.find_elements(By.CSS_SELECTOR, "button")
                            for button in buttons:
                                try:
                                    if button.is_displayed() and "new" in button.text.lower():
                                        new_game_button = button
                                        break
                                except StaleElementReferenceException:
                                    continue
                    except NoSuchElementException:
                        pass

                # Strategy 3: game-over-buttons-component
                if new_game_button is None:
                    try:
                        buttons_container = self.chrome.find_element(By.CLASS_NAME, "game-over-buttons-component")
                        buttons = buttons_container.find_elements(By.CSS_SELECTOR, "button")
                        for button in buttons:
                            try:
                                if button.is_displayed() and "new" in button.text.lower():
                                    new_game_button = button
                                    break
                            except StaleElementReferenceException:
                                continue
                    except NoSuchElementException:
                        pass

                # Strategy 4: aria-label
                if new_game_button is None:
                    try:
                        new_game_button = self.chrome.find_element(
                            By.XPATH, "//button[contains(@aria-label, 'New') or contains(@aria-label, 'new')]"
                        )
                    except NoSuchElementException:
                        pass

                if new_game_button:
                    self.chrome.execute_script("arguments[0].click();", new_game_button)
                    print(f"[DEBUG] click_game_next: Clicked button on attempt {attempt + 1}")

                    # Verify click worked - wait for modal to disappear
                    time.sleep(1.0)
                    try:
                        modal = self.chrome.find_element(By.CLASS_NAME, "board-modal-container")
                        if not modal.is_displayed():
                            return True  # Success - modal gone
                    except NoSuchElementException:
                        return True  # Success - modal gone

                    print(f"[DEBUG] click_game_next: Modal still visible, retrying...")
                else:
                    print(f"[DEBUG] click_game_next: No button found on attempt {attempt + 1}")

            except Exception as e:
                print(f"[DEBUG] click_game_next error on attempt {attempt + 1}: {e}")

            time.sleep(1.0)

        print("[DEBUG] click_game_next: All attempts failed")
        return False

    def make_mouseless_move(self, move, move_count):
        pass
