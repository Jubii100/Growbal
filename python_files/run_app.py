#!/usr/bin/env python3
"""
Runner script for the Growbal Intelligence FastAPI application
"""

import sys
import os
import subprocess
import time

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        'fastapi',
        'uvicorn',
        'gradio',
        'python-dotenv',
        'python-multipart'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print("Please install them with: pip install " + ' '.join(missing))
        return False
    
    return True

def run_application():
    """Run the FastAPI application"""
    print("🚀 Starting Growbal Intelligence Platform...")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        return
    
    # Change to the chat directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("📍 Application will be available at:")
    print("   - Main: http://localhost:8000")
    print("   - Country Selection: http://localhost:8000/country/")
    print("   - Health Check: http://localhost:8000/health")
    print("   - Debug Sessions: http://localhost:8000/debug/sessions")
    print("=" * 50)
    
    try:
        # Run the improved FastAPI app
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "improved_main_app:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
            "--log-level", "info"
        ])
    except KeyboardInterrupt:
        print("\n🔄 Shutting down application...")
    except Exception as e:
        print(f"❌ Error running application: {e}")

if __name__ == "__main__":
    run_application()