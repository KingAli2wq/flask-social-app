"""Entry point for running the FastAPI application with Uvicorn."""
from __future__ import annotations

import os

import uvicorn


def main() -> None:
  port = int(os.getenv("SOCIAL_SERVER_PORT", "8000"))
  reload = os.getenv("UVICORN_RELOAD", "true").lower() == "true"
  uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
  main()
