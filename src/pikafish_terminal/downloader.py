import platform
import requests
import os
import stat
import urllib3
import subprocess
import warnings
from pathlib import Path
from .logging_config import get_logger

from tqdm import tqdm

# Disable all SSL warnings for compatibility
urllib3.disable_warnings()
warnings.filterwarnings("ignore", message=".*urllib3.*", category=Warning)

# Supported platforms
SUPPORTED_PLATFORMS = {
    ("Darwin", "x86_64"): "macos",
    ("Darwin", "arm64"): "macos", 
    ("Linux", "x86_64"): "linux",
    ("Windows", "AMD64"): "windows",
}


def extract_7z_file(archive_path: Path, extract_to: Path) -> None:
    """Extract 7z file using system tools."""
    logger = get_logger('pikafish.downloader')
    
    try:
        # Try using 7z command first
        result = subprocess.run([
            "7z", "x", str(archive_path), f"-o{extract_to}", "-y"
        ], capture_output=True, text=True, check=True)
        logger.info("Extracted using 7z command.")
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    try:
        # Try using 7za (7zip alternative)
        result = subprocess.run([
            "7za", "x", str(archive_path), f"-o{extract_to}", "-y"
        ], capture_output=True, text=True, check=True)
        logger.info("Extracted using 7za command.")
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    try:
        # Try using Python's py7zr library
        import py7zr
        with py7zr.SevenZipFile(archive_path, mode='r') as archive:
            archive.extractall(path=extract_to)
        logger.info("Extracted using py7zr library.")
        return
    except ImportError:
        logger.info("py7zr library not available. Installing...")
        try:
            subprocess.run([
                "pip", "install", "py7zr"
            ], capture_output=True, text=True, check=True)
            import py7zr
            with py7zr.SevenZipFile(archive_path, mode='r') as archive:
                archive.extractall(path=extract_to)
            logger.info("Installed py7zr and extracted successfully.")
            return
        except Exception as e:
            pass
    except Exception as e:
        pass
    
    raise RuntimeError("Unable to extract 7z file. Please install 7z, 7za, or py7zr.")


