"""
Maia Chess Manager - Subprocess-based wrapper for Maia-1 neural network
Uses a separate process with lc0 engine and Maia weights.
This is the REAL Maia (same as maiachess.com), not the maia2 pip package.
"""
import subprocess
import sys
import os
import json


class MaiaProcess:
    """
    Manages a Maia worker subprocess for inference.
    Communicates via JSON over stdin/stdout pipes.
    """

    def __init__(self, elo: int = 1500, time_control: str = "blitz"):
        """
        Start the Maia worker subprocess.

        Args:
            elo: Target ELO rating (1100-1900, will be rounded to nearest 100)
            time_control: Time control for thinking time calculation ("bullet", "blitz", "rapid")
        """
        self.process = None
        self.elo = elo
        self.time_control = time_control

    def start(self) -> bool:
        """
        Start the worker process and initialize Maia (lc0 with Maia weights).

        Returns:
            True if initialization succeeded, False otherwise

        Raises:
            RuntimeError: If initialization fails
        """
        # Find the worker script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        worker_path = os.path.join(script_dir, "maia_worker.py")

        if not os.path.exists(worker_path):
            raise RuntimeError(f"Maia worker script not found: {worker_path}")

        # Start the subprocess
        try:
            self.process = subprocess.Popen(
                [sys.executable, worker_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                cwd=script_dir
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start Maia worker: {e}")

        # Send initialization parameters
        init_params = {
            "elo": self.elo,
            "time_control": self.time_control
        }
        self._send(init_params)

        # Wait for ready signal (lc0 startup is fast, no download needed)
        response = self._receive(timeout=30)
        if response is None:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            self.stop()
            raise RuntimeError(f"Maia worker did not respond. Stderr: {stderr}")

        if "error" in response:
            self.stop()
            raise RuntimeError(f"Maia initialization failed: {response['error']}")

        if response.get("status") != "ready":
            self.stop()
            raise RuntimeError(f"Unexpected response: {response}")

        return True

    def get_move(self, fen: str, elo_self: int, elo_oppo: int, move_count: int = 0) -> tuple:
        """
        Get a move from Maia for the given position.

        Args:
            fen: FEN string of current position
            elo_self: Simulated ELO of the player (1100-1900)
            elo_oppo: ELO of opponent (not used by Maia-1, kept for API compatibility)
            move_count: Number of moves played so far

        Returns:
            (move_uci, think_time) - UCI move string and delay in seconds

        Raises:
            RuntimeError: If the worker is not running or returns an error
        """
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("Maia worker is not running")

        request = {
            "fen": fen,
            "elo_self": elo_self,
            "elo_oppo": elo_oppo,
            "move_count": move_count
        }
        self._send(request)

        response = self._receive(timeout=30)
        if response is None:
            raise RuntimeError("Maia worker did not respond")

        if "error" in response:
            raise RuntimeError(f"Maia inference error: {response['error']}")

        return response["move"], response.get("think_time", 1.0)

    def stop(self):
        """Stop the worker subprocess."""
        if self.process:
            try:
                self._send_raw("QUIT\n")
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            finally:
                self.process = None

    def _send(self, data: dict):
        """Send JSON data to the worker."""
        self._send_raw(json.dumps(data) + "\n")

    def _send_raw(self, text: str):
        """Send raw text to the worker."""
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(text)
                self.process.stdin.flush()
            except:
                pass

    def _receive(self, timeout: float = 30) -> dict:
        """Receive JSON response from the worker using threading for Windows compatibility."""
        if not self.process or not self.process.stdout:
            return None

        import threading
        import queue
        import time

        result_queue = queue.Queue()
        stop_event = threading.Event()

        def read_lines():
            """Read lines until we get valid JSON or timeout."""
            try:
                while not stop_event.is_set():
                    line = self.process.stdout.readline()
                    if not line:
                        result_queue.put(None)
                        break
                    line = line.strip()
                    if line:
                        result_queue.put(line)
                        # If it looks like JSON, we might be done
                        if line.startswith('{'):
                            break
            except:
                result_queue.put(None)

        # Start reader thread
        reader = threading.Thread(target=read_lines, daemon=True)
        reader.start()

        # Wait for valid JSON response with timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                line = result_queue.get(timeout=1)
                if line is None:
                    return None
                # Try to parse as JSON
                if line.startswith('{'):
                    try:
                        stop_event.set()
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
                # Non-JSON line (library output) - continue reading
            except queue.Empty:
                continue

        stop_event.set()
        return None

    def __del__(self):
        """Clean up subprocess on deletion."""
        self.stop()


# Convenience functions for backwards compatibility
def initialize_maia(elo: int = 1500, time_control: str = "blitz", device: str = "auto") -> tuple:
    """
    Initialize Maia-1 via subprocess (using lc0 with Maia weights).

    Args:
        elo: Target ELO rating (1100-1900)
        time_control: Time control for thinking time ("bullet", "blitz", "rapid")
        device: Ignored for lc0 (uses CPU, kept for API compatibility)

    Returns:
        (MaiaProcess instance, None) - Second value for API compatibility
    """
    maia = MaiaProcess(elo=elo, time_control=time_control)
    maia.start()
    return maia, None  # Second value for API compatibility


def get_maia_move(maia_process: MaiaProcess, _prepared, fen: str,
                  elo_self: int, elo_oppo: int, move_count: int = 0) -> tuple:
    """
    Get the best move from Maia with human-like thinking time.

    Args:
        maia_process: MaiaProcess instance from initialize_maia
        _prepared: Unused (for API compatibility)
        fen: FEN string of current position
        elo_self: Simulated ELO of the player (1100-1900)
        elo_oppo: ELO of opponent
        move_count: Number of moves played so far

    Returns:
        (move_uci, think_time) - UCI move string and delay in seconds
    """
    return maia_process.get_move(fen, elo_self, elo_oppo, move_count)


def is_maia_available() -> bool:
    """Check if Maia (lc0 + weights) is available."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    lc0_path = os.path.join(project_dir, "engines", "lc0", "lc0.exe")
    weights_path = os.path.join(project_dir, "maia_original", "maia_weights", "maia-1500.pb.gz")

    return os.path.exists(lc0_path) and os.path.exists(weights_path)
