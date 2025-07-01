import platform
import requests
import os
import stat
import shutil
import time
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
    """Extract 7z file using py7zr library."""
    logger = get_logger('pikafish.downloader')
    
    try:
        import py7zr
        with py7zr.SevenZipFile(archive_path, mode='r') as archive:
            archive.extractall(path=extract_to)
        logger.info("Successfully extracted 7z archive.")
    except ImportError:
        raise RuntimeError(
            "py7zr library is required to extract 7z files. "
            "Install it with: pip install py7zr"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to extract 7z file: {e}")


def download_with_progress(session: requests.Session, url: str, output_path: Path, description: str = "Downloading") -> None:
    """Download a file with progress bar."""
    logger = get_logger('pikafish.downloader')
    
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
    
    # Check if we already have a working engine
    if engine_path.is_file() and test_binary_compatibility(engine_path):
        return engine_path

    logger.info(f"Pikafish not found or incompatible. Trying multiple instruction sets for compatibility...")
    
    # Create a session with SSL verification disabled to handle SSL issues
    session = requests.Session()
    session.verify = False
    
    # Try multiple instruction sets in order of compatibility
    # Based on https://www.pikafish.com/ - different instruction sets for different environments
    if system == "Darwin":
        instruction_sets = ["apple-silicon"]  # macOS only has one variant
    else:
        instruction_sets = [
            "sse41-popcnt",  # Most compatible for virtualized environments
            "ssse3",         # Fallback for older systems
            "avx2",          # Good performance but may not work in VMs
            "bmi2",          # Higher performance
            # Skip the highest performance ones as they're likely to fail in VMs
        ]
    
    return download_compatible_binary(data_dir, engine_name, session, instruction_sets)


def download_compatible_binary(data_dir: Path, engine_name: str, session: requests.Session, instruction_sets: list) -> Path:
    """Download archive and test multiple instruction set variants until we find a compatible one."""
    logger = get_logger('pikafish.downloader')
    system = platform.system()
    
    # Download the main archive once
    logger.info("Downloading Pikafish archive with all instruction set variants...")
    print("📥 Downloading Pikafish engine variants...")
    
    try:
        # Get the latest release info from GitHub API
        api_url = "https://api.github.com/repos/official-pikafish/Pikafish/releases/latest"
        response = session.get(api_url)
        response.raise_for_status()
        release_data = response.json()
        
        # Find the main release asset
        assets = release_data["assets"]
        asset = None
        
        for a in assets:
            if a["name"].endswith(".7z"):
                asset = a
                break
        
        if not asset:
            raise RuntimeError("Could not find release archive")

        download_url = asset["browser_download_url"]
        filename = asset["name"]
        
    except Exception as e:
        logger.info(f"GitHub API failed ({e}), using fallback...")
        download_url = "https://github.com/official-pikafish/Pikafish/releases/download/Pikafish-2025-06-23/Pikafish.2025-06-23.7z"
        filename = "Pikafish.2025-06-23.7z"

    archive_path = data_dir / filename
    
    # Download the file with progress bar
    download_with_progress(session, download_url, archive_path, "Pikafish Archive")

    logger.info("Extracting and testing instruction set variants...")
    print("📦 Extracting instruction set variants...")
    
    # Create temporary extraction directory
    extract_dir = data_dir / "temp_extract"
    extract_dir.mkdir(exist_ok=True)
    
    try:
        # Extract the archive
        if filename.endswith(".7z"):
            extract_7z_file(archive_path, extract_dir)
        elif filename.endswith(".zip"):
            import zipfile
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
        else:
            raise RuntimeError(f"Unsupported archive format: {filename}")
        
        # Find all potential binaries in the extracted files
        potential_binaries = []
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                file_lower = file.lower()
                # Look for pikafish binaries (with or without instruction set suffix)
                if (file_lower.startswith("pikafish") and 
                    (system == "Windows" and file.endswith(".exe") or 
                     system != "Windows" and not "." in file)):
                    
                    # Filter by platform directory structure
                    root_path = Path(root)
                    if system == "Windows" and "windows" in str(root_path).lower():
                        potential_binaries.append(root_path / file)
                    elif system == "Linux" and "linux" in str(root_path).lower():
                        potential_binaries.append(root_path / file)
                    elif system == "Darwin" and "macos" in str(root_path).lower():
                        potential_binaries.append(root_path / file)
        
        if not potential_binaries:
            raise RuntimeError("Could not find any Pikafish binaries in archive")
        
        logger.info(f"Found {len(potential_binaries)} potential binaries")
        print(f"🔍 Found {len(potential_binaries)} engine variants to test")
        
        # Sort binaries by instruction set preference
        def instruction_set_priority(binary_path):
            name = binary_path.name.lower()
            for i, instruction_set in enumerate(instruction_sets):
                if instruction_set in name:
                    return i
            return len(instruction_sets)  # Unknown instruction sets go last
        
        potential_binaries.sort(key=instruction_set_priority)
        
        # Test each binary until we find a compatible one
        for binary_path in potential_binaries:
            instruction_set = "unknown"
            for inst_set in instruction_sets:
                if inst_set in binary_path.name.lower():
                    instruction_set = inst_set
                    break
            
            logger.info(f"Testing binary: {binary_path.name}")
            print(f"🔄 Testing {instruction_set}: {binary_path.name}")
            
            # Copy to final location for testing
            engine_path = data_dir / engine_name
            if engine_path.exists():
                engine_path.unlink()
                
            shutil.copy2(binary_path, engine_path)
            
            # Make executable on Unix-like systems
            if system != "Windows":
                st = os.stat(engine_path)
                os.chmod(engine_path, st.st_mode | stat.S_IEXEC)
            
            # Test compatibility
            if test_binary_compatibility(engine_path):
                logger.info(f"Found compatible binary: {binary_path.name}")
                print(f"✅ Compatible engine found: {instruction_set}")
                
                # Look for neural network file in extracted directory
                nn_file = data_dir / "pikafish.nnue"
                if not nn_file.exists():
                    for root, dirs, files in os.walk(extract_dir):
                        for file in files:
                            if file.lower() == "pikafish.nnue":
                                nn_source = Path(root) / file
                                shutil.copy2(nn_source, nn_file)
                                logger.info("Extracted neural network file from archive")
                                print("📦 Extracted neural network file")
                                break
                        else:
                            continue
                        break
                    
                return engine_path
            else:
                logger.info(f"Binary {binary_path.name} not compatible")
                print(f"❌ {instruction_set} not compatible")
                
    finally:
        # Clean up
        if archive_path.exists():
            archive_path.unlink()
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
    
    # If we get here, none of the binaries worked
    num_tested = len([b for b in potential_binaries if b.exists()]) if 'potential_binaries' in locals() else 0
    raise RuntimeError(
        "Could not find a compatible Pikafish binary for this system.\n"
        f"Tested {num_tested} instruction set variants.\n\n"
        "This often happens in highly restricted virtualized environments like GitHub Codespaces.\n"
        "The environment may not support running any x86_64 binaries.\n\n"
        "Solutions:\n"
        "• Try running on a physical machine\n"
        "• Use a different development environment\n"
        "• Check system compatibility with 'pikafish --info'\n"
        "• Some cloud environments may block binary execution entirely"
    )



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
