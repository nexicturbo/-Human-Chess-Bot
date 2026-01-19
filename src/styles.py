"""
PawnBit Dark Theme Styles
Modern neutral dark color palette and Qt Style Sheets
"""

# Color Palette - Modern Neutral Dark Theme
COLORS = {
    # Base colors - Charcoal/Dark Gray
    "background": "#121212",
    "surface": "#1e1e1e",
    "surface_hover": "#2a2a2a",
    "surface_border": "#333333",

    # Text colors
    "text_primary": "#e4e4e7",
    "text_secondary": "#a1a1aa",
    "text_disabled": "#52525b",

    # Accent colors - Teal/Cyan
    "accent": "#14b8a6",
    "accent_hover": "#2dd4bf",
    "accent_pressed": "#0d9488",

    # Status colors
    "success": "#22c55e",
    "error": "#ef4444",
    "warning": "#f59e0b",
    "neutral": "#71717a",

    # Evaluation colors
    "eval_positive": "#22c55e",
    "eval_negative": "#ef4444",
    "eval_neutral": "#a1a1aa",

    # Table colors
    "table_header": "#272727",
    "table_row_alt": "#1a1a1a",
    "table_row": "#1e1e1e",
    "table_selection": "#14b8a6",
}

# Main application stylesheet
MAIN_STYLESHEET = """
/* Main Window */
QMainWindow, QWidget#centralWidget {
    background-color: #121212;
}

/* Generic QWidget background */
QWidget {
    background-color: transparent;
    color: #e4e4e7;
    font-family: "Segoe UI", "Arial", sans-serif;
}

/* Cards (QFrame with objectName "card") */
QFrame#card {
    background-color: #1e1e1e;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
}

/* Labels */
QLabel {
    color: #e4e4e7;
    font-size: 13px;
    background-color: transparent;
}

QLabel#title {
    font-size: 15px;
    font-weight: 600;
    color: #ffffff;
    padding-bottom: 4px;
}

QLabel#muted {
    color: #71717a;
    font-size: 12px;
}

QLabel#statusRunning {
    color: #22c55e;
    font-weight: bold;
}

QLabel#statusInactive {
    color: #ef4444;
    font-weight: bold;
}

QLabel#evalPositive {
    color: #22c55e;
    font-weight: bold;
}

QLabel#evalNegative {
    color: #ef4444;
    font-weight: bold;
}

QLabel#evalNeutral {
    color: #a1a1aa;
}

/* Buttons */
QPushButton {
    background-color: #27272a;
    color: #e4e4e7;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 500;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}

QPushButton:pressed {
    background-color: #18181b;
}

QPushButton:disabled {
    background-color: #1e1e1e;
    color: #52525b;
    border-color: #27272a;
}

QPushButton#primary {
    background-color: #14b8a6;
    color: #042f2e;
    border: none;
    font-weight: 600;
}

QPushButton#primary:hover {
    background-color: #2dd4bf;
}

QPushButton#primary:pressed {
    background-color: #0d9488;
}

QPushButton#danger {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
}

QPushButton#danger:hover {
    background-color: #ef4444;
}

QPushButton#danger:pressed {
    background-color: #b91c1c;
}

/* Radio Buttons */
QRadioButton {
    color: #e4e4e7;
    spacing: 10px;
    font-size: 13px;
    padding: 4px 0;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 2px solid #3f3f46;
    background-color: #27272a;
}

QRadioButton::indicator:hover {
    border-color: #52525b;
    background-color: #3f3f46;
}

QRadioButton::indicator:checked {
    background-color: #14b8a6;
    border-color: #14b8a6;
}

/* Checkboxes */
QCheckBox {
    color: #e4e4e7;
    spacing: 10px;
    font-size: 13px;
    padding: 4px 0;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #3f3f46;
    background-color: #27272a;
}

QCheckBox::indicator:hover {
    border-color: #52525b;
    background-color: #3f3f46;
}

QCheckBox::indicator:checked {
    background-color: #14b8a6;
    border-color: #14b8a6;
}

QCheckBox::indicator:disabled {
    background-color: #18181b;
    border-color: #27272a;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background-color: #27272a;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 18px;
    height: 18px;
    margin: -6px 0;
    background-color: #14b8a6;
    border-radius: 9px;
}

QSlider::handle:horizontal:hover {
    background-color: #2dd4bf;
}

QSlider::sub-page:horizontal {
    background-color: #14b8a6;
    border-radius: 3px;
}

/* Spin Boxes */
QSpinBox, QDoubleSpinBox {
    background-color: #27272a;
    color: #e4e4e7;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    min-width: 80px;
    selection-background-color: #14b8a6;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #14b8a6;
}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #3f3f46;
    border: none;
    width: 20px;
    border-radius: 2px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #52525b;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #a1a1aa;
    width: 0;
    height: 0;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #a1a1aa;
    width: 0;
    height: 0;
}

/* Line Edit */
QLineEdit {
    background-color: #27272a;
    color: #e4e4e7;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #14b8a6;
}

QLineEdit:focus {
    border-color: #14b8a6;
}

/* Table Widget */
QTableWidget {
    background-color: #1e1e1e;
    gridline-color: #27272a;
    border: 1px solid #27272a;
    border-radius: 8px;
    font-size: 13px;
    outline: none;
}

QTableWidget::item {
    color: #e4e4e7;
    padding: 10px;
    border: none;
}

QTableWidget::item:selected {
    background-color: #14b8a6;
    color: #042f2e;
}

QTableWidget::item:alternate {
    background-color: #171717;
}

QHeaderView::section {
    background-color: #27272a;
    color: #e4e4e7;
    padding: 12px;
    border: none;
    font-weight: 600;
    font-size: 13px;
}

QTableCornerButton::section {
    background-color: #27272a;
    border: none;
}

/* Scrollbars */
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 10px;
    border-radius: 5px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #3f3f46;
    border-radius: 5px;
    min-height: 30px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #52525b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background-color: transparent;
}

QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 10px;
    border-radius: 5px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #3f3f46;
    border-radius: 5px;
    min-width: 30px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #52525b;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Progress Bar */
QProgressBar {
    background-color: #27272a;
    border-radius: 6px;
    height: 20px;
    text-align: center;
    color: #e4e4e7;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #14b8a6;
    border-radius: 6px;
}

/* Message Box */
QMessageBox {
    background-color: #1e1e1e;
}

QMessageBox QLabel {
    color: #e4e4e7;
}

QMessageBox QPushButton {
    min-width: 80px;
}

/* Tool Tips */
QToolTip {
    background-color: #27272a;
    color: #e4e4e7;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
}

/* Group Box */
QGroupBox {
    font-weight: bold;
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
}

QGroupBox::title {
    color: #e4e4e7;
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
}

/* File Dialog */
QFileDialog {
    background-color: #1e1e1e;
}

/* Progress Dialog */
QProgressDialog {
    background-color: #1e1e1e;
}
"""
