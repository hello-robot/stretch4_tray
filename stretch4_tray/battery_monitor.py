#!/usr/bin/env python3
"""
Stretch 3 Battery Monitor Module

This script monitors the battery level by polling Stretch Body. If another process is using the PIMU device, it will skip polling until the next interval.

The voltage-to-percentage conversion logic matches the firmware implementation from LightBarManager.cpp in the stretch_firmware repository, which divides the voltage range (10.0V - 12.0V) into 4 equal segments of 25%.
"""

from dataclasses import dataclass
from enum import Enum
import os
import time

from stretch4_tray.get_stretch_version import StretchVersion, get_stretch_version


class BatteryLevel(Enum):
    full = 100
    high = 80
    medium = 50
    low = 20
    critical = 10

@dataclass
class BatteryStatus:
    percentage: float
    voltage: float
    level: BatteryLevel
    timestamp:float
    is_charging: bool

    def get_battery_icon_name(self) -> str:
        if self.is_charging:
            return f"battery-{self.level.name}-charging.png"
        else:
            return f"battery-{self.level.name}.png"


class BatteryMonitorMixin:

    def get_battery_level(self):
        raise Exception("Override this method")
    def connect(self) -> bool:
        raise Exception("Override this method")
    def disconnect(self) -> None:
        raise Exception("Override this method")
    def get_battery_status(self) -> BatteryStatus|None:
        raise Exception("Override this method")
        
        
    def _get_battery_level(self, voltage: float, min_voltage: float, max_volatge:float) -> BatteryLevel:
        """
        This matches the segmented approach from the firmware where the voltage
        range is divided into 4 equal segments.
        """
        dv = (max_volatge - min_voltage) / 4  # 0.5V segments

        if voltage >= max_volatge:
            return BatteryLevel.full
        elif voltage >= (min_voltage + 3 * dv):  # 11.5V - 12.0V (75-100%)
            return BatteryLevel.high
        elif voltage >= (min_voltage + 2 * dv):  # 11.0V - 11.5V (50-75%)
            return BatteryLevel.medium
        elif voltage >= (min_voltage + dv):      # 10.5V - 11.0V (25-50%)
            return BatteryLevel.low
        else:  # Below 10.5V (0-25%)
            return BatteryLevel.critical

class Stretch4BatteryMonitor(BatteryMonitorMixin):
    def __init__(self) -> None:
        super().__init__()

        import stretch4_body.robot.robot_client as rc #type:ignore

        self.robot = rc.RobotClient()

    def connect(self) -> bool:
        return self.robot.startup(allow_different_user_connection=True)
    
    def disconnect(self): ...

    def get_battery_status(self):
        try:
            pimu=self.robot.status["pimu"]
            percentage=pimu["battery_soc"]
            charger_is_charging = pimu["charger_is_charging"]
            voltage = pimu["voltage"]
            return BatteryStatus(
                percentage=percentage,
                voltage=voltage,
                level = self._get_battery_level(percentage, 0, BatteryLevel.high.value),
                timestamp= time.time(),
                is_charging=charger_is_charging
            )
        except:
            return None


