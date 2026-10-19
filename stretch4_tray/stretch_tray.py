#!/usr/bin/env python3
from dataclasses import asdict
import os
import shlex
import threading
import subprocess
import logging
from datetime import datetime
from pathlib import Path

import yaml
import pystray
from pystray import MenuItem as item
from PIL import Image

from stretch4_tray.battery_monitor_system_tray import BatteryMonitoring
from stretch4_tray.get_stretch_version import StretchVersion, get_stretch_version
from stretch4_tray.visible_shell import ExecutionResult, VisibleShell
from stretch4_tray.stretch_tray_logger import create_stretch_tray_logger
from stretch4_tray.scripts_config import ScriptsConfig


def get_package_version() -> str:
    """Get the CalVer version of the package."""
    try:
        from importlib.metadata import version
        return version("hello-robot-stretch4-tray")
    except Exception:
        pass
    try:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            import re
            content = pyproject_path.read_text()
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "0.0.0"


def create_user_config_file(default_config: Path, target_user_config: Path) -> None:
    """Create a user configuration file from default_config with CalVer version injected at the top."""
    pkg_version = get_package_version()
    content = default_config.read_text()
    version_header = f"- version: '{pkg_version}'\n"
    target_user_config.parent.mkdir(parents=True, exist_ok=True)
    target_user_config.write_text(version_header + content)


def get_config_version(config_file: Path) -> str | None:
    if not config_file.exists():
        return None
    try:
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'version' in item:
                        return str(item['version'])
    except Exception:
        pass
    return None


def is_version_ahead(repo_v: str, user_v: str | None) -> bool:
    if not user_v:
        return True
    try:
        from packaging.version import parse as parse_version
        return parse_version(str(repo_v)) > parse_version(str(user_v))
    except ImportError:
        import re
        def parse_simple(v_str):
            return [int(x) for x in re.findall(r'\d+', str(v_str))]
        return parse_simple(repo_v) > parse_simple(user_v)


