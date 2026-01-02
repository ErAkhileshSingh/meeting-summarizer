#!/usr/bin/env python
"""
Meeting Summary App - Complete Setup Script
============================================
Run this script on a new device to set up everything end-to-end.

Usage:
    python setup.py           # Full interactive setup
    python setup.py --check   # Only check dependencies
    python setup.py --install # Skip prompts, install everything
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path
import platform
import urllib.request
import zipfile
import tempfile

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header():
    """Print the setup header."""
    print(f"""
{Colors.BOLD}{Colors.BLUE}╔══════════════════════════════════════════════════════════════╗
║          Meeting Summary App - Complete Setup                 ║
║     1-hour meeting → 5-minute processing with AI              ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}
""")

def print_step(step_num, total, description):
    """Print a step indicator."""
    print(f"\n{Colors.BOLD}[{step_num}/{total}] {description}{Colors.END}")
    print("─" * 60)

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")

def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error(f"Python 3.8+ required. Found: {version.major}.{version.minor}")
        return False
    print_success(f"Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def check_pip():
    """Check if pip is available."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            pip_version = result.stdout.strip().split()[1]
            print_success(f"pip version: {pip_version}")
            return True
    except Exception:
        pass
    print_error("pip not found. Please install pip first.")
    return False

def check_ffmpeg():
    """Check if FFmpeg is installed and accessible."""
    ffmpeg_path = shutil.which("ffmpeg")
    
    if ffmpeg_path:
        try:
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True, text=True, timeout=10
            )
            version_line = result.stdout.split('\n')[0]
            print_success(f"FFmpeg found: {version_line[:60]}")
            return True
        except Exception:
            pass
    
    # Check common Windows paths
    if platform.system() == "Windows":
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        for path in common_paths:
            if Path(path).exists():
                print_success(f"FFmpeg found at: {path}")
                print_warning("FFmpeg is not in PATH. Consider adding it.")
                return True
    
    print_error("FFmpeg NOT FOUND")
    return False

def check_tkinter():
    """Check if Tkinter is available."""
    try:
        import tkinter
        print_success(f"Tkinter version: {tkinter.TkVersion}")
        return True
    except ImportError:
        print_error("Tkinter not found")
        if platform.system() == "Linux":
            print_info("Install with: sudo apt-get install python3-tk")
        return False

