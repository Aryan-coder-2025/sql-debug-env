import uvicorn
import sys
import os

# Ensure parent directory is on path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


def main():
    """Entry point for multi-node deployment."""
    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
