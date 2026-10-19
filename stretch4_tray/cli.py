import subprocess
import os
import sys
from pathlib import Path
import stretch4_tray

def restart_service(service_name):
    result = subprocess.run(["systemctl", "--user", "is-active", "--quiet", service_name])
    if result.returncode == 0:
        print(f"Restarting {service_name}...")
        subprocess.run(["systemctl", "--user", "restart", service_name])
        print(f"✓ {service_name} restarted!")
    else:
        print(f"{service_name} is not currently running.")
        print(f"To start it, try running: systemctl --user start {service_name}")

def restart_tray():
    restart_service("stretch_tray.service")

def status_tray():
    print("Status of stretch_tray.service:\n")
    subprocess.run(["systemctl", "--user", "status", "stretch_tray.service", "--no-pager"])
    print("\n" + "="*50 + "\n")
    print("Tailing Logs (Ctrl+C to exit):\n")
    try:
        subprocess.run(["journalctl", "--user", "-u", "stretch_tray.service", "-n", "50", "-f"])
    except KeyboardInterrupt:
        pass

def _get_repo_root(module_file):
    # Check current working directory first (useful if installed normally but run from repo)
    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, "pyproject.toml")) and os.path.exists(os.path.join(cwd, "stretch4_tray", "systemd_service.sh")):
        return cwd
        
    # Check module path (useful if installed in editable mode)
    possible_root = os.path.dirname(os.path.dirname(module_file))
    if os.path.exists(os.path.join(possible_root, "pyproject.toml")) and os.path.exists(os.path.join(possible_root, "stretch4_tray", "systemd_service.sh")):
        return possible_root
        
    return None

def install_tray():
    repo_root = _get_repo_root(stretch4_tray.__file__)
    if repo_root:
        print(f"Running pip install in {repo_root}...")
        # Run pip install -e .
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", repo_root], check=True)
    else:
        print("Not running from repository. Skipping editable pip installation.")
    
    print("Installing stretch_tray systemd service...")
    script_path = os.path.join(os.path.dirname(stretch4_tray.__file__), "systemd_service.sh")
    if os.path.exists(script_path):
        env = os.environ.copy()
        env["PYTHON_PATH"] = sys.executable
        subprocess.run([script_path, "--install"], env=env, check=True)
        subprocess.run([script_path, "--start"], env=env, check=True)
    else:
        print("Error: Could not find systemd_service.sh")
        sys.exit(1)
    print("Install complete.")

def uninstall_tray():
    print("Uninstalling stretch_tray systemd service...")
    script_path = os.path.join(os.path.dirname(stretch4_tray.__file__), "systemd_service.sh")
    if os.path.exists(script_path):
        env = os.environ.copy()
        env["PYTHON_PATH"] = sys.executable
        subprocess.run([script_path, "--uninstall"], env=env)
    else:
        print("Note: Could not locate systemd_service.sh, assuming service is already removed or handling manually.")
        
    print("Uninstalling stretch_tray pip package...")
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "hello-robot-stretch4-tray"])
    print("Uninstall complete.")

def kill_tray():
    print("Stopping stretch_tray services...")
    subprocess.run(["systemctl", "--user", "stop", "stretch_tray.service"], stderr=subprocess.DEVNULL)
    print("Killing any remaining stretch_tray processes...")
    subprocess.run(["pkill", "-f", r"stretch_tray\.stretch_tray"])
    subprocess.run(["pkill", "-f", "bin/stretch_tray$"])
    print("Done killing stretch_tray processes.")


def factory_reset(restart_daemon=True):
    """Reset the user configuration file."""
    from datetime import datetime
    import shutil
    from stretch4_tray.get_stretch_version import StretchVersion, get_stretch_version
    stretch_version = get_stretch_version()
    
    if stretch_version == StretchVersion.mock:
        print("Mock version detected. Factory reset is not applicable as built-in config is used.")
        return

    fleet_path = os.environ.get('HELLO_FLEET_PATH')
    fleet_id = os.environ.get('HELLO_FLEET_ID')
    
    if not fleet_path or not fleet_id:
        print("Error: HELLO_FLEET_PATH and HELLO_FLEET_ID environment variables must be set to perform a factory reset.")
        sys.exit(1)

    user_config_file = Path(fleet_path) / fleet_id / "stretch_tray.yaml"
    
    if user_config_file.exists():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = user_config_file.with_name(f"stretch_tray.yaml.bak_{timestamp}")
            shutil.move(str(user_config_file), str(backup_file))
            print(f"✓ Backed up old config {user_config_file} to {backup_file}")
        except Exception as e:
            print(f"Error: Failed to backup user config: {e}")
            return
    else:
        print("No existing user configuration found.")

    # Recreate config with injected version
    try:
        script_dir = Path(__file__).parent
        if stretch_version == StretchVersion.stretch_4:
            default_config = script_dir / "stretch_4_scripts.yaml"
        elif stretch_version == StretchVersion.stretch_3:
            default_config = script_dir / "stretch_3_scripts.yaml"
        else:
            raise NotImplementedError(f"Unsupported stretch version: {stretch_version}")

        from stretch4_tray.stretch_tray import create_user_config_file
        create_user_config_file(default_config, user_config_file)
        print(f"✓ Factory reset complete! Initialized default config at {user_config_file}")
        
        if restart_daemon:
            restart_tray()
    except Exception as e:
        print(f"Error: Failed to create default config: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Stretch Tray CLI", add_help=False)
    
    # Flags
    parser.add_argument("--install", action="store_true", help="Install the tray")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall the tray")
    parser.add_argument("--restart", action="store_true", help="Restart the tray service")
    parser.add_argument("--status", action="store_true", help="Check status and logs")
    parser.add_argument("--kill", action="store_true", help="Kill all tray processes")
    parser.add_argument("--factory-reset", "--factory_reset", action="store_true", dest="factory_reset", help="Reset user configuration to defaults")
    parser.add_argument("--help", action="store_true", help="Show this help message")

    # If user provides flags, handle them and exit
    args, unknown = parser.parse_known_args()
    
    if args.help:
        parser.print_help()
        sys.exit(0)
    elif args.install:
        install_tray()
        sys.exit(0)
    elif args.uninstall:
        uninstall_tray()
        sys.exit(0)
    elif args.restart:
        restart_tray()
        sys.exit(0)
    elif args.status:
        status_tray()
        sys.exit(0)
    elif args.kill:
        kill_tray()
        sys.exit(0)
    elif args.factory_reset:
        factory_reset()
        sys.exit(0)
    
    # If no flags are provided, start the tray application
    from stretch4_tray.stretch_tray import main as tray_main
    # Update sys.argv to remove these flags but keep other potential args for pystray/tk
    sys.argv = [sys.argv[0]] + unknown
    tray_main()
