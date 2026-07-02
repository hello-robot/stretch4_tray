from datetime import datetime
import logging
import os
from pathlib import Path
import sys

# Configuration
LOG_DIR = Path.home() / "stretch_user" / "log" / "system_tray"

LOG_DIR.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist

def create_stretch_tray_logger(id:str, level=logging.INFO):
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
