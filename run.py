"""Friendly launcher for non-technical users.

Double-click this (once dependencies are installed) or run:  python run.py
It starts the local server and opens Escriba in your browser automatically.
Nothing is uploaded anywhere — everything runs on this computer.
"""

import threading
import webbrowser

import uvicorn

HOST, PORT = "127.0.0.1", 8000


def _open_browser():
    webbrowser.open(f"http://{HOST}:{PORT}")


if __name__ == "__main__":
    print("\n  Escriba is starting…")
    print(f"  Your browser will open at  http://{HOST}:{PORT}")
    print("  Keep this window open while you work. Close it to stop.\n")
    threading.Timer(1.5, _open_browser).start()
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="warning")
