import platform
import requests
import os
import stat
import urllib3
import subprocess
import warnings
from pathlib import Path
from logging_config import get_logger

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
    try:
        # Try using 7z command first
        result = subprocess.run([
            "7z", "x", str(archive_path), f"-o{extract_to}", "-y"
        ], capture_output=True, text=True, check=True)
        print("Extracted using 7z command.")
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    try:
        # Try using 7za (7zip alternative)
        result = subprocess.run([
            "7za", "x", str(archive_path), f"-o{extract_to}", "-y"
        ], capture_output=True, text=True, check=True)
        print("Extracted using 7za command.")
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    try:
        # Try using Python's py7zr library
        import py7zr
        with py7zr.SevenZipFile(archive_path, mode='r') as archive:
            archive.extractall(path=extract_to)
        print("Extracted using py7zr library.")
        return
    except ImportError:
        print("py7zr library not available. Installing...")
        try:
            subprocess.run([
                "pip", "install", "py7zr"
            ], capture_output=True, text=True, check=True)
            import py7zr
            with py7zr.SevenZipFile(archive_path, mode='r') as archive:
                archive.extractall(path=extract_to)
            print("Installed py7zr and extracted successfully.")
            return
        except Exception as e:
            pass
    except Exception as e:
        pass
    
    raise RuntimeError("Unable to extract 7z file. Please install 7z, 7za, or py7zr.")


def get_pikafish_path() -> Path:
    """Return path to local Pikafish binary, downloading if required."""
    logger = get_logger('pikafish.downloader')
    system = platform.system()
    machine = platform.machine()
    platform_key = (system, machine)
    
    if platform_key not in SUPPORTED_PLATFORMS:
        raise RuntimeError(f"Unsupported platform: {system} {machine}")

    # Project root is parent of src/
    project_root = Path(__file__).resolve().parent.parent
    engine_name = "pikafish.exe" if system == "Windows" else "pikafish"
    engine_path = project_root / engine_name
    
    if engine_path.is_file():
        return engine_path

    logger.info(f"Pikafish not found. Downloading latest version...")
    
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

    archive_path = project_root / filename

    logger.info(f"Downloading from: {download_url}")
    
    # Download the file
    try:
        with session.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(archive_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("Download successful with requests.")
    except Exception as e:
        print(f"Python requests failed ({e}), trying curl...")
        result = subprocess.run([
            "curl", "-L", "-o", str(archive_path), download_url
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to download with curl: {result.stderr}")
        print("Download successful with curl.")

    print("Extracting binary...")
    
    # Create temporary extraction directory
    extract_dir = project_root / "temp_extract"
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
    
    # Download neural network file if missing
    nn_file = project_root / "pikafish.nnue"
    if not nn_file.exists():
        print("Downloading neural network file...")
        download_neural_network(project_root, session)
    
    logger.info("Download and extraction complete.")
    return engine_path


def download_neural_network(project_root: Path, session: requests.Session) -> None:
    """Download the required neural network file."""
    nn_url = "https://github.com/official-pikafish/Networks/releases/download/master-net/pikafish.nnue"
    nn_path = project_root / "pikafish.nnue"
    
    print(f"Downloading neural network from: {nn_url}")
    try:
        with session.get(nn_url, stream=True) as r:
            r.raise_for_status()
            with open(nn_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("Neural network download successful.")
    except Exception as e:
        print(f"Failed to download neural network with requests ({e}), trying curl...")
        result = subprocess.run([
            "curl", "-L", "-o", str(nn_path), nn_url
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to download neural network with curl: {result.stderr}")
        print("Neural network download successful with curl.")
