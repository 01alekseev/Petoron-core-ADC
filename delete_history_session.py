"""
delete_history_session.py

This script removes local traces of Petoron CLI activity on your computer:
- interface lock file (interface.lock),
- local log file (logs/interface.log),
- Python readline history file (typically ~/.python_history),
- clears the current readline session history.

Use this script to protect your privacy and security by deleting
all local activity traces after finishing work with the CLI.

Run this after disconnecting from the network or exiting the CLI.

WARNING: This script only deletes local files and does not affect any
data on the network.
"""

import os
import pathlib

LOCK_FILE = "interface.lock"
LOG_FILE = "logs/interface.log"

def clear_cli_session():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            print(f"Removed lock file: {LOCK_FILE}")
    except Exception as e:
        print(f"Error removing lock file: {e}")

    try:
        log_path = pathlib.Path(LOG_FILE)
        if log_path.exists():
            log_path.unlink()
            print(f"Removed log file: {LOG_FILE}")
    except Exception as e:
        print(f"Error removing log file: {e}")

    try:
        hist_file = pathlib.Path.home() / ".python_history"
        if hist_file.exists():
            hist_file.unlink()
            print(f"Removed readline history: {hist_file}")
    except Exception as e:
        print(f"Error removing readline history: {e}")

    try:
        import readline
        readline.clear_history()
        print("Cleared readline history for current session.")
    except Exception as e:
        print(f"Error clearing readline history: {e}")

if __name__ == "__main__":
    clear_cli_session()
