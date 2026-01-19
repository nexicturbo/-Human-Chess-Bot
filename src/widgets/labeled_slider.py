"""
Labeled Slider Widget - Slider with label and live value display
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSlider
from PyQt6.QtCore import Qt, pyqtSignal


class LabeledSlider(QWidget):
    """
    A slider with a label and a value display that updates in real-time.
    Supports both integer and decimal values.
    """

    valueChanged = pyqtSignal(float)

    def __init__(
        self,
        label: str,
        min_val: float,
        max_val: float,
        default_val: float = None,
        step: float = 1.0,
        suffix: str = "",
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        parent=None
    ):
        super().__init__(parent)

        self.step = step
        self.suffix = suffix
        self.multiplier = int(1 / step) if step < 1 else 1

        if orientation == Qt.Orientation.Horizontal:
            self._setup_horizontal(label, min_val, max_val, default_val)
        else:
            self._setup_vertical(label, min_val, max_val, default_val)

    def _setup_horizontal(self, label: str, min_val: float, max_val: float, default_val: float):
        """Setup horizontal slider layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Top row: label and value
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(label)
        self.value_label = QLabel()

        top_layout.addWidget(self.label)
        top_layout.addStretch()
        top_layout.addWidget(self.value_label)

        layout.addLayout(top_layout)

        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(min_val * self.multiplier))
        self.slider.setMaximum(int(max_val * self.multiplier))
        # Set step size for keyboard/click increments
        self.slider.setSingleStep(int(self.step * self.multiplier))
        self.slider.setPageStep(int(self.step * self.multiplier))
        self.slider.setTickInterval(int(self.step * self.multiplier))

        if default_val is not None:
            self.slider.setValue(int(default_val * self.multiplier))
        else:
            self.slider.setValue(int(min_val * self.multiplier))

        self.slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.slider)

        # Initialize value display
        self._update_value_display()

    def _setup_vertical(self, label: str, min_val: float, max_val: float, default_val: float):
        """Setup vertical slider layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Label
        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        # Slider
        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setMinimum(int(min_val * self.multiplier))
        self.slider.setMaximum(int(max_val * self.multiplier))
        # Set step size for keyboard/click increments
        self.slider.setSingleStep(int(self.step * self.multiplier))
        self.slider.setPageStep(int(self.step * self.multiplier))
        self.slider.setTickInterval(int(self.step * self.multiplier))

        if default_val is not None:
            self.slider.setValue(int(default_val * self.multiplier))
        else:
            self.slider.setValue(int(min_val * self.multiplier))

        self.slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.slider, 1, Qt.AlignmentFlag.AlignCenter)

        # Value label
        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

        # Initialize value display
        self._update_value_display()

    def _on_value_changed(self, value: int):
        """Handle slider value change - snaps to step increments"""
        # Snap to nearest step
        step_int = int(self.step * self.multiplier)
        if step_int > 1:
            min_val = self.slider.minimum()
            snapped = min_val + round((value - min_val) / step_int) * step_int
            if snapped != value:
                self.slider.blockSignals(True)
                self.slider.setValue(snapped)
                self.slider.blockSignals(False)
                value = snapped

        self._update_value_display()
        real_value = value / self.multiplier
        self.valueChanged.emit(real_value)

    def _update_value_display(self):
        """Update the value label text"""
        real_value = self.slider.value() / self.multiplier
        if self.step >= 1:
            text = f"{int(real_value)}{self.suffix}"
        else:
            decimals = len(str(self.step).split('.')[-1])
            text = f"{real_value:.{decimals}f}{self.suffix}"
        self.value_label.setText(text)

    def value(self) -> float:
        """Get the current value"""
        return self.slider.value() / self.multiplier

    def setValue(self, value: float):
        """Set the slider value"""
        self.slider.setValue(int(value * self.multiplier))

    def setEnabled(self, enabled: bool):
        """Enable or disable the slider"""
        super().setEnabled(enabled)
        self.slider.setEnabled(enabled)
        self.label.setEnabled(enabled)
        self.value_label.setEnabled(enabled)
