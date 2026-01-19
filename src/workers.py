"""
PawnBit Worker Threads
Background workers for process monitoring and IPC
"""
import time
from PyQt6.QtCore import QObject, QThread, pyqtSlot
from signals import GUISignals

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False


class ProcessCheckerWorker(QObject):
    """
    Monitors if the StockfishBot process is still alive.
    Emits bot_stopped signal when the process terminates.
    """

    def __init__(self, signals: GUISignals):
        super().__init__()
        self.signals = signals
        self.running = False
        self.process = None
        self.restart_after_stopping = False

    def set_process(self, process):
        """Set the process to monitor"""
        self.process = process

    def set_restart_flag(self, restart: bool):
        """Set whether to restart after stopping"""
        self.restart_after_stopping = restart

    @pyqtSlot()
    def run(self):
        """Main worker loop"""
        self.running = True
        while self.running:
            if self.process is not None and not self.process.is_alive():
                self.signals.bot_stopped.emit()
                if self.restart_after_stopping:
                    self.restart_after_stopping = False
                    self.signals.restart_requested.emit()
                self.process = None
            QThread.msleep(100)

    def stop(self):
        """Stop the worker"""
        self.running = False


class BrowserCheckerWorker(QObject):
    """
    Monitors the Chrome WebDriver for window close events.
    Emits browser_closed signal when the browser is closed.
    """

    def __init__(self, signals: GUISignals):
        super().__init__()
        self.signals = signals
        self.running = False
        self.chrome = None

    def set_chrome(self, chrome):
        """Set the Chrome driver to monitor"""
        self.chrome = chrome

    @pyqtSlot()
    def run(self):
        """Main worker loop"""
        self.running = True
        while self.running:
            if self.chrome is not None:
                try:
                    # Try to access window handles - this will fail if browser is closed
                    handles = self.chrome.window_handles
                    if not handles:
                        # No windows open
                        self.signals.browser_closed.emit()
                        self.chrome = None
                except Exception:
                    # Any exception means browser is likely closed
                    self.signals.browser_closed.emit()
                    self.chrome = None
            QThread.msleep(500)  # Check every 500ms

    def stop(self):
        """Stop the worker"""
        self.running = False


class PipeCommunicatorWorker(QObject):
    """
    Handles communication between the GUI and StockfishBot process.
    Receives messages from the pipe and emits appropriate signals.
    """

    def __init__(self, signals: GUISignals):
        super().__init__()
        self.signals = signals
        self.running = False
        self.pipe = None

    def set_pipe(self, pipe):
        """Set the pipe to communicate through"""
        self.pipe = pipe

    @pyqtSlot()
    def run(self):
        """Main worker loop"""
        self.running = True
        while self.running:
            if self.pipe is not None:
                try:
                    if self.pipe.poll(0.05):  # 50ms timeout
                        data = self.pipe.recv()
                        self._handle_message(data)
                except (BrokenPipeError, OSError, EOFError):
                    self.pipe = None
            else:
                QThread.msleep(100)

    def _handle_message(self, data: str):
        """Process incoming message from bot"""
        if data == "START":
            self.signals.clear_moves.emit()
            self.signals.bot_started.emit()

        elif data == "RESTART":
            self.signals.restart_requested.emit()

        elif data.startswith("S_MOVE"):
            # Single move: "S_MOVEe4"
            move = data[6:]
            self.signals.single_move.emit(move)

        elif data.startswith("M_MOVE"):
            # Multiple moves: "M_MOVEe4,c5,Nf3,d6"
            moves_str = data[6:]
            moves = moves_str.split(",") if moves_str else []
            self.signals.multiple_moves.emit(moves)

        elif data.startswith("EVAL|"):
            # Evaluation data: "EVAL|+1.45|65.2/24.1/10.7|+3|92.5%|78.3%"
            parts = data.split("|")
            if len(parts) >= 6:
                eval_str = parts[1]
                wdl_str = parts[2]
                material_str = parts[3]
                bot_acc = parts[4]
                opp_acc = parts[5]
                self.signals.eval_updated.emit(eval_str, wdl_str, material_str, bot_acc, opp_acc)

        elif data.startswith("ERR_"):
            # Error messages
            error_map = {
                "ERR_EXE": ("Error", "Stockfish path provided is not valid!"),
                "ERR_PERM": ("Error", "Stockfish path provided is not executable!"),
                "ERR_BOARD": ("Error", "Can't find board!"),
                "ERR_COLOR": ("Error", "Can't find player color!"),
                "ERR_MOVES": ("Error", "Can't find moves list!"),
                "ERR_GAMEOVER": ("Error", "Game has already finished!"),
            }

            if data.startswith("ERR_RUNTIME"):
                # Runtime error with message: "ERR_RUNTIME|error message"
                error_msg = data.split("|")[1] if "|" in data else "Unknown error"
                self.signals.error_occurred.emit("Runtime Error", f"Bot encountered an error: {error_msg}")
            elif data[:12] in error_map:
                title, message = error_map[data[:12]]
                self.signals.error_occurred.emit(title, message)
            else:
                # Try shorter keys
                for key, (title, message) in error_map.items():
                    if data.startswith(key):
                        self.signals.error_occurred.emit(title, message)
                        break

    def stop(self):
        """Stop the worker"""
        self.running = False


class KeyboardListenerWorker(QObject):
    """
    Listens for global keyboard shortcuts.
    Emits signals when start/stop keys are pressed.
    """

    def __init__(self, signals: GUISignals):
        super().__init__()
        self.signals = signals
        self.running = False
        self.browser_open = False

    def set_browser_open(self, is_open: bool):
        """Set whether the browser is open (shortcuts only work when browser is open)"""
        self.browser_open = is_open

    @pyqtSlot()
    def run(self):
        """Main worker loop"""
        if not KEYBOARD_AVAILABLE:
            return

        self.running = True
        while self.running:
            if self.browser_open:
                try:
                    if keyboard.is_pressed("1"):
                        self.signals.key_start_pressed.emit()
                        QThread.msleep(300)  # Debounce
                    elif keyboard.is_pressed("2"):
                        self.signals.key_stop_pressed.emit()
                        QThread.msleep(300)  # Debounce
                except Exception:
                    pass
            QThread.msleep(100)

    def stop(self):
        """Stop the worker"""
        self.running = False


class DownloadWorker(QObject):
    """
    Handles Stockfish download in background.
    Emits progress updates and completion signal.
    """

    def __init__(self, signals: GUISignals):
        super().__init__()
        self.signals = signals

    @pyqtSlot()
    def run(self):
        """Run the download"""
        from stockfish_manager import download_stockfish

        def progress_callback(percent, message):
            self.signals.download_progress.emit(percent, message)

        path = download_stockfish(progress_callback)
        self.signals.download_complete.emit(path if path else "")
