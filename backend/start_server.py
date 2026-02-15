#!/usr/bin/env python3
"""
Development server startup script for SLPro backend.

This script starts the FastAPI server using uvicorn with development settings.
Run this script from the backend directory to start the local development server.
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    """Start the uvicorn development server."""
    # Get the directory where this script is located (backend directory)
    backend_dir = Path(__file__).parent
    
    # Change to the backend directory
    os.chdir(backend_dir)
    
    # Check if virtual environment exists
    venv_path = backend_dir / ".venv"
    if venv_path.exists():
        print("🔍 Virtual environment found at .venv")
        
        # Determine the python executable path based on OS
        if os.name == 'nt':  # Windows
            python_exe = venv_path / "Scripts" / "python.exe"
        else:  # Unix/Linux/MacOS
            python_exe = venv_path / "bin" / "python"
            
        if python_exe.exists():
            print(f"✅ Using Python from virtual environment: {python_exe}")
        else:
            print("⚠️  Virtual environment found but Python executable not found, using system Python")
            python_exe = sys.executable
    else:
        print("⚠️  No virtual environment found at .venv, using system Python")
        python_exe = sys.executable
    
    # Uvicorn command arguments
    cmd = [
        str(python_exe),
        "-m", "uvicorn",
        "main:app",
        "--reload",
        "--host", "0.0.0.0", 
        "--port", "8000"
    ]
    
    print(f"🚀 Starting SLPro backend server...")
    print(f"📍 Working directory: {backend_dir}")
    print(f"🔧 Command: {' '.join(cmd)}")
    print(f"🌐 Server will be available at: http://localhost:8000")
    print(f"📚 API docs will be available at: http://localhost:8000/docs")
    print("─" * 60)
    
    try:
        # Run the uvicorn command
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user (Ctrl+C)")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"❌ Python executable not found: {python_exe}")
        print("Please ensure Python is installed and the virtual environment is set up correctly.")
        sys.exit(1)


if __name__ == "__main__":
    main()
