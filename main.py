import os
import sys
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSpinBox,
    QTextEdit,
    QMessageBox,
    QGroupBox,
)

# Simulation run will be killed if it exceeds this many seconds.
SIMULATION_TIMEOUT_SECONDS = 30


class SimulationRunner:
    """Handles validating inputs and actually launching the model exe."""

    MIN_TIME = 0
    MAX_TIME = 5

    def __init__(self, exe_path: str, start: int, stop: int) -> None:
        """Store the executable path and the requested start/stop times."""
        self.exe_path = exe_path
        self.start = start
        self.stop = stop

    def validate(self) -> None:
        """Raise ValueError if the exe path or time range is invalid."""
        if not self.exe_path:
            raise ValueError("Please select an executable first.")

        if not Path(self.exe_path).is_file():
            raise ValueError("That executable path doesn't exist.")

        if not (self.MIN_TIME <= self.start < self.stop < self.MAX_TIME):
            raise ValueError(
                f"Times must satisfy {self.MIN_TIME} <= start < stop < "
                f"{self.MAX_TIME}"
            )

    def run(self) -> str:
        """Validate inputs, run the executable, and return its output.

        Raises:
            ValueError: if inputs fail validation.
            OSError: if the executable can't be launched.
            subprocess.TimeoutExpired: if the simulation exceeds the
                configured timeout.
        """
        self.validate()

        cmd = [
            self.exe_path,
            f"-startTime={self.start}",
            f"-stopTime={self.stop}",
        ]

        # bundled DLLs live in a bin/ folder next to the exe, if present
        env = os.environ.copy()
        bin_dir = Path(self.exe_path).parent / "bin"
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(self.exe_path).parent),
            env=env,
            timeout=SIMULATION_TIMEOUT_SECONDS,
        )

        output = f"Return code: {result.returncode}\n\n{result.stdout}"
        if result.stderr:
            output += f"\n--- stderr ---\n{result.stderr}"

        return output


class MainWindow(QWidget):
    """Main application window: parameter inputs, run button, output log."""

    def __init__(self) -> None:
        """Build the window and its widgets."""
        super().__init__()
        self.setWindowTitle("OpenModelica Model Runner")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create and lay out all widgets in the window."""
        layout = QVBoxLayout()

        group = QGroupBox("Simulation Parameters")
        group_layout = QVBoxLayout()

        # executable picker
        exe_row = QHBoxLayout()
        self.exe_input = QLineEdit()
        self.exe_input.setPlaceholderText("Select the model executable (.exe)")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._pick_exe)
        exe_row.addWidget(QLabel("Executable:"))
        exe_row.addWidget(self.exe_input)
        exe_row.addWidget(browse_btn)
        group_layout.addLayout(exe_row)

        # start time (capped to the valid 0 <= start < stop < 5 range)
        start_row = QHBoxLayout()
        self.start_input = QSpinBox()
        self.start_input.setRange(0, 4)
        start_row.addWidget(QLabel("Start Time:"))
        start_row.addWidget(self.start_input)
        group_layout.addLayout(start_row)

        # stop time (capped to the valid 0 <= start < stop < 5 range)
        stop_row = QHBoxLayout()
        self.stop_input = QSpinBox()
        self.stop_input.setRange(0, 4)
        self.stop_input.setValue(4)
        stop_row.addWidget(QLabel("Stop Time:"))
        stop_row.addWidget(self.stop_input)
        group_layout.addLayout(stop_row)

        group.setLayout(group_layout)
        layout.addWidget(group)

        self.run_btn = QPushButton("Run Simulation")
        self.run_btn.clicked.connect(self._run_clicked)
        layout.addWidget(self.run_btn)

        layout.addWidget(QLabel("Output:"))
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        layout.addWidget(self.output_box)

        self.setLayout(layout)

    def _pick_exe(self) -> None:
        """Open a file dialog and store the chosen executable path."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Executable", "", "Executable Files (*.exe);;All Files (*)"
        )
        if path:
            self.exe_input.setText(path)

    def _set_busy(self, busy: bool) -> None:
        """Disable input widgets and show a wait cursor while running."""
        self.run_btn.setEnabled(not busy)
        self.run_btn.setText("Running..." if busy else "Run Simulation")
        self.exe_input.setEnabled(not busy)
        self.start_input.setEnabled(not busy)
        self.stop_input.setEnabled(not busy)

        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _run_clicked(self) -> None:
        """Validate inputs, run the simulation, and display the result."""
        exe_path = self.exe_input.text().strip()
        start = self.start_input.value()
        stop = self.stop_input.value()

        runner = SimulationRunner(exe_path, start, stop)

        self._set_busy(True)
        try:
            self.output_box.clear()
            self.output_box.append("Running simulation...\n")
            QApplication.processEvents()
            result = runner.run()
            self.output_box.append(result)
            self.output_box.append("\nDone.")
        except ValueError as e:
            QMessageBox.critical(self, "Invalid Input", str(e))
        except subprocess.TimeoutExpired:
            QMessageBox.critical(
                self,
                "Timeout",
                f"Simulation did not finish within "
                f"{SIMULATION_TIMEOUT_SECONDS} seconds and was aborted.",
            )
        except OSError as e:
            QMessageBox.critical(self, "Execution Error", f"Failed to run:\n{e}")
        finally:
            self._set_busy(False)


def main() -> None:
    """Start the Qt application."""
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()