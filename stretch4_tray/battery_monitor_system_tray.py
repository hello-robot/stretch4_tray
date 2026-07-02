import threading
import time
from typing import TYPE_CHECKING
from stretch4_tray.battery_monitor import BatteryLevel, get_battery_monitor

if TYPE_CHECKING:
    from stretch4_tray.stretch4_tray import StretchSystemTray


BATTERY_POLL_INTERVAL_MINUTES = 10

class BatteryMonitoring:
    def __init__(self, system_tray:"StretchSystemTray"):
        self.system_tray = system_tray
        self.battery_monitor = get_battery_monitor()
        self.current_battery_status = None
        self.is_server_connected = False


        # Battery update interval from settings
        self.battery_update_interval = 60 * BATTERY_POLL_INTERVAL_MINUTES
        
    def _get_server_status_menu_text(self):
        """Get the server connection status text for the menu."""
        if self.is_server_connected:
            return "Server: Connected"
        return "Server: Disconnected"

    def _get_battery_menu_text(self):
        """Get battery status text for menu."""
        if not self.current_battery_status:
            return "Battery: Unknown"
            
        percentage = self.current_battery_status.percentage
        voltage = self.current_battery_status.voltage
        charging = self.current_battery_status.is_charging
        
        status_text = f"Battery: {percentage}% ({voltage:.1f}V)"
        if charging:
            status_text += " (Charging)"
            
        return status_text
    

    def _update_tray_icon(self):
        """Update the system tray icon based on current battery status."""
        if not self.current_battery_status:
            icon_path = self.system_tray.icons_dir / "tray_icon.png"
            self.system_tray.update_tray_icon(icon_path, self.is_server_connected)
            return

        level = self.current_battery_status.level
        charging = self.current_battery_status.is_charging

        self.system_tray.logger.info(f"Updating tray icon to {level} with charging={charging}")

        icon_path = self.system_tray.icons_dir / self.current_battery_status.get_battery_icon_name()

        self.system_tray.update_tray_icon(icon_path, self.is_server_connected)
        
    def refresh_battery_status(self):
        # Connect, check, and disconnect
        is_connected = False
        try:
            is_connected = self.battery_monitor.connect()
        except Exception as e:
            self.system_tray.logger.error(f"Error connecting to battery monitor: {e}")

        self.is_server_connected = is_connected

        if is_connected:
            status = self.battery_monitor.get_battery_status()

            # Always disconnect after checking
            self.battery_monitor.disconnect()

            if status:
                self.current_battery_status = status
                self._update_tray_icon()

                self.system_tray.logger.info(f"Battery status updated: {status.percentage}% ({status.voltage:.1f}V)")

                # Check for low battery warning
                if status.level == BatteryLevel.low and not status.is_charging:
                    self.system_tray._show_notification("Warning: Low battery detected! Please charge Stretch.")
                
                return True
            
        self.system_tray.logger.warning("Failed to get battery status. Is Stretch Body Server running?")
        self.is_server_connected = False
        self._update_tray_icon()
        return False


    def _start_battery_monitoring(self):
        """Start the battery monitoring thread with immediate initial check."""
        def monitor_battery():
            """Battery monitoring loop with connect-check-disconnect pattern."""
            connection_retry_count = 0
            max_retries = 3
            first_check = True

            while self.system_tray.running:
                self.system_tray.logger.info("Starting battery check cycle...")

                   
                is_success = self.refresh_battery_status()
                if is_success:
                    connection_retry_count = 0
                else:
                    connection_retry_count += 1

                    if connection_retry_count >= max_retries:
                        self.system_tray.logger.error("Max connection retries reached. Will retry on next cycle.")
                        # Reduced notification noise during expected disconnects
                        connection_retry_count = 0  # Reset for next cycle

                # Skip the wait on first check (immediate startup check)
                if first_check:
                    first_check = False
                    self.system_tray.logger.info("Initial battery check complete. Next check in 2 seconds.")
                    time.sleep(2)  # Short delay before starting regular interval
                else:
                    # Wait for next update cycle (10 minutes by default, but 5 seconds if disconnected)
                    interval = self.battery_update_interval if self.is_server_connected else 5
                    self.system_tray.logger.info(f"Battery check complete. Next check in {interval} seconds.")
                    time.sleep(interval)

        # Start monitoring thread
        self.battery_thread = threading.Thread(target=monitor_battery, daemon=True)
        self.battery_thread.start()

