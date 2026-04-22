#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Server startup script with comprehensive encoding fixes
This script ensures UTF-8 encoding is set before any other operations
"""

import os
import sys
import subprocess

# Set all encoding environment variables before any other operations
def set_encoding_environment():
    """Set all necessary encoding environment variables"""
    encoding_vars = {
        'PYTHONUTF8': '1',
        'PYTHONIOENCODING': 'utf-8',
        'LC_ALL': 'en_US.UTF-8',
        'LANG': 'en_US.UTF-8',
        'PYTHONLEGACYWINDOWSSTDIO': 'utf-8',
        'PYTHONHASHSEED': '0'
    }
    
    for key, value in encoding_vars.items():
        os.environ[key] = value
        print(f"Set {key}={value}")

def main():
    """Main function to start the server with proper encoding"""
    print("🔧 Setting up UTF-8 encoding environment...")
    set_encoding_environment()
    
    print("🚀 Starting server with UTF-8 encoding...")
    
    # Change to the backend directory
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)
    
    # Start the uvicorn server
    try:
        subprocess.run([
            sys.executable, '-m', 'uvicorn', 
            'main:app', 
            '--reload', 
            '--host', '127.0.0.1', 
            '--port', '8000'
        ], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