def install_ffmpeg_windows():
    """Download and install FFmpeg on Windows."""
    print_info("Downloading FFmpeg for Windows...")
    
    # FFmpeg download URL (gyan.dev builds - reliable source)
    ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    install_path = Path("C:/ffmpeg")
    
    try:
        # Download
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "ffmpeg.zip"
            
            print_info("Downloading FFmpeg (~80MB)... This may take a few minutes.")
            urllib.request.urlretrieve(ffmpeg_url, zip_path)
            print_success("Download complete!")
            
            # Extract
            print_info("Extracting...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
            
            # Find extracted folder
            extracted_dirs = [d for d in Path(tmp_dir).iterdir() if d.is_dir() and d.name.startswith("ffmpeg")]
            if not extracted_dirs:
                raise Exception("Failed to find extracted FFmpeg folder")
            
            extracted_path = extracted_dirs[0]
            
            # Move to install location
            if install_path.exists():
                shutil.rmtree(install_path)
            
            shutil.copytree(extracted_path, install_path)
            print_success(f"FFmpeg installed to: {install_path}")
            
            # Add to PATH for current session
            bin_path = install_path / "bin"
            os.environ["PATH"] = str(bin_path) + os.pathsep + os.environ["PATH"]
            
            print_warning("FFmpeg installed but NOT added to system PATH permanently.")
            print_info(f"To add permanently, add this to your system PATH: {bin_path}")
            print_info("Or run in PowerShell (Admin): [Environment]::SetEnvironmentVariable('Path', $env:Path + ';C:\\ffmpeg\\bin', 'Machine')")
            
            return True
            
    except Exception as e:
        print_error(f"Failed to install FFmpeg: {e}")
        print_info("Please install manually from: https://ffmpeg.org/download.html")
        return False

def upgrade_pip():
    """Upgrade pip to the latest version."""
    print_info("Upgrading pip...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print_success("pip upgraded successfully")
        return True
    else:
        print_warning("Failed to upgrade pip, continuing anyway...")
        return True

def install_requirements():
    """Install Python packages from requirements.txt."""
    req_file = Path(__file__).parent / "requirements.txt"
    
    if not req_file.exists():
        print_error(f"requirements.txt not found at {req_file}")
        return False
    
    print_info("Installing Python packages... This may take several minutes.")
    print_info("(PyTorch and Transformers are large downloads)")
    
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        capture_output=False  # Show live output
    )
    
    if result.returncode == 0:
        print_success("All Python packages installed successfully!")
        return True
    else:
        print_error("Some packages failed to install")
        return False

def verify_installation():
    """Verify all components are working."""
    print("\nVerifying installation...")
    
    checks = []
    
    # Check faster-whisper
    try:
        from faster_whisper import WhisperModel
        print_success("faster-whisper: OK")
        checks.append(True)
    except ImportError as e:
        print_error(f"faster-whisper: FAILED ({e})")
        checks.append(False)
    
    # Check transformers
    try:
        from transformers import BartForConditionalGeneration, BartTokenizer
        print_success("transformers: OK")
        checks.append(True)
    except ImportError as e:
        print_error(f"transformers: FAILED ({e})")
        checks.append(False)
    
    # Check torch
    try:
        import torch
        print_success(f"torch: OK (version {torch.__version__})")
        checks.append(True)
    except ImportError as e:
        print_error(f"torch: FAILED ({e})")
        checks.append(False)
    
    # Check numpy
    try:
        import numpy as np
        print_success(f"numpy: OK (version {np.__version__})")
        checks.append(True)
    except ImportError as e:
        print_error(f"numpy: FAILED ({e})")
        checks.append(False)
    
    # Check scipy
    try:
        import scipy
        print_success(f"scipy: OK (version {scipy.__version__})")
        checks.append(True)
    except ImportError as e:
        print_error(f"scipy: FAILED ({e})")
        checks.append(False)
    
    return all(checks)

def pre_download_models():
    """Optionally pre-download ML models."""
    print("\nModels will be downloaded on first run (~2GB total):")
    print("  • Whisper small model: ~244 MB")
    print("  • DistilBART summarization model: ~1.2 GB")
    
    response = input("\nPre-download models now? [y/N]: ").strip().lower()
    
    if response == 'y':
        print_info("Downloading Whisper model...")
        try:
            from faster_whisper import WhisperModel
            models_dir = Path(__file__).parent / "models" / "faster-whisper"
            models_dir.mkdir(parents=True, exist_ok=True)
            
            model = WhisperModel("small", device="cpu", compute_type="int8", download_root=str(models_dir))
            del model
            print_success("Whisper model downloaded!")
        except Exception as e:
            print_error(f"Failed to download Whisper model: {e}")
        
        print_info("Downloading DistilBART model...")
        try:
            from transformers import BartForConditionalGeneration, BartTokenizer
            model_name = "sshleifer/distilbart-cnn-12-6"
            models_dir = Path(__file__).parent / "models" / "distilbart"
            models_dir.mkdir(parents=True, exist_ok=True)
            
            tokenizer = BartTokenizer.from_pretrained(model_name, cache_dir=str(models_dir))
            model = BartForConditionalGeneration.from_pretrained(model_name, cache_dir=str(models_dir))
            del tokenizer, model
            print_success("DistilBART model downloaded!")
        except Exception as e:
            print_error(f"Failed to download DistilBART model: {e}")

def create_directories():
    """Create necessary project directories."""
    project_root = Path(__file__).parent
    
    dirs = [
        project_root / "models",
        project_root / "models" / "faster-whisper",
        project_root / "models" / "distilbart",
        project_root / "temp",
        project_root / "outputs",
    ]
    
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    print_success("Project directories created")

def main():
    """Main setup function."""
    print_header()
    
    # Parse arguments
    check_only = "--check" in sys.argv
    auto_install = "--install" in sys.argv
    
    total_steps = 6 if not check_only else 4
    current_step = 0
    
    # Step 1: Check Python
    current_step += 1
    print_step(current_step, total_steps, "Checking Python version")
    if not check_python_version():
        print_error("\nSetup cannot continue. Please install Python 3.8+")
        sys.exit(1)
    
    # Step 2: Check pip
    current_step += 1
    print_step(current_step, total_steps, "Checking pip")
    if not check_pip():
        sys.exit(1)
    
    # Step 3: Check FFmpeg
    current_step += 1
    print_step(current_step, total_steps, "Checking FFmpeg")
    ffmpeg_ok = check_ffmpeg()
    
    if not ffmpeg_ok and not check_only:
        if platform.system() == "Windows":
            if auto_install or input("\nInstall FFmpeg automatically? [Y/n]: ").strip().lower() != 'n':
                install_ffmpeg_windows()
                ffmpeg_ok = check_ffmpeg()
        else:
            print_info("Please install FFmpeg manually:")
            print_info("  Ubuntu/Debian: sudo apt-get install ffmpeg")
            print_info("  macOS: brew install ffmpeg")
            print_info("  Or download from: https://ffmpeg.org/download.html")
    
    # Step 4: Check Tkinter
    current_step += 1
    print_step(current_step, total_steps, "Checking Tkinter (GUI)")
    tkinter_ok = check_tkinter()
    
    if check_only:
        print("\n" + "═" * 60)
        print(f"{Colors.BOLD}Dependency Check Complete{Colors.END}")
        print("═" * 60)
        
        if not ffmpeg_ok:
            print_warning("FFmpeg is required for video processing")
        if not tkinter_ok:
            print_warning("Tkinter is required for the GUI")
        
        sys.exit(0 if (ffmpeg_ok and tkinter_ok) else 1)
    
    # Step 5: Install Python packages
    current_step += 1
    print_step(current_step, total_steps, "Installing Python packages")
    
    upgrade_pip()
    
    if not install_requirements():
        print_error("\nFailed to install some packages.")
        print_info("Try running: pip install -r requirements.txt")
        sys.exit(1)
    
    # Step 6: Verify and finalize
    current_step += 1
    print_step(current_step, total_steps, "Verifying installation")
    
    create_directories()
    all_ok = verify_installation()
    
    # Summary
    print("\n" + "═" * 60)
    print(f"{Colors.BOLD}Setup Complete!{Colors.END}")
    print("═" * 60)
    
    if all_ok and ffmpeg_ok and tkinter_ok:
        print_success("All components installed successfully!")
        print(f"""
{Colors.BOLD}To run the application:{Colors.END}
    python fast_video_app.py

{Colors.BOLD}First run will download ML models (~2GB):{Colors.END}
    • Whisper model for transcription
    • DistilBART model for summarization

{Colors.BOLD}Enjoy fast meeting summaries! ⚡{Colors.END}
""")
        
        # Offer to pre-download models
        if not auto_install:
            pre_download_models()
    else:
        print_warning("Setup completed with some issues:")
        if not ffmpeg_ok:
            print_error("  - FFmpeg not found (required for video processing)")
        if not tkinter_ok:
            print_error("  - Tkinter not found (required for GUI)")
        if not all_ok:
            print_error("  - Some Python packages failed verification")
        
        print_info("\nPlease resolve the issues above and run setup again.")

if __name__ == "__main__":
    main()