class StretchSystemTray:
    """
    System tray application for Stretch monitoring and control.
    """

    def __init__(self, use_battery_monitoring: bool):
        """Initialize the system tray application."""
        self.icon: pystray._base.Icon
        self.running = True

        self.logger, file_path =  create_stretch_tray_logger("stretch_system_tray")

        self.battery_monitor = None
        if use_battery_monitoring:
            self.battery_monitor = BatteryMonitoring(self)

        # Paths
        self.script_dir = Path(__file__).parent
        self.icons_dir = self.script_dir / "icons"

        # Determine stretch version
        stretch_version = get_stretch_version()

        if stretch_version == StretchVersion.mock:
            # For mock, use the built-in stretch_4_scripts.yaml directly
            self.user_config_file = self.script_dir / "stretch_4_scripts.yaml"
            self.logger.info(f"Mock version detected. Using built-in config: {self.user_config_file}")
        else:
            # Determine user config path
            fleet_path = os.environ.get('HELLO_FLEET_PATH')
            fleet_id = os.environ.get('HELLO_FLEET_ID')

            if not fleet_path or not fleet_id:
                error_msg = "HELLO_FLEET_PATH and HELLO_FLEET_ID environment variables must be set."
                self.logger.error(error_msg)
                raise EnvironmentError(error_msg)

            user_config_dir = Path(fleet_path) / fleet_id
            self.user_config_file = user_config_dir / "stretch_tray.yaml"

            if stretch_version == StretchVersion.stretch_4:
                default_config = self.script_dir / "stretch_4_scripts.yaml"
            elif stretch_version == StretchVersion.stretch_3:
                default_config = self.script_dir / "stretch_3_scripts.yaml"
            else:
                raise NotImplementedError(f"Unsupported stretch version: {stretch_version}")

            # Check version differences and trigger factory reset if package version is ahead
            if self.user_config_file.exists():
                pkg_version = get_package_version()
                user_version = get_config_version(self.user_config_file)

                if is_version_ahead(pkg_version, user_version):
                    self.logger.info(
                        f"Package CalVer version ({pkg_version}) is ahead of user config version ({user_version}). "
                        "Invoking factory reset..."
                    )
                    from stretch4_tray.cli import factory_reset
                    factory_reset(restart_daemon=False)

            # Initialize user config if it doesn't exist (or was moved by factory reset)
            if not self.user_config_file.exists():
                try:
                    create_user_config_file(default_config, self.user_config_file)
                    self.logger.info(f"Initialized user-editable config at {self.user_config_file}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize user config: {e}")
                    raise e

        self.robot_scripts: dict[str, ScriptsConfig] = (
            ScriptsConfig.load_scripts_config_from_file(self.user_config_file)
        )

        # Initialize shell for visible execution
        self.visible_shell = VisibleShell()

    def update_tray_icon(self, icon_path: Path, is_server_connected: bool = True):
        """Update the system tray icon."""

        try:
            image = Image.open(icon_path)

            if not is_server_connected:
                # Convert the image to grayscale, retaining alpha if present
                image = image.convert("RGBA")
                from PIL import ImageOps
                r, g, b, a = image.split()
                rgb = Image.merge("RGB", (r, g, b))
                gray = ImageOps.grayscale(rgb)
                image = Image.merge("RGBA", (gray, gray, gray, a))

            self.icon.icon = image

            # Update the menu to reflect new battery status
            self._update_menu()
            self.logger.info(
                "Updated tray icon and menu with new battery status"
            )
        except Exception as e:
            self.logger.error(f"Error updating icon: {e}")
            raise e

    def _update_menu(self):
        """Update the system tray menu with current information."""
        if self.icon:
            try:
                self.icon.menu = self.create_menu()
                self.logger.debug("Menu updated successfully")
            except Exception as e:
                self.logger.error(f"Error updating menu: {e}")


    def execute_command(self, command_key: str):
        def run_command():
            try:
                script_config: ScriptsConfig | None = self.robot_scripts.get(
                    command_key
                )
                if script_config is None:
                    self._log_failure(
                        f"Could not determine a command for {command_key=}", True
                    )
                    return

                command = script_config.command
                
                # Resolve relative paths that refer to the package directory
                if "./stretch4_tray/" in command:
                    command = command.replace("./stretch4_tray/", str(self.script_dir) + "/")
                    self.logger.info(f"Resolved relative command path to: {command}")

                visible = script_config.open_terminal

                self.logger.info(f"Executing robot command: {command_key}")
                self._show_notification(f"Executing {command_key} command...")

                # Log the execution
                process_logger, file_path = create_stretch_tray_logger(command_key)

                if visible and self.visible_shell:
                    script_dir = None
                    script_path = command.split(" ")[0]
                    if not script_path or not os.path.exists(script_path):
                        script_dir = os.path.dirname(script_path)

                    result = self.visible_shell.execute_command(command, script_dir, process_logger)
                    self.logger.info(
                        f"Executed {command} for {command_key} in visible terminal, logged to: {file_path}"
                    )
                else:
                    # Execute silently
                    process = subprocess.run(
                        shlex.split(command),
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )

                    # Convert subprocess result to our format
                    result = ExecutionResult(
                        success=process.returncode == 0,
                        returncode=process.returncode,
                        stdout=process.stdout,
                        stderr=process.stderr,
                        command=command,
                        pid=-1,
                    )

                    process_logger.info(command, asdict(result))

                    self.logger.info(
                        f"Executed {command_key} silently, logged to: {file_path}"
                    )

                if result.success:
                    self._log_success(
                        f"Robot command '{command_key}' completed successfully", False
                    )
                else:
                    error_msg = (
                        result.stderr.strip() if result.stderr else "Unknown error"
                    )
                    self._log_failure(
                        f"Robot command '{command_key}' failed: {error_msg}", True
                    )

            except subprocess.TimeoutExpired:
                self._log_failure(
                    f"Error:Robot command '{command_key}' timed out.", True
                )
            except Exception as e:
                self._log_failure(
                    f"Error: Could not execute command '{command_key}': {e}", True
                )

        # Run command in separate thread to avoid blocking UI
        command_thread = threading.Thread(target=run_command, daemon=True)
        command_thread.start()

    def _log_success(self, message: str, show_notification: bool):
        self.logger.info(message)
        if show_notification:
            self._show_notification(message)

    def _log_failure(self, message: str, show_notification: bool):
        self.logger.error(message)
        if show_notification:
            self._show_notification(message)

    def _show_notification(self, message):
        """Show a desktop notification (if available)."""
        try:
            # Try to use notify-send if available
            subprocess.run(
                ["notify-send", "Stretch System Tray", message], check=False, timeout=5
            )
        except Exception:
            ...

    def quit(self):
        self.logger.info("Shutting down Stretch system tray application")
        self.running = False

        # Ensure we disconnect from robot
        if self.battery_monitor is not None:
            try:
                self.battery_monitor.battery_monitor.disconnect()
                self.logger.info("Disconnected from robot during shutdown")
            except Exception as e:
                self.logger.error(f"Error disconnecting during shutdown: {e}")

        if self.icon:
            self.icon.stop()

    def _create_script_menu_item(self, script_config: ScriptsConfig):
        """Create a menu item from a script configuration."""
        key = script_config.key
        icon = script_config.icon
        name = script_config.name

        return item(
            f'{icon + " " if icon else ""}{name}',
            lambda : self.execute_command(key),
        )

    def open_all_scripts_dialog(self):
        """Open a Tkinter dialog showing all scripts grouped by category."""
        def run_dialog():
            import tkinter as tk
            from tkinter import ttk

            def is_dark_mode():
                try:
                    import subprocess
                    result = subprocess.run(['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'], capture_output=True, text=True, timeout=1)
                    if 'prefer-dark' in result.stdout:
                        return True
                except Exception:
                    pass
                return False

            if is_dark_mode():
                # Clean Black Theme
                BG_COLOR = "#000000"
                FG_COLOR = "#ffffff"
                BTN_BG = "#151515"
                BTN_HOVER = "#2a2a2a"
                CAT_COLOR = "#888888"
                ACCENT_COLOR = "#007aff"
            else:
                # Clean White Theme
                BG_COLOR = "#ffffff"
                FG_COLOR = "#000000"
                BTN_BG = "#f5f5f5"
                BTN_HOVER = "#e5e5e5"
                CAT_COLOR = "#666666"
                ACCENT_COLOR = "#007aff"

            root = tk.Tk()
            root.title("Tools")
            root.geometry("450x650")
            root.minsize(350, 400)
            root.configure(bg=BG_COLOR)
            
            # Main container with padding
            main_frame = tk.Frame(root, bg=BG_COLOR)
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)

            # Header
            header_lbl = tk.Label(main_frame, text="Stretch 4 Tools", font=("Helvetica", 20, "bold"), bg=BG_COLOR, fg=FG_COLOR, anchor="w")
            header_lbl.pack(fill="x", pady=(0, 15))

            # Search Bar
            search_frame = tk.Frame(main_frame, bg=BTN_BG, padx=10, pady=8)
            search_frame.pack(fill="x", pady=(0, 15))
            
            search_icon = tk.Label(search_frame, text="🔍", bg=BTN_BG, fg=CAT_COLOR, font=("Helvetica", 12))
            search_icon.pack(side="left")
            
            search_var = tk.StringVar()
            search_entry = tk.Entry(search_frame, textvariable=search_var, bg=BTN_BG, fg=FG_COLOR, insertbackground=FG_COLOR, relief="flat", font=("Helvetica", 12), borderwidth=0)
            search_entry.pack(side="left", fill="x", expand=True, padx=5)
            search_entry.focus_set()

            # Create a canvas for scrolling
            canvas = tk.Canvas(main_frame, bg=BG_COLOR, highlightthickness=0)
            
            # Configure modern looking ttk scrollbar
            style = ttk.Style()
            style.theme_use('default')
            style.configure("Vertical.TScrollbar", gripcount=0, background=BTN_BG, darkcolor=BG_COLOR, lightcolor=BG_COLOR, troughcolor=BG_COLOR, bordercolor=BG_COLOR, arrowcolor=FG_COLOR)
            
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview, style="Vertical.TScrollbar")
            
            scrollable_frame = tk.Frame(canvas, bg=BG_COLOR)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(
                    scrollregion=canvas.bbox("all")
                )
            )

            canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            
            # Make the frame expand to canvas width
            def configure_canvas(event):
                canvas.itemconfig(canvas_frame, width=event.width)
            canvas.bind('<Configure>', configure_canvas)

            canvas.configure(yscrollcommand=scrollbar.set)

            # Bind mouse wheel for linux (button 4 and 5)
            root.bind('<Button-4>', lambda e: canvas.yview_scroll(-1, "units"))
            root.bind('<Button-5>', lambda e: canvas.yview_scroll(1, "units"))

            def rebuild_ui(*args):
                query = search_var.get().lower()
                
                # Clear existing widgets in scrollable_frame
                for widget in scrollable_frame.winfo_children():
                    widget.destroy()
                
                # Group scripts by category and filter
                categories: dict[str, list] = {}
                for script_config in self.robot_scripts.values():
                    # Filter logic
                    name_match = query in script_config.name.lower()
                    cat_match = query in (script_config.category or "").lower()
                    
                    if name_match or cat_match:
                        cat = script_config.category or "Other"
                        if cat not in categories:
                            categories[cat] = []
                        categories[cat].append(script_config)

                sorted_categories = sorted(categories.keys())

                # Build UI items
                for cat in sorted_categories:
                    # Category Header
                    lbl = tk.Label(scrollable_frame, text=cat.upper(), font=("Helvetica", 10, "bold"), bg=BG_COLOR, fg=CAT_COLOR, anchor="w")
                    lbl.pack(pady=(15, 5), fill="x", padx=5)
                    
                    for script_config in categories[cat]:
                        name = script_config.name
                        if script_config.icon:
                            name = f"{script_config.icon}  {name}"
                        
                        def cmd(k=script_config.key):
                            self.execute_command(k)
                            root.destroy()
                            
                        # Custom flat button using tk.Label for easy hover effects
                        btn = tk.Label(scrollable_frame, text=name, font=("Helvetica", 12), bg=BTN_BG, fg=FG_COLOR, cursor="hand2", pady=12, anchor="w", padx=15)
                        btn.pack(fill="x", padx=5, pady=4)
                        
                        # Hover effects
                        btn.bind("<Enter>", lambda e, w=btn: w.configure(bg=BTN_HOVER))
                        btn.bind("<Leave>", lambda e, w=btn: w.configure(bg=BTN_BG))
                        btn.bind("<Button-1>", lambda e, f=cmd: f())

            search_var.trace_add("write", rebuild_ui)
            rebuild_ui()

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Center window on screen
            root.update_idletasks()
            x = (root.winfo_screenwidth() // 2) - (450 // 2)
            y = (root.winfo_screenheight() // 2) - (650 // 2)
            root.geometry(f"+{x}+{y}")
            
            # Make it pop to top
            root.attributes('-topmost', True)
            root.update()
            root.attributes('-topmost', False)

            root.mainloop()

        # Run in a separate thread so it doesn't block the system tray event loop
        threading.Thread(target=run_dialog, daemon=True).start()

    def create_menu(self):
        """Create the system tray menu."""
        menu_items = []

        if self.battery_monitor is not None:
            menu_items += [
                item(
                    self.battery_monitor._get_server_status_menu_text(),
                    self.battery_monitor.refresh_battery_status,
                ),
                item(
                    self.battery_monitor._get_battery_menu_text(),
                    self.battery_monitor.refresh_battery_status,
                    default=True,
                ),
                pystray.Menu.SEPARATOR,
            ]

        # Add robot script commands from JSON config
        for key, script_config in self.robot_scripts.items():
            if not script_config.visible_in_tray:
                continue

            menu_items.append(self._create_script_menu_item(script_config))

            if script_config.separator_after:
                menu_items.append(pystray.Menu.SEPARATOR)

        # Add "All Scripts" button that opens a Tkinter dialog
        menu_items.append(
            item("More...", lambda: self.open_all_scripts_dialog())
        )

        # Add quit
        # menu_items += [pystray.Menu.SEPARATOR, item("Quit", self.quit)]

        return pystray.Menu(*menu_items)

    def run(self):
        """Run using pystray backend."""
        default_icon_path = self.icons_dir / "tray_icon.png"

        icon = Image.open(default_icon_path)

        # Create and run the system tray icon
        self.icon = pystray.Icon(
            "stretch_robot", icon, "Stretch System Tray", menu=self.create_menu()
        )

        self.logger.info("Starting the Stretch system tray icon app")

        # Setup function to run after icon is initialized
        def setup(icon):
            icon.visible = True
            self.logger.info("Icon visibility set to True")
            if self.battery_monitor:
                self.battery_monitor._start_battery_monitoring()

        # Start battery monitoring
        self.icon.run(setup)


def main():
    try:
        app = StretchSystemTray(use_battery_monitoring=True)
        app.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        logging.error(f"Unhandled exception: {e}")


if __name__ == "__main__":
    main()
