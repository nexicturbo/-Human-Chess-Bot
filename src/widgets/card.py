"""
Card Widget - Modern card container with rounded corners
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt


class Card(QFrame):
    """
    A modern card container widget with optional title.
    Used to group related UI elements.
    """

    def __init__(self, title: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")

        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

        # Add title if provided
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("title")
            self._layout.addWidget(title_label)

    def addWidget(self, widget, stretch=0):
        """Add a widget to the card"""
        self._layout.addWidget(widget, stretch)

    def addLayout(self, layout, stretch=0):
        """Add a layout to the card"""
        self._layout.addLayout(layout, stretch)

    def addSpacing(self, size: int):
        """Add spacing between elements"""
        self._layout.addSpacing(size)

    def addStretch(self, stretch: int = 1):
        """Add stretch to push elements"""
        self._layout.addStretch(stretch)

    def setSpacing(self, spacing: int):
        """Set the spacing between elements"""
        self._layout.setSpacing(spacing)


class StatusCard(QFrame):
    """
    Horizontal status bar card showing game metrics.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(20)

        # Status
        self.status_label = self._create_metric("Status:", "Inactive")
        self.status_value.setObjectName("statusInactive")
        layout.addLayout(self.status_label)

        self._add_separator(layout)

        # Eval
        self.eval_label = self._create_metric("Eval:", "-")
        layout.addLayout(self.eval_label)

        self._add_separator(layout)

        # WDL
        self.wdl_label = self._create_metric("WDL:", "-")
        layout.addLayout(self.wdl_label)

        self._add_separator(layout)

        # Material
        self.material_label = self._create_metric("Material:", "-")
        layout.addLayout(self.material_label)

        self._add_separator(layout)

        # Bot Accuracy
        self.bot_acc_label = self._create_metric("Bot Acc:", "-")
        layout.addLayout(self.bot_acc_label)

        self._add_separator(layout)

        # Opponent Accuracy
        self.opp_acc_label = self._create_metric("Opp Acc:", "-")
        layout.addLayout(self.opp_acc_label)

        layout.addStretch()

    def _create_metric(self, label_text: str, initial_value: str):
        """Create a label-value pair"""
        layout = QHBoxLayout()
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("muted")

        value = QLabel(initial_value)

        layout.addWidget(label)
        layout.addWidget(value)

        # Store reference to value label
        attr_name = label_text.lower().replace(":", "").replace(" ", "_") + "_value"
        attr_name = attr_name.replace(".", "")
        setattr(self, attr_name.replace("_value", "") + "_value", value)

        return layout

    def _add_separator(self, layout):
        """Add a visual separator"""
        sep = QLabel("|")
        sep.setObjectName("muted")
        layout.addWidget(sep)

    def set_status(self, text: str, is_running: bool):
        """Update status display"""
        self.status_value.setText(text)
        if is_running:
            self.status_value.setObjectName("statusRunning")
        else:
            self.status_value.setObjectName("statusInactive")
        # Force style refresh
        self.status_value.style().unpolish(self.status_value)
        self.status_value.style().polish(self.status_value)

    def set_eval(self, text: str):
        """Update evaluation display with color"""
        self.eval_value.setText(text)
        if text.startswith("+") or text.startswith("M"):
            self.eval_value.setObjectName("evalPositive")
        elif text.startswith("-") or text.startswith("-M"):
            self.eval_value.setObjectName("evalNegative")
        else:
            self.eval_value.setObjectName("evalNeutral")
        self.eval_value.style().unpolish(self.eval_value)
        self.eval_value.style().polish(self.eval_value)

    def set_wdl(self, text: str):
        """Update WDL display"""
        self.wdl_value.setText(text)

    def set_material(self, text: str):
        """Update material display with color"""
        self.material_value.setText(text)
        if text.startswith("+"):
            self.material_value.setObjectName("evalPositive")
        elif text.startswith("-"):
            self.material_value.setObjectName("evalNegative")
        else:
            self.material_value.setObjectName("evalNeutral")
        self.material_value.style().unpolish(self.material_value)
        self.material_value.style().polish(self.material_value)

    def set_bot_accuracy(self, text: str):
        """Update bot accuracy display"""
        self.bot_acc_value.setText(text)

    def set_opponent_accuracy(self, text: str):
        """Update opponent accuracy display"""
        self.opp_acc_value.setText(text)

    def reset(self):
        """Reset all values to default"""
        self.set_status("Inactive", False)
        self.eval_value.setText("-")
        self.eval_value.setObjectName("evalNeutral")
        self.wdl_value.setText("-")
        self.material_value.setText("-")
        self.material_value.setObjectName("evalNeutral")
        self.bot_acc_value.setText("-")
        self.opp_acc_value.setText("-")
