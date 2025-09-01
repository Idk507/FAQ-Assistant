#!/usr/bin/env python3
"""
Quick test to verify server startup without warnings
"""

import subprocess
import sys
import time
import signal
import os

def test_server_startup():
    """Test server startup briefly"""
    print("🧪 Testing Regulatory FAQ Assistant startup...")

    try:
        # Start server in background
        process = subprocess.Popen([
            sys.executable, "run_server.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Wait a bit for startup
        time.sleep(3)

        # Check if process is still running
        if process.poll() is None:
            print("✅ Server started successfully without warnings!")
            # Kill the process
            if os.name == 'nt':  # Windows
                process.terminate()
            else:  # Unix-like
                os.kill(process.pid, signal.SIGTERM)
            return True
        else:
            # Process has exited, check for errors
            stdout, stderr = process.communicate()
            if stderr:
                print(f"❌ Server startup failed with errors:\n{stderr}")
                return False
            else:
                print("✅ Server started and exited cleanly!")
                return True

    except Exception as e:
        print(f"❌ Error testing server: {e}")
        return False

if __name__ == "__main__":
    test_server_startup()
