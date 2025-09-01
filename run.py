#!/usr/bin/env python3
"""
Simple runner script for the Regulatory FAQ Assistant
"""

import subprocess
import sys
import os

def main():
    """Run the FastAPI application"""
    print("🚀 Starting Regulatory FAQ Assistant...")
    print("📍 Application will be available at:")
    print("   http://localhost:8000")
    print("   http://127.0.0.1:8000")
    print("❌ Press Ctrl+C to stop the server")
    print("-" * 50)

    try:
        # Run the server script instead of app.py directly
        subprocess.run([
            sys.executable, "run_server.py"
        ], check=True)

    except KeyboardInterrupt:
        print("\n👋 Shutting down Regulatory FAQ Assistant...")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running application: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ run_server.py not found. Make sure you're in the correct directory.")
        sys.exit(1)

if __name__ == "__main__":
    main()
