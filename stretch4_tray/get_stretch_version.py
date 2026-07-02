from enum import Enum
import os


class StretchVersion(Enum):
    stretch_3 = 1
    stretch_4 = 2
    mock = 0
    
def get_stretch_version() -> StretchVersion:
    """Quick hack to get the Stretch body installed on the system"""
    if os.environ.get('STRETCH_TRAY_MOCK', False):
        return StretchVersion.mock
    
    try:
        import stretch4_body  #type:ignore
        return StretchVersion.stretch_4
    except: ...    
    try:
        import stretch_body  #type:ignore
        return StretchVersion.stretch_3
    except: ...


    raise Exception("Could not import stretch_body. Are you running on a robot? Note: You can use `export STRETCH_TRAY_MOCK=1` to mock the battery monitor.")