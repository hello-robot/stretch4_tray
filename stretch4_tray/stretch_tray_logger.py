from datetime import datetime
import logging
import os
from pathlib import Path
import sys

# Configuration
LOG_DIR = Path.home() / "stretch_user" / "log" / "system_tray"

# Keep at most this many log files per logger id. Every tray start (and every
# script launched from the menu) creates a new file, so without a cap a crash-looping
# service can fill the directory with tens of thousands of files.
MAX_LOG_FILES_PER_ID = 20

LOG_DIR.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist


def prune_old_logs(id: str, keep: int = MAX_LOG_FILES_PER_ID):
    """Delete all but the newest `keep` log files for this logger id."""
    try:
        # Timestamps are YYYYmmdd_HHMMSS, so lexical order == chronological order
        files = sorted(LOG_DIR.glob(f"{id}_[0-9]*_[0-9]*.log"))
        for old in files[:-keep] if keep > 0 else files:
            old.unlink(missing_ok=True)
    except OSError as e:
        print(f"Warning: could not prune old logs in {LOG_DIR}: {e}")


def create_stretch_tray_logger(id:str, level=logging.INFO):
    prune_old_logs(id, keep=MAX_LOG_FILES_PER_ID - 1)  # leave room for the new file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = LOG_DIR / f'{id}_{timestamp}.log'
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(file_path)
    handler.setFormatter(formatter)
    logger = logging.getLogger(id)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    
    ch = logging.StreamHandler(sys.stdout) # or sys.stderr
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)


    print(f"Logging to {file_path}")

    return logger, file_path