def download_with_progress(session: requests.Session, url: str, output_path: Path, description: str = "Downloading") -> None:
    """Download a file with progress bar."""
    logger = get_logger('pikafish.downloader')
    
    try:
        with session.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            
            if total_size > 0:
                # Use tqdm progress bar
                with tqdm(
                    desc=description,
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    ascii=True,
                    bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
                ) as pbar:
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
            else:
                # Fallback without progress bar
                with open(output_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            
        logger.info(f"Download successful: {output_path.name}")
        
    except Exception as e:
        logger.info(f"Download with requests failed ({e}), trying curl...")
        result = subprocess.run([
            "curl", "-L", "-o", str(output_path), url
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to download with curl: {result.stderr}")
        logger.info(f"Download successful with curl: {output_path.name}")


def get_pikafish_path() -> Path:
    """Return path to local Pikafish binary, downloading if required."""
    logger = get_logger('pikafish.downloader')
    system = platform.system()
    machine = platform.machine()
    platform_key = (system, machine)
    
    if platform_key not in SUPPORTED_PLATFORMS:
        raise RuntimeError(f"Unsupported platform: {system} {machine}")

    # Use user data directory for downloaded engines
    engine_name = "pikafish.exe" if system == "Windows" else "pikafish"
    
    # Try project root first (for development)
    project_root = Path(__file__).resolve().parent.parent.parent
    engine_path_dev = project_root / engine_name
    if engine_path_dev.is_file():
        return engine_path_dev
    
    # Use user data directory for installed package
    data_dir = get_data_directory()
    
    data_dir.mkdir(parents=True, exist_ok=True)
    engine_path = data_dir / engine_name
    
    if engine_path.is_file():
        return engine_path

    logger.info(f"Pikafish not found. Downloading latest version to {data_dir}...")
    
    # Create a session with SSL verification disabled to handle SSL issues
    session = requests.Session()
    session.verify = False
    
    try:
        # Get the latest release info from GitHub API
        api_url = "https://api.github.com/repos/official-pikafish/Pikafish/releases/latest"
        response = session.get(api_url)
        response.raise_for_status()
        release_data = response.json()
        
        # Find the main release asset (should be .7z file)
        assets = release_data["assets"]
        asset = None
        
        # Look for .7z file first
        for a in assets:
            if a["name"].endswith(".7z"):
                asset = a
                break
        
        # Fallback: look for any compressed file
        if not asset:
            for a in assets:
                if any(a["name"].endswith(ext) for ext in [".zip", ".tar.gz", ".tar.bz2"]):
                    asset = a
                    break
        
        if not asset:
            raise RuntimeError("Could not find a suitable release asset")

        download_url = asset["browser_download_url"]
        filename = asset["name"]
        
    except Exception as e:
        logger.info(f"GitHub API failed ({e}), trying fallback direct download...")
        # Fallback to known download URL
        download_url = "https://github.com/official-pikafish/Pikafish/releases/download/Pikafish-2025-06-23/Pikafish.2025-06-23.7z"
        filename = "Pikafish.2025-06-23.7z"

    archive_path = data_dir / filename

    logger.info(f"Downloading from: {download_url}")
    
    # Download the file with progress bar
    download_with_progress(session, download_url, archive_path, "Pikafish Engine")

    logger.info("Extracting binary...")
    
    # Create temporary extraction directory
    extract_dir = data_dir / "temp_extract"
    extract_dir.mkdir(exist_ok=True)
    
    try:
        # Extract based on file type
        if filename.endswith(".7z"):
            extract_7z_file(archive_path, extract_dir)
        elif filename.endswith(".zip"):
            import zipfile
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
        elif filename.endswith((".tar.gz", ".tar.bz2")):
            import tarfile
            with tarfile.open(archive_path, "r:*") as tar_ref:
                tar_ref.extractall(extract_dir)
        else:
            raise RuntimeError(f"Unsupported archive format: {filename}")
        
        # Find the binary in extracted files
        binary_found = False
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                # Look for pikafish executable
                if (file.lower() == engine_name.lower() or 
                    file.lower().startswith("pikafish") and 
                    (system == "Windows" and file.endswith(".exe") or system != "Windows" and not "." in file)):
                    
                    found_path = Path(root) / file
                    found_path.rename(engine_path)
                    binary_found = True
                    break
            if binary_found:
                break
        
        if not binary_found:
            raise RuntimeError(f"Could not find {engine_name} in extracted files")
            
    finally:
        # Clean up
        if archive_path.exists():
            archive_path.unlink()
        if extract_dir.exists():
            import shutil
            shutil.rmtree(extract_dir)

    # Make executable on Unix-like systems
    if system != "Windows":
        st = os.stat(engine_path)
        os.chmod(engine_path, st.st_mode | stat.S_IEXEC)
    
    # Test if the binary works (especially important for virtualized environments)
    logger.info("Testing binary compatibility...")
    if not test_binary_compatibility(engine_path):
        raise RuntimeError(
            "Downloaded Pikafish binary is not compatible with this system. "
            "This often happens in virtualized environments like Docker or GitHub Codespaces "
            "where the binary may use CPU instructions not available in the virtual machine. "
            "You may need to compile Pikafish from source for your specific environment, "
            "or run this on a physical machine with full CPU instruction support."
        )
    
    # Download neural network file if missing
    nn_file = data_dir / "pikafish.nnue"
    if not nn_file.exists():
        logger.info("Downloading neural network file...")
        download_neural_network(data_dir, session)
    
    logger.info("Download and extraction complete.")
    return engine_path


def test_binary_compatibility(engine_path: Path) -> bool:
    """Test if the downloaded binary is compatible with this system."""
    logger = get_logger('pikafish.downloader')
    
    try:
        logger.debug(f"Testing binary: {engine_path}")
        # Try to run the binary with a simple command
        proc = subprocess.Popen(
            [str(engine_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=str(engine_path.parent)
        )
        
        # Send uci command and wait for response
        try:
            if proc.stdin is not None:
                proc.stdin.write("uci\n")
                proc.stdin.flush()
            else:
                proc.kill()
                logger.info("Binary test failed: Unable to write to stdin")
                return False
            
            import time
            start_time = time.time()
            got_response = False
            
            while time.time() - start_time < 3:  # Shorter timeout for faster detection
                return_code = proc.poll()
                if return_code is not None:
                    # Process has exited
                    if return_code == 0:
                        logger.debug("Binary test passed - clean exit")
                        return True
                    elif return_code == -4:  # SIGILL - Illegal instruction
                        logger.info(f"Binary test failed: Illegal instruction (SIGILL) - binary uses unsupported CPU instructions")
                        return False
                    elif return_code < 0:  # Other signals
                        logger.info(f"Binary test failed: Process terminated by signal {-return_code}")
                        return False
                    else:
                        logger.info(f"Binary test failed: Process exited with code {return_code}")
                        return False
                
                # Check if we got any output indicating the engine is working
                try:
                    if proc.stdout is not None:
                        line = proc.stdout.readline()
                        if line:
                            line = line.strip()
                            logger.debug(f"Engine output: {line}")
                            if "id name Pikafish" in line or "uciok" in line:
                                got_response = True
                                # Send quit and cleanup
                                if proc.stdin is not None:
                                    proc.stdin.write("quit\n")
                                    proc.stdin.flush()
                                try:
                                    proc.wait(timeout=2)
                                except subprocess.TimeoutExpired:
                                    proc.kill()
                                logger.debug("Binary test passed - got expected response")
                                return True
                except:
                    pass
                    
                time.sleep(0.1)
            
            # Timeout - kill process
            proc.kill()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            
            if got_response:
                logger.debug("Binary test passed - got partial response")
                return True
            else:
                logger.info("Binary test failed: No response from engine within timeout")
                return False
            
        except Exception as e:
            logger.info(f"Binary test failed with exception: {e}")
            try:
                proc.kill()
            except:
                pass
            return False
            
    except Exception as e:
        logger.info(f"Failed to start binary test: {e}")
        return False



def download_neural_network(data_dir: Path, session: requests.Session) -> None:
    """Download the required neural network file."""
    logger = get_logger('pikafish.downloader')
    nn_url = "https://github.com/official-pikafish/Networks/releases/download/master-net/pikafish.nnue"
    nn_path = data_dir / "pikafish.nnue"
    
    logger.info(f"Downloading neural network from: {nn_url}")
    download_with_progress(session, nn_url, nn_path, "Neural Network")


def get_data_directory() -> Path:
    """Get the platform-specific data directory where Pikafish files are stored."""
    system = platform.system()
    
    if system == "Windows":
        return Path.home() / "AppData" / "Local" / "pikafish-terminal"
    elif system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "pikafish-terminal"
    else:  # Linux and others
        return Path.home() / ".local" / "share" / "pikafish-terminal"


def cleanup_data_directory() -> None:
    """Remove all downloaded Pikafish files and the data directory."""
    import shutil
    
    logger = get_logger('pikafish.downloader')
    data_dir = get_data_directory()
    
    if not data_dir.exists():
        logger.info("No data directory found - nothing to clean up.")
        return
    
    logger.info(f"Removing Pikafish data directory: {data_dir}")
    try:
        shutil.rmtree(data_dir)
        logger.info("Data directory successfully removed.")
    except Exception as e:
        logger.error(f"Failed to remove data directory: {e}")
        raise


def get_downloaded_files_info() -> dict:
    """Get information about downloaded files."""
    data_dir = get_data_directory()
    
    if not data_dir.exists():
        return {"exists": False, "path": str(data_dir), "files": [], "total_size": 0}
    
    files = []
    total_size = 0
    
    for file_path in data_dir.rglob("*"):
        if file_path.is_file():
            size = file_path.stat().st_size
            files.append({
                "name": file_path.name,
                "path": str(file_path.relative_to(data_dir)),
                "size": size
            })
            total_size += size
    
    return {
        "exists": True,
        "path": str(data_dir),
        "files": files,
        "total_size": total_size
    }
