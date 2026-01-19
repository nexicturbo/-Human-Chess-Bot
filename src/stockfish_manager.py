"""
Stockfish Manager - Handles automatic download and installation of Stockfish engine
"""
import os
import platform
import stat
import tarfile
import zipfile
import tempfile
import shutil
import requests


# Latest Stockfish version info
STOCKFISH_VERSION = "sf_17.1"
STOCKFISH_BASE_URL = f"https://github.com/official-stockfish/Stockfish/releases/download/{STOCKFISH_VERSION}"

# Download URLs for different platforms
STOCKFISH_URLS = {
    "windows": f"{STOCKFISH_BASE_URL}/stockfish-windows-x86-64-avx2.zip",
    "windows_sse": f"{STOCKFISH_BASE_URL}/stockfish-windows-x86-64.zip",
    "linux": f"{STOCKFISH_BASE_URL}/stockfish-ubuntu-x86-64-avx2.tar",
    "linux_sse": f"{STOCKFISH_BASE_URL}/stockfish-ubuntu-x86-64.tar",
}


def get_stockfish_dir():
    """Get the directory where Stockfish should be stored"""
    # Store in user's home directory under .pawnbit
    home = os.path.expanduser("~")
    stockfish_dir = os.path.join(home, ".pawnbit", "stockfish")
    return stockfish_dir


def get_stockfish_path():
    """Get the path to the Stockfish executable if it exists"""
    stockfish_dir = get_stockfish_dir()

    if platform.system() == "Windows":
        # Look for stockfish.exe in the directory
        exe_path = os.path.join(stockfish_dir, "stockfish-windows-x86-64-avx2.exe")
        if os.path.exists(exe_path):
            return exe_path
        # Try SSE version
        exe_path = os.path.join(stockfish_dir, "stockfish-windows-x86-64.exe")
        if os.path.exists(exe_path):
            return exe_path
        # Try generic name
        exe_path = os.path.join(stockfish_dir, "stockfish.exe")
        if os.path.exists(exe_path):
            return exe_path
    else:
        # Look for stockfish binary on Linux/Mac
        exe_path = os.path.join(stockfish_dir, "stockfish-ubuntu-x86-64-avx2")
        if os.path.exists(exe_path):
            return exe_path
        # Try SSE version
        exe_path = os.path.join(stockfish_dir, "stockfish-ubuntu-x86-64")
        if os.path.exists(exe_path):
            return exe_path
        # Try generic name
        exe_path = os.path.join(stockfish_dir, "stockfish")
        if os.path.exists(exe_path):
            return exe_path

    return None


def is_stockfish_installed():
    """Check if Stockfish is already installed"""
    path = get_stockfish_path()
    return path is not None and os.path.exists(path)


def download_stockfish(progress_callback=None):
    """
    Download and install Stockfish

    Args:
        progress_callback: Optional callback function(percent, message) for progress updates

    Returns:
        str: Path to the installed Stockfish executable, or None if failed
    """
    stockfish_dir = get_stockfish_dir()

    # Create directory if it doesn't exist
    os.makedirs(stockfish_dir, exist_ok=True)

    # Determine which URL to use based on platform
    system = platform.system()

    if system == "Windows":
        url = STOCKFISH_URLS["windows"]
        fallback_url = STOCKFISH_URLS["windows_sse"]
        archive_ext = ".zip"
    else:  # Linux or other Unix-like
        url = STOCKFISH_URLS["linux"]
        fallback_url = STOCKFISH_URLS["linux_sse"]
        archive_ext = ".tar"

    if progress_callback:
        progress_callback(0, "Starting download...")

    # Try to download with AVX2 first, fall back to SSE if needed
    for attempt, download_url in enumerate([url, fallback_url]):
        try:
            if progress_callback:
                progress_callback(5, f"Downloading Stockfish from GitHub...")

            # Download the file
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=archive_ext) as tmp_file:
                tmp_path = tmp_file.name
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp_file.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and progress_callback:
                            percent = int(5 + (downloaded / total_size) * 70)
                            progress_callback(percent, f"Downloading... {downloaded // 1024}KB / {total_size // 1024}KB")

            if progress_callback:
                progress_callback(75, "Extracting...")

            # Extract the archive
            if archive_ext == ".zip":
                with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                    zip_ref.extractall(stockfish_dir)
            else:  # .tar
                with tarfile.open(tmp_path, 'r') as tar_ref:
                    tar_ref.extractall(stockfish_dir)

            # Clean up temp file
            os.unlink(tmp_path)

            if progress_callback:
                progress_callback(90, "Setting permissions...")

            # Find the extracted executable
            stockfish_exe = None
            for root, dirs, files in os.walk(stockfish_dir):
                for file in files:
                    if file.startswith("stockfish") and not file.endswith(('.txt', '.md', '.1')):
                        stockfish_exe = os.path.join(root, file)
                        break
                if stockfish_exe:
                    break

            if stockfish_exe:
                # Move executable to the stockfish_dir if it's in a subdirectory
                final_path = os.path.join(stockfish_dir, os.path.basename(stockfish_exe))
                if stockfish_exe != final_path:
                    shutil.move(stockfish_exe, final_path)
                    stockfish_exe = final_path

                # On Linux, make the file executable
                if system != "Windows":
                    os.chmod(stockfish_exe, os.stat(stockfish_exe).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

                # Clean up extracted directories (keep only the executable)
                for item in os.listdir(stockfish_dir):
                    item_path = os.path.join(stockfish_dir, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)

                if progress_callback:
                    progress_callback(100, "Installation complete!")

                return stockfish_exe
            else:
                if progress_callback:
                    progress_callback(0, "Could not find Stockfish executable in archive")
                continue

        except requests.exceptions.RequestException as e:
            if attempt == 0:
                # Try fallback URL
                if progress_callback:
                    progress_callback(0, "AVX2 version failed, trying SSE version...")
                continue
            else:
                if progress_callback:
                    progress_callback(0, f"Download failed: {str(e)}")
                return None
        except Exception as e:
            if progress_callback:
                progress_callback(0, f"Installation failed: {str(e)}")
            return None

    return None


def verify_stockfish(path):
    """
    Verify that the Stockfish executable works

    Args:
        path: Path to the Stockfish executable

    Returns:
        bool: True if Stockfish works, False otherwise
    """
    if not path or not os.path.exists(path):
        return False

    try:
        import subprocess
        result = subprocess.run(
            [path, "uci"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "uciok" in result.stdout
    except Exception:
        return False


if __name__ == "__main__":
    # Test the manager
    def print_progress(percent, message):
        print(f"[{percent:3d}%] {message}")

    if is_stockfish_installed():
        path = get_stockfish_path()
        print(f"Stockfish already installed at: {path}")
        print(f"Verification: {'OK' if verify_stockfish(path) else 'FAILED'}")
    else:
        print("Stockfish not found. Downloading...")
        path = download_stockfish(print_progress)
        if path:
            print(f"Installed to: {path}")
            print(f"Verification: {'OK' if verify_stockfish(path) else 'FAILED'}")
        else:
            print("Installation failed!")
