"""
Moves Table Widget - Chess move history display
"""
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt6.QtCore import Qt


class MovesTable(QTableWidget):
    """
    A table widget for displaying chess move history.
    Shows move number, white's move, and black's move.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Setup table structure
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["#", "White", "Black"])

        # Configure header
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(0, 45)

        # Hide vertical header (row numbers)
        self.verticalHeader().setVisible(False)

        # Configure selection and editing
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Enable alternating row colors
        self.setAlternatingRowColors(True)

        # Show grid
        self.setShowGrid(False)

        # Track moves for export
        self._moves = []

    def add_move(self, move: str):
        """
        Add a single move to the table.
        Automatically pairs white and black moves.
        """
        self._moves.append(move)

        row_count = self.rowCount()
        if row_count == 0 or self.item(row_count - 1, 2) is not None:
            # Need new row (white's move)
            self.insertRow(row_count)
            self._set_cell(row_count, 0, str(row_count + 1))
            self._set_cell(row_count, 1, move)
        else:
            # Add to existing row (black's move)
            self._set_cell(row_count - 1, 2, move)

        self.scrollToBottom()

    def set_moves(self, moves: list):
        """
        Replace all moves with a new list.
        """
        self.clear_moves()
        self._moves = list(moves)

        for i in range(0, len(moves), 2):
            row = self.rowCount()
            self.insertRow(row)
            self._set_cell(row, 0, str(row + 1))
            self._set_cell(row, 1, moves[i])
            if i + 1 < len(moves):
                self._set_cell(row, 2, moves[i + 1])

        self.scrollToBottom()

    def clear_moves(self):
        """Clear all moves from the table"""
        self.setRowCount(0)
        self._moves = []

    def get_moves(self) -> list:
        """Get all moves as a list"""
        return list(self._moves)

    def get_pgn(self) -> str:
        """
        Generate PGN notation from the moves.
        Returns formatted string with move numbers.
        """
        pgn_parts = []
        for i in range(0, len(self._moves), 2):
            move_num = i // 2 + 1
            white_move = self._moves[i]
            if i + 1 < len(self._moves):
                black_move = self._moves[i + 1]
                pgn_parts.append(f"{move_num}. {white_move} {black_move}")
            else:
                pgn_parts.append(f"{move_num}. {white_move}")

        return " ".join(pgn_parts)

    def _set_cell(self, row: int, col: int, text: str):
        """Set cell text with center alignment"""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, col, item)
