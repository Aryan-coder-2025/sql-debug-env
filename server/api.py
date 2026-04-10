"""
server/api.py — Alternative entry point for the SQL Debug Environment.
OpenEnv Hackathon by Meta × Hugging Face × Scaler School of Technology

Re-exports the main FastAPI app for backward compatibility with
deployment configurations that reference server.api:app.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, main  # noqa: F401

if __name__ == "__main__":
    main()
