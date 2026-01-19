"""
PawnBit Custom PyQt Signals
Thread-safe communication between workers and UI
"""
from PyQt6.QtCore import QObject, pyqtSignal


class GUISignals(QObject):
    """
    Custom signals for thread-safe UI updates.
    Workers emit these signals, main thread receives them via slots.
    """

    # Status updates
    status_changed = pyqtSignal(str, str)  # (text, color)

    # Evaluation updates - eval, wdl, material, bot_acc, opponent_acc
    eval_updated = pyqtSignal(str, str, str, str, str)

    # Move updates
    single_move = pyqtSignal(str)  # Single move string
    multiple_moves = pyqtSignal(list)  # List of moves
    clear_moves = pyqtSignal()  # Clear all moves

    # Error signals
    error_occurred = pyqtSignal(str, str)  # (title, message)

    # Process lifecycle signals
    bot_started = pyqtSignal()
    bot_stopped = pyqtSignal()
    browser_opened = pyqtSignal()
    browser_closed = pyqtSignal()

    # Restart signal
    restart_requested = pyqtSignal()

    # Download progress
    download_progress = pyqtSignal(int, str)  # (percent, message)
    download_complete = pyqtSignal(str)  # (path or empty string on failure)

    # Keyboard shortcuts
    key_start_pressed = pyqtSignal()
    key_stop_pressed = pyqtSignal()
