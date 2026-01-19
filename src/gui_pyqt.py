"""
PawnBit Modern GUI - PyQt6 Implementation
A modern dark-themed interface for the chess bot
"""
import os
import platform
import sys

import multiprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QRadioButton, QCheckBox, QSpinBox,
    QButtonGroup, QFileDialog, QMessageBox, QProgressDialog,
    QSizePolicy, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSlot, QSize
from PyQt6.QtGui import QIcon, QFont

from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common import WebDriverException

from styles import MAIN_STYLESHEET, COLORS
from signals import GUISignals
from widgets import Card, LabeledSlider, MovesTable
from widgets.card import StatusCard
from workers import (
    ProcessCheckerWorker, BrowserCheckerWorker,
    PipeCommunicatorWorker, KeyboardListenerWorker, DownloadWorker
)
from stockfish_bot import StockfishBot
from stockfish_manager import is_stockfish_installed, get_stockfish_path, verify_stockfish
from overlay import run as run_overlay


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # State variables
        self.running = False
        self.opening_browser = False
        self.browser_open = False
        self.stockfish_path = ""
        self.match_moves = []

        # Process and IPC
        self.chrome = None
        self.chrome_url = None
        self.chrome_session_id = None
        self.stockfish_bot_pipe = None
        self.stockfish_bot_process = None
        self.overlay_process = None
        self.overlay_queue = None

        # Signals for thread-safe communication
        self.signals = GUISignals()
        self._connect_signals()

        # Setup UI
        self._setup_window()
        self._setup_ui()
        self._setup_workers()

        # Check for existing Stockfish installation
        self._check_auto_stockfish()

    def _setup_window(self):
        """Configure main window properties"""
        self.setWindowTitle("PawnBit Chess Bot")
        self.setMinimumSize(800, 700)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "pawn_32x32.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Apply dark theme
        self.setStyleSheet(MAIN_STYLESHEET)

        # Start with window on top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    def _setup_ui(self):
        """Setup the main UI layout"""
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Status bar at top
        self.status_card = StatusCard()
        main_layout.addWidget(self.status_card)

        # Content area (3 columns)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left column
        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        self._setup_left_column(left_column)
        content_layout.addLayout(left_column)

        # Middle column (in scroll area to handle overflow)
        middle_scroll = QScrollArea()
        middle_scroll.setWidgetResizable(True)
        middle_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        middle_scroll.setFrameShape(QFrame.Shape.NoFrame)
        middle_scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")

        middle_widget = QWidget()
        middle_column = QVBoxLayout(middle_widget)
        middle_column.setSpacing(12)
        middle_column.setContentsMargins(0, 0, 8, 0)  # Right margin for scrollbar
        self._setup_middle_column(middle_column)

        middle_scroll.setWidget(middle_widget)
        middle_scroll.setMinimumWidth(250)
        content_layout.addWidget(middle_scroll)

        # Right column (moves table)
        right_column = QVBoxLayout()
        right_column.setSpacing(12)
        self._setup_right_column(right_column)
        content_layout.addLayout(right_column, 1)  # Give it stretch

        main_layout.addLayout(content_layout, 1)

    def _setup_left_column(self, layout):
        """Setup the left column with connection and modes"""
        # Connection Card
        connection_card = Card("Connection")

        # Website selection
        website_layout = QVBoxLayout()
        website_label = QLabel("Website")
        website_label.setObjectName("muted")
        website_layout.addWidget(website_label)

        self.website_group = QButtonGroup(self)
        self.chesscom_radio = QRadioButton("Chess.com")
        self.lichess_radio = QRadioButton("Lichess.org")
        self.chesscom_radio.setChecked(True)
        self.website_group.addButton(self.chesscom_radio)
        self.website_group.addButton(self.lichess_radio)

        website_layout.addWidget(self.chesscom_radio)
        website_layout.addWidget(self.lichess_radio)
        connection_card.addLayout(website_layout)

        connection_card.addSpacing(8)

        # Browser button
        self.browser_btn = QPushButton("Open Browser")
        self.browser_btn.clicked.connect(self._on_open_browser)
        connection_card.addWidget(self.browser_btn)

        # Start/Stop button
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("primary")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._on_start_stop)
        connection_card.addWidget(self.start_btn)

        layout.addWidget(connection_card)

        # Play Modes Card
        modes_card = Card("Play Modes")

        self.manual_mode_cb = QCheckBox("Manual Mode")
        self.manual_mode_cb.stateChanged.connect(self._on_manual_mode_changed)
        modes_card.addWidget(self.manual_mode_cb)

        self.manual_hint = QLabel("Press 3 to make a move")
        self.manual_hint.setObjectName("muted")
        self.manual_hint.setVisible(False)
        modes_card.addWidget(self.manual_hint)

        self.nonstop_matches_cb = QCheckBox("Non-stop Matches")
        modes_card.addWidget(self.nonstop_matches_cb)

        self.human_mode_cb = QCheckBox("Human Mode")
        self.human_mode_cb.stateChanged.connect(self._on_human_mode_changed)
        modes_card.addWidget(self.human_mode_cb)

        self.human_mode_hint = QLabel("Uses Maia AI for human-like play")
        self.human_mode_hint.setObjectName("muted")
        self.human_mode_hint.setVisible(False)
        modes_card.addWidget(self.human_mode_hint)

        layout.addWidget(modes_card)

        # Timing Card
        timing_card = Card("Timing")
        self.latency_slider = LabeledSlider(
            "Mouse Latency",
            min_val=0.0,
            max_val=15.0,
            default_val=0.0,
            step=0.2,
            suffix=" sec"
        )
        timing_card.addWidget(self.latency_slider)
        layout.addWidget(timing_card)

        layout.addStretch()

    def _setup_middle_column(self, layout):
        """Setup the middle column with engine settings"""
        # Engine Card
        engine_card = Card("Engine Settings")

        # Slow Mover
        slow_layout = QHBoxLayout()
        slow_label = QLabel("Slow Mover")
        self.slow_mover_spin = QSpinBox()
        self.slow_mover_spin.setRange(10, 1000)
        self.slow_mover_spin.setValue(100)
        slow_layout.addWidget(slow_label)
        slow_layout.addStretch()
        slow_layout.addWidget(self.slow_mover_spin)
        engine_card.addLayout(slow_layout)

        # Skill Level
        self.skill_slider = LabeledSlider(
            "Skill Level",
            min_val=0,
            max_val=20,
            default_val=20,
            step=1
        )
        engine_card.addWidget(self.skill_slider)

        # Depth
        self.depth_slider = LabeledSlider(
            "Depth",
            min_val=1,
            max_val=20,
            default_val=15,
            step=1
        )
        engine_card.addWidget(self.depth_slider)

        # Memory
        memory_layout = QHBoxLayout()
        memory_label = QLabel("Memory")
        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(16, 16384)
        self.memory_spin.setValue(512)
        memory_unit = QLabel("MB")
        memory_layout.addWidget(memory_label)
        memory_layout.addStretch()
        memory_layout.addWidget(self.memory_spin)
        memory_layout.addWidget(memory_unit)
        engine_card.addLayout(memory_layout)

        # CPU Threads
        threads_layout = QHBoxLayout()
        threads_label = QLabel("CPU Threads")
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 128)
        self.threads_spin.setValue(1)
        threads_layout.addWidget(threads_label)
        threads_layout.addStretch()
        threads_layout.addWidget(self.threads_spin)
        engine_card.addLayout(threads_layout)

        layout.addWidget(engine_card)

        # Stockfish Card
        stockfish_card = Card("Stockfish")

        btn_layout = QHBoxLayout()
        self.select_sf_btn = QPushButton("Select")
        self.select_sf_btn.clicked.connect(self._on_select_stockfish)
        self.download_sf_btn = QPushButton("Auto Download")
        self.download_sf_btn.clicked.connect(self._on_download_stockfish)
        btn_layout.addWidget(self.select_sf_btn)
        btn_layout.addWidget(self.download_sf_btn)
        stockfish_card.addLayout(btn_layout)

        self.stockfish_path_label = QLabel("No Stockfish selected")
        self.stockfish_path_label.setObjectName("muted")
        self.stockfish_path_label.setWordWrap(True)
        stockfish_card.addWidget(self.stockfish_path_label)

        layout.addWidget(stockfish_card)

        # Human Mode Settings Card
        self.human_mode_card = Card("Human Mode Settings")

        # ELO Slider (Maia-1 has weights at 100-point intervals: 1100-1900)
        self.maia_elo_slider = LabeledSlider(
            "Maia ELO",
            min_val=1100,
            max_val=1900,
            default_val=1500,
            step=100
        )
        self.human_mode_card.addWidget(self.maia_elo_slider)

        # Time Control Selection
        tc_layout = QHBoxLayout()
        tc_label = QLabel("Time Control")
        self.maia_tc_group = QButtonGroup(self)
        self.maia_rapid_radio = QRadioButton("Rapid")
        self.maia_blitz_radio = QRadioButton("Blitz")
        self.maia_rapid_radio.setChecked(True)
        self.maia_tc_group.addButton(self.maia_rapid_radio)
        self.maia_tc_group.addButton(self.maia_blitz_radio)
        tc_layout.addWidget(tc_label)
        tc_layout.addStretch()
        tc_layout.addWidget(self.maia_rapid_radio)
        tc_layout.addWidget(self.maia_blitz_radio)
        self.human_mode_card.addLayout(tc_layout)

        # GPU Checkbox
        self.maia_gpu_cb = QCheckBox("Use GPU (if available)")
        self.maia_gpu_cb.setChecked(True)
        self.human_mode_card.addWidget(self.maia_gpu_cb)

        # Initially hidden
        self.human_mode_card.setVisible(False)
        layout.addWidget(self.human_mode_card)

        # Misc Card
        misc_card = Card("Misc")
        self.topmost_cb = QCheckBox("Window stays on top")
        self.topmost_cb.setChecked(True)
        self.topmost_cb.stateChanged.connect(self._on_topmost_changed)
        misc_card.addWidget(self.topmost_cb)
        layout.addWidget(misc_card)

        layout.addStretch()

    def _setup_right_column(self, layout):
        """Setup the right column with moves table"""
        # Moves Card
        moves_card = Card("Moves")
        moves_card.setSpacing(8)

        self.moves_table = MovesTable()
        self.moves_table.setMinimumWidth(200)
        moves_card.addWidget(self.moves_table, 1)

        self.export_btn = QPushButton("Export PGN")
        self.export_btn.clicked.connect(self._on_export_pgn)
        moves_card.addWidget(self.export_btn)

        layout.addWidget(moves_card)

    def _connect_signals(self):
        """Connect custom signals to slots"""
        self.signals.bot_started.connect(self._on_bot_started)
        self.signals.bot_stopped.connect(self._on_bot_stopped)
        self.signals.browser_closed.connect(self._on_browser_closed)
        self.signals.restart_requested.connect(self._on_restart_requested)

        self.signals.single_move.connect(self._on_single_move)
        self.signals.multiple_moves.connect(self._on_multiple_moves)
        self.signals.clear_moves.connect(self._on_clear_moves)

        self.signals.eval_updated.connect(self._on_eval_updated)
        self.signals.error_occurred.connect(self._on_error)

        self.signals.download_progress.connect(self._on_download_progress)
        self.signals.download_complete.connect(self._on_download_complete)

        self.signals.key_start_pressed.connect(self._on_key_start)
        self.signals.key_stop_pressed.connect(self._on_key_stop)

    def _setup_workers(self):
        """Setup background worker threads"""
        # Process checker
        self.process_checker_thread = QThread()
        self.process_checker = ProcessCheckerWorker(self.signals)
        self.process_checker.moveToThread(self.process_checker_thread)
        self.process_checker_thread.started.connect(self.process_checker.run)
        self.process_checker_thread.start()

        # Browser checker
        self.browser_checker_thread = QThread()
        self.browser_checker = BrowserCheckerWorker(self.signals)
        self.browser_checker.moveToThread(self.browser_checker_thread)
        self.browser_checker_thread.started.connect(self.browser_checker.run)
        self.browser_checker_thread.start()

        # Pipe communicator
        self.pipe_comm_thread = QThread()
        self.pipe_comm = PipeCommunicatorWorker(self.signals)
        self.pipe_comm.moveToThread(self.pipe_comm_thread)
        self.pipe_comm_thread.started.connect(self.pipe_comm.run)
        self.pipe_comm_thread.start()

        # Keyboard listener
        self.keyboard_thread = QThread()
        self.keyboard_listener = KeyboardListenerWorker(self.signals)
        self.keyboard_listener.moveToThread(self.keyboard_thread)
        self.keyboard_thread.started.connect(self.keyboard_listener.run)
        self.keyboard_thread.start()

    def _check_auto_stockfish(self):
        """Check if Stockfish is already installed"""
        if is_stockfish_installed():
            path = get_stockfish_path()
            if path and verify_stockfish(path):
                self.stockfish_path = path
                self.stockfish_path_label.setText(f"(Auto) {path}")
                self.download_sf_btn.setText("Reinstall")

    # ==================== Event Handlers ====================

    def _on_open_browser(self):
        """Handle Open Browser button click"""
        if self.opening_browser:
            return

        self.opening_browser = True
        self.browser_btn.setEnabled(False)
        self.browser_btn.setText("Opening...")

        # Configure Chrome options
        options = webdriver.ChromeOptions()
        options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('useAutomationExtension', False)

        # Use persistent profile directory to save login sessions
        profile_dir = os.path.join(os.path.expanduser("~"), ".pawnbit", "chrome_profile")
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f'--user-data-dir={profile_dir}')

        try:
            chrome_install = ChromeDriverManager().install()

            # Cross-platform chromedriver path
            folder = os.path.dirname(chrome_install)
            if platform.system() == "Windows":
                chromedriver_path = os.path.join(folder, "chromedriver.exe")
            else:
                chromedriver_path = os.path.join(folder, "chromedriver")

            if not os.path.exists(chromedriver_path):
                chromedriver_path = chrome_install

            service = ChromeService(chromedriver_path)
            self.chrome = webdriver.Chrome(service=service, options=options)

        except WebDriverException:
            self.opening_browser = False
            self.browser_btn.setEnabled(True)
            self.browser_btn.setText("Open Browser")
            QMessageBox.critical(
                self, "Error",
                "Could not open Chrome browser.\nMake sure Google Chrome is installed."
            )
            return
        except Exception as e:
            self.opening_browser = False
            self.browser_btn.setEnabled(True)
            self.browser_btn.setText("Open Browser")
            QMessageBox.critical(self, "Error", f"Failed to open browser:\n{str(e)}")
            return

        # Navigate to selected website
        if self.chesscom_radio.isChecked():
            self.chrome.get("https://www.chess.com")
        else:
            self.chrome.get("https://lichess.org")

        # Store session info
        self.chrome_url = self.chrome.service.service_url
        self.chrome_session_id = self.chrome.session_id

        # Update UI
        self.browser_btn.setText("Browser Open")
        self.start_btn.setEnabled(True)
        self.browser_open = True
        self.opening_browser = False

        # Setup browser monitoring
        self.browser_checker.set_chrome(self.chrome)
        self.keyboard_listener.set_browser_open(True)

    def _on_start_stop(self):
        """Handle Start/Stop button click"""
        print(f"[DEBUG] Start/Stop clicked. running={self.running}")
        if self.running:
            self._stop_bot()
        else:
            self._start_bot()

    def _start_bot(self):
        """Start the chess bot"""
        print("[DEBUG] _start_bot called")

        # Clear moves from previous game
        self.match_moves = []
        self.moves_table.clear_moves()
        self.status_card.reset()

        # Validate slow mover
        slow_mover = self.slow_mover_spin.value()
        if slow_mover < 10 or slow_mover > 1000:
            QMessageBox.warning(self, "Invalid Value", "Slow Mover must be between 10 and 1000")
            return

        # Validate stockfish path
        if not self.stockfish_path:
            QMessageBox.warning(self, "No Stockfish", "Please select or download Stockfish first.")
            return

        # Check mode compatibility
        # Update UI
        self.start_btn.setText("Starting...")
        self.start_btn.setEnabled(False)

        # Create communication channels
        parent_conn, child_conn = multiprocess.Pipe()
        self.stockfish_bot_pipe = parent_conn
        self.overlay_queue = multiprocess.Queue()

        # Get website
        website = "chesscom" if self.chesscom_radio.isChecked() else "lichess"

        # Create and start StockfishBot process
        self.stockfish_bot_process = StockfishBot(
            pipe=child_conn,
            overlay_queue=self.overlay_queue,
            chrome_url=self.chrome_url,
            chrome_session_id=self.chrome_session_id,
            stockfish_path=self.stockfish_path,
            website=website,
            enable_manual_mode=self.manual_mode_cb.isChecked(),
            enable_non_stop_matches=self.nonstop_matches_cb.isChecked(),
            mouse_latency=self.latency_slider.value(),
            slow_mover=slow_mover,
            skill_level=int(self.skill_slider.value()),
            stockfish_depth=int(self.depth_slider.value()),
            memory=self.memory_spin.value(),
            cpu_threads=self.threads_spin.value(),
            enable_human_mode=self.human_mode_cb.isChecked(),
            maia_elo=int(self.maia_elo_slider.value()),
            maia_time_control="rapid" if self.maia_rapid_radio.isChecked() else "blitz",
            maia_use_gpu=self.maia_gpu_cb.isChecked()
        )
        self.stockfish_bot_process.start()

        # Create and start overlay process
        self.overlay_process = multiprocess.Process(
            target=run_overlay,
            args=(self.overlay_queue,)
        )
        self.overlay_process.start()

        # Update workers
        self.process_checker.set_process(self.stockfish_bot_process)
        self.pipe_comm.set_pipe(self.stockfish_bot_pipe)

        self.running = True

    def _stop_bot(self):
        """Stop the chess bot"""
        print("[DEBUG] _stop_bot called")

        # Kill overlay
        if self.overlay_process and self.overlay_process.is_alive():
            self.overlay_process.kill()
            self.overlay_process = None

        # Send delete command and kill bot
        if self.stockfish_bot_pipe:
            try:
                self.stockfish_bot_pipe.send("DELETE")
            except (BrokenPipeError, OSError):
                pass

        if self.stockfish_bot_process and self.stockfish_bot_process.is_alive():
            self.stockfish_bot_process.kill()
            self.stockfish_bot_process = None

        # Close pipe
        if self.stockfish_bot_pipe:
            try:
                self.stockfish_bot_pipe.close()
            except Exception:
                pass
            self.stockfish_bot_pipe = None

        # Update workers
        self.process_checker.set_process(None)
        self.pipe_comm.set_pipe(None)

        # Reset UI
        self.running = False
        self.start_btn.setText("Start")
        self.start_btn.setObjectName("primary")
        self.start_btn.setEnabled(True)
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)

        self.status_card.reset()
        print(f"[DEBUG] _stop_bot completed. running={self.running}")

    def _on_manual_mode_changed(self, state):
        """Handle manual mode checkbox change"""
        self.manual_hint.setVisible(state == Qt.CheckState.Checked.value)

    def _on_human_mode_changed(self, state):
        """Handle human mode checkbox change"""
        is_enabled = state == Qt.CheckState.Checked.value
        self.human_mode_hint.setVisible(is_enabled)
        self.human_mode_card.setVisible(is_enabled)

        # Disable Stockfish-specific settings when Human Mode is active
        self.skill_slider.setEnabled(not is_enabled)
        self.depth_slider.setEnabled(not is_enabled)

        # Adjust window size to accommodate Human Mode Settings card
        if is_enabled:
            # Expand window to fit all content without scrolling
            self.resize(self.width(), 950)
        else:
            # Shrink back to default
            self.resize(self.width(), 700)

    def _on_topmost_changed(self, state):
        """Handle stay on top checkbox change"""
        self.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint,
            state == Qt.CheckState.Checked.value
        )
        self.show()

    def _on_select_stockfish(self):
        """Handle Select Stockfish button click"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Stockfish Executable",
            "",
            "All Files (*)"
        )
        if path:
            self.stockfish_path = path
            self.stockfish_path_label.setText(path)

    def _on_download_stockfish(self):
        """Handle Auto Download button click"""
        self.download_sf_btn.setEnabled(False)
        self.download_sf_btn.setText("Downloading...")

        # Create progress dialog
        self.progress_dialog = QProgressDialog(
            "Downloading Stockfish...", None, 0, 100, self
        )
        self.progress_dialog.setWindowTitle("Downloading")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.show()

        # Start download worker
        self.download_thread = QThread()
        self.download_worker = DownloadWorker(self.signals)
        self.download_worker.moveToThread(self.download_thread)
        self.download_thread.started.connect(self.download_worker.run)
        self.download_thread.start()

    def _on_export_pgn(self):
        """Handle Export PGN button click"""
        if not self.moves_table.get_moves():
            QMessageBox.information(self, "No Moves", "No moves to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export PGN",
            "game.pgn",
            "PGN Files (*.pgn);;All Files (*)"
        )
        if path:
            try:
                with open(path, 'w') as f:
                    f.write(self.moves_table.get_pgn())
                QMessageBox.information(self, "Exported", f"PGN saved to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save PGN:\n{str(e)}")

    # ==================== Signal Slots ====================

    @pyqtSlot()
    def _on_bot_started(self):
        """Handle bot started signal"""
        self.running = True
        self.start_btn.setText("Stop")
        self.start_btn.setObjectName("danger")
        self.start_btn.setEnabled(True)
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)

        self.status_card.set_status("Running", True)

    @pyqtSlot()
    def _on_bot_stopped(self):
        """Handle bot stopped signal"""
        self._stop_bot()

    @pyqtSlot()
    def _on_browser_closed(self):
        """Handle browser closed signal"""
        self.browser_open = False
        self.keyboard_listener.set_browser_open(False)
        self.browser_btn.setText("Open Browser")
        self.browser_btn.setEnabled(True)
        self.start_btn.setEnabled(False)
        self.chrome = None

        if self.running:
            self._stop_bot()

    @pyqtSlot()
    def _on_restart_requested(self):
        """Handle restart request from bot"""
        if self.stockfish_bot_pipe:
            try:
                self.stockfish_bot_pipe.send("DELETE")
            except (BrokenPipeError, OSError):
                pass

    @pyqtSlot(str)
    def _on_single_move(self, move: str):
        """Handle single move from bot"""
        self.match_moves.append(move)
        self.moves_table.add_move(move)

    @pyqtSlot(list)
    def _on_multiple_moves(self, moves: list):
        """Handle multiple moves from bot"""
        self.match_moves = moves
        self.moves_table.set_moves(moves)

    @pyqtSlot()
    def _on_clear_moves(self):
        """Handle clear moves signal"""
        self.match_moves = []
        self.moves_table.clear_moves()

    @pyqtSlot(str, str, str, str, str)
    def _on_eval_updated(self, eval_str: str, wdl_str: str, material_str: str,
                         bot_acc: str, opp_acc: str):
        """Handle evaluation update from bot"""
        self.status_card.set_eval(eval_str)
        self.status_card.set_wdl(wdl_str)
        self.status_card.set_material(material_str)
        self.status_card.set_bot_accuracy(bot_acc)
        self.status_card.set_opponent_accuracy(opp_acc)

    @pyqtSlot(str, str)
    def _on_error(self, title: str, message: str):
        """Handle error signal"""
        QMessageBox.critical(self, title, message)
        if self.running:
            self._stop_bot()

    @pyqtSlot(int, str)
    def _on_download_progress(self, percent: int, message: str):
        """Handle download progress update"""
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.setValue(percent)
            self.progress_dialog.setLabelText(message)

    @pyqtSlot(str)
    def _on_download_complete(self, path: str):
        """Handle download completion"""
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        if hasattr(self, 'download_thread'):
            self.download_thread.quit()
            self.download_thread.wait()

        if path:
            self.stockfish_path = path
            self.stockfish_path_label.setText(f"(Auto) {path}")
            self.download_sf_btn.setText("Reinstall")
            QMessageBox.information(self, "Success", "Stockfish installed successfully!")
        else:
            QMessageBox.critical(
                self, "Error",
                "Failed to download Stockfish.\nPlease try again or download manually."
            )
            self.download_sf_btn.setText("Auto Download")

        self.download_sf_btn.setEnabled(True)

    @pyqtSlot()
    def _on_key_start(self):
        """Handle keyboard start shortcut"""
        if not self.running and self.browser_open:
            self._start_bot()

    @pyqtSlot()
    def _on_key_stop(self):
        """Handle keyboard stop shortcut"""
        if self.running:
            self._stop_bot()

    # ==================== Window Events ====================

    def closeEvent(self, event):
        """Handle window close"""
        # Stop all workers
        self.process_checker.stop()
        self.browser_checker.stop()
        self.pipe_comm.stop()
        self.keyboard_listener.stop()

        # Wait for threads
        self.process_checker_thread.quit()
        self.browser_checker_thread.quit()
        self.pipe_comm_thread.quit()
        self.keyboard_thread.quit()

        self.process_checker_thread.wait(1000)
        self.browser_checker_thread.wait(1000)
        self.pipe_comm_thread.wait(1000)
        self.keyboard_thread.wait(1000)

        # Stop bot if running
        if self.running:
            self._stop_bot()

        # Close browser
        if self.chrome:
            try:
                self.chrome.quit()
            except Exception:
                pass

        event.accept()


def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
