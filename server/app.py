"""
server/app.py — SQL Debug Environment Server
OpenEnv Hackathon by Meta × Hugging Face × Scaler School of Technology

Creates the FastAPI application using the OpenEnv framework's
create_fastapi_app helper, which provides standard HTTP and WebSocket
endpoints automatically.
"""

import sys
import os

# Ensure parent directory is on path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openenv.core.env_server import create_fastapi_app
from environment import SQLDebugEnv
from models import SQLAction, SQLObservation

# Create the OpenEnv-compliant FastAPI app.
# Uses the environment class (not instance) as a factory function
# so each WebSocket session gets its own isolated environment.
app = create_fastapi_app(
    SQLDebugEnv,
    SQLAction,
    SQLObservation,
    max_concurrent_envs=50,
)


def main():
    """Entry point for running the OpenEnv server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
