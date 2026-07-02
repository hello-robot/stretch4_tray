
from stretch4_tray.stretch_tray_logger import create_stretch_tray_logger

def open_web_browser(url:str):
    _stretch_tray_logger, file_path = create_stretch_tray_logger("browser")
    import webbrowser
    try:
        webbrowser.open(url)
        _stretch_tray_logger.info(f"Opened {url}")
    except Exception as e:
        _stretch_tray_logger.error(f"Error opening {url}: {e}")

def open_documentation():
    """Open the Stretch Robot documentation in the default browser."""
    return open_web_browser('https://docs.hello-robot.com/')
        

if __name__ == "__main__":
    open_documentation()
