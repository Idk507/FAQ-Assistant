#!/usr/bin/env python3
"""
Production-ready server runner for Regulatory FAQ Assistant
"""

import uvicorn
import os
import sys
from pathlib import Path

def main():
    """Run the FastAPI application with proper configuration"""

    # Add current directory to Python path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))

    print("🚀 Starting Regulatory FAQ Assistant Server...")
    print("=" * 50)
    print("📍 Server will be available at:")
    print("   http://localhost:8000")
    print("   http://127.0.0.1:8000")
    print("❌ Press Ctrl+C to stop the server")
    print("=" * 50)

    try:
        # Run with proper import string for reload support
        uvicorn.run(
            "app:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=[str(current_dir)],
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