class Stretch3BatteryMonitor(BatteryMonitorMixin):
    """
    Monitor battery status for the Stretch robot using the PIMU interface.
    """
    
    # Battery voltage thresholds (matching Stretch firmware LightBarManager.cpp)
    # These values match the firmware's V_BAT_MIN and V_BAT_MAX constants
    VOLTAGE_MIN = 10.0       # 0% - Minimum voltage (V_BAT_MIN from firmware)
    VOLTAGE_MAX = 12.0       # 100% - Maximum voltage (V_BAT_MAX from firmware)
    
    def __init__(self):
        self.pimu_device = None
        
    def connect(self) -> bool:

        import stretch_body.pimu as pimu  #type:ignore
        """
        Connect to the PIMU device.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.pimu_device = pimu.Pimu()
            
            if not self.pimu_device.startup():
                return False
                
            return True
            
        except Exception as e:
            return False
            
    def disconnect(self):
        """Disconnect from the PIMU device."""
        if self.pimu_device:
            try:
                self.pimu_device.stop()
            except Exception as e:...
            finally:
                self.pimu_device = None
                
    def get_battery_status(self):
        """
        Get current battery status from the PIMU.
        
        Returns:
            Dict containing battery information or None if error
        """
        if not self.pimu_device:
            return None
            
        try:
            # Pull latest status from the device
            self.pimu_device.pull_status()
            status = self.pimu_device.status
            
            voltage = status.get('voltage', 0.0)
            # current = status.get('current', 0.0)
            # temp = status.get('temp', 0.0)
            # low_voltage_alert = status.get('low_voltage_alert', False)
            # charger_connected = status.get('adapter_connected', False)
            charger_is_charging = status.get('charger_is_charging', False)
            
            # Calculate battery percentage
            percentage = self._voltage_to_percentage(voltage)
            
            # Determine battery level category
            level = self._get_battery_level(voltage, self.VOLTAGE_MIN, self.VOLTAGE_MAX)
            
            return BatteryStatus(
                percentage=percentage,
                voltage=voltage,
                level =level,
                timestamp= time.time(),
                is_charging=charger_is_charging
            ) 
            
        except Exception as e:
            return None
            
    def _voltage_to_percentage(self, voltage: float) -> int:
        """
        Convert battery voltage to percentage using firmware logic.

        This matches the logic from LightBarManager.cpp ColoredBatteryLevel function
        which divides the voltage range into 4 equal segments (25% each).

        Args:
            voltage: Battery voltage in volts

        Returns:
            Battery percentage (0-100)
        """
        v_bat_min = self.VOLTAGE_MIN
        v_bat_max = self.VOLTAGE_MAX

        # Handle edge cases
        if voltage <= v_bat_min:
            return 0
        elif voltage >= v_bat_max:
            return 100

        # Divide voltage range into 4 equal segments (matching firmware logic)
        dv = (v_bat_max - v_bat_min) / 4  # Each segment = 0.5V for 10.0-12.0V range

        # Calculate percentage based on which segment the voltage falls into
        if voltage < (v_bat_min + dv):  # 10.0 - 10.5V = 0-25%
            segment_progress = (voltage - v_bat_min) / dv
            percentage = segment_progress * 25
        elif voltage < (v_bat_min + 2 * dv):  # 10.5 - 11.0V = 25-50%
            segment_progress = (voltage - (v_bat_min + dv)) / dv
            percentage = 25 + segment_progress * 25
        elif voltage < (v_bat_min + 3 * dv):  # 11.0 - 11.5V = 50-75%
            segment_progress = (voltage - (v_bat_min + 2 * dv)) / dv
            percentage = 50 + segment_progress * 25
        else:  # 11.5 - 12.0V = 75-100%
            segment_progress = (voltage - (v_bat_min + 3 * dv)) / dv
            percentage = 75 + segment_progress * 25

        return int(max(0, min(100, percentage)))
            

class MockBatteryMonitor(Stretch4BatteryMonitor):
    class Robot:
        def startup(self):
            return True
        
        status = {
            "pimu": {
                "battery_soc": 85,
                "charger_is_charging": True,
                "voltage_36v0": 30.0
            }
        }

    def __init__(self) -> None:
        self.robot = MockBatteryMonitor.Robot()


def get_battery_monitor():
    stretch_version = get_stretch_version()

    if stretch_version == StretchVersion.stretch_3:
        return Stretch3BatteryMonitor()
    elif stretch_version == StretchVersion.stretch_4:
        return Stretch4BatteryMonitor()
    elif stretch_version == StretchVersion.mock:
        return MockBatteryMonitor()

    raise NotImplementedError(f"Unsupported stretch version: {stretch_version}")

def main():
    monitor = get_battery_monitor()
    
    if not monitor.connect():
        print("Failed to connect to Stretch")
        return
        
    try:
        # Get battery status
        status = monitor.get_battery_status()
        if status:
            print(f"Battery Status: {status}")
        else:
            print("Failed to get battery status")
            
    finally:
        monitor.disconnect()


if __name__ == "__main__":
    main()
