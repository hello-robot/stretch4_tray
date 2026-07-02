#!/bin/bash
# Management script for Stretch Tray systemd service

set -e

# Get the absolute path of the script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
USER_NAME="$(whoami)"
USER_HOME="$HOME"


# Detect Python path (prefer venv if available)
if [ -f "$REPO_ROOT/.venv/bin/python3" ]; then
    PYTHON_PATH="$REPO_ROOT/.venv/bin/python3"
else
    PYTHON_PATH="$(which python3)"
fi

# Get HELLO_FLEET_PATH from environment (default to ~/stretch_user if not set)
if [ -z "$HELLO_FLEET_PATH" ]; then
    HELLO_FLEET_PATH="$USER_HOME/stretch_user"
fi

# Detect ROS distribution setup file
if [ -n "$ROS_DISTRO" ] && [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
    ROS_SETUP="/opt/ros/$ROS_DISTRO/setup.bash"
else
    # Find the first available ROS distro if not set
    ROS_SETUP=$(ls -1 /opt/ros/*/setup.bash 2>/dev/null | head -n 1) || true
fi

echo "Detected configuration:"
echo "  Repository root: $REPO_ROOT"
echo "  Script directory: $SCRIPT_DIR"
echo "  User: $USER_NAME"
echo "  Python: $PYTHON_PATH"
echo "  HELLO_FLEET_PATH: $HELLO_FLEET_PATH"
echo "  ROS Setup: $ROS_SETUP"
echo ""

# Function to generate service file content
generate_service() {
    # Determine the ExecStart command based on whether we found a ROS setup to source
    if [ -n "$ROS_SETUP" ]; then
        EXEC_START_CMD="/bin/bash -c \"source $ROS_SETUP && source $USER_HOME/ament_ws/install/setup.bash && stretch_tray\""
    else
        EXEC_START_CMD="/bin/bash -c \"source $USER_HOME/ament_ws/install/setup.bash && stretch_tray\""
    fi

    cat > "$SCRIPT_DIR/stretch_tray.service" << EOF
[Unit]
Description=Stretch Tray System Monitor
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
Environment="GI_TYPELIB_PATH=/usr/lib/girepository-1.0:/usr/lib/x86_64-linux-gnu/girepository-1.0"
Environment="HELLO_FLEET_PATH=$HELLO_FLEET_PATH"
Environment="HELLO_FLEET_ID=$HELLO_FLEET_ID"
Environment="RMW_IMPLEMENTATION=rmw_zenoh_cpp"
Environment="PATH=$USER_HOME/.local/bin:$USER_HOME/bin:$(dirname $PYTHON_PATH):/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
WorkingDirectory=$REPO_ROOT
ExecStart=$EXEC_START_CMD
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical-session.target
EOF
}

# Function to install service
install_service() {
    echo "Installing Stretch Tray systemd user service..."

    # Generate service file with current paths
    echo "Generating service file..."
    generate_service

    # Create user systemd directory if it doesn't exist
    USER_SYSTEMD_DIR="$USER_HOME/.config/systemd/user"
    mkdir -p "$USER_SYSTEMD_DIR"

    # Copy service file to user systemd directory
    echo "Copying service file to $USER_SYSTEMD_DIR/..."
    cp "$SCRIPT_DIR/stretch_tray.service" "$USER_SYSTEMD_DIR/"

    # Reload systemd user daemon
    echo "Reloading systemd user daemon..."
    systemctl --user daemon-reload

    # Enable service to start at login
    echo "Enabling service to start at login..."
    systemctl --user enable stretch_tray.service

    echo ""
    echo "✓ Service installed successfully!"
    echo ""
    echo "To start the service now, run:"
    echo "  systemctl --user start stretch_tray.service"
    echo ""
    echo "Or use this script:"
    echo "  $0 --start"
}

# Function to uninstall service
uninstall_service() {
    echo "Uninstalling Stretch Tray systemd user service..."

    # Stop service if running
    echo "Stopping service..."
    systemctl --user stop stretch_tray.service 2>/dev/null || true

    # Disable service
    echo "Disabling service..."
    systemctl --user disable stretch_tray.service 2>/dev/null || true

    # Remove service file from user directory
    USER_SYSTEMD_DIR="$USER_HOME/.config/systemd/user"
    echo "Removing service file from $USER_SYSTEMD_DIR/..."
    rm -f "$USER_SYSTEMD_DIR/stretch_tray.service"

    # Reload systemd user daemon
    echo "Reloading systemd user daemon..."
    systemctl --user daemon-reload

    echo ""
    echo "✓ Service uninstalled successfully!"
}

# Function to start service
start_service() {
    echo "Starting service..."
    systemctl --user start stretch_tray.service
    echo "✓ Service started!"
}

# Function to stop service
stop_service() {
    echo "Stopping service..."
    systemctl --user stop stretch_tray.service
    echo "✓ Service stopped!"
}

# Function to restart service
restart_service() {
    echo "Restarting service..."
    systemctl --user restart stretch_tray.service
    echo "✓ Service restarted!"
}

# Function to show status
status_service() {
    systemctl --user status stretch_tray.service --no-pager || true
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTION]

Manage Stretch Tray systemd user service.

Options:
  --install     Install and enable service to start at login
  --uninstall   Stop, disable, and remove service
  --start       Start service
  --stop        Stop service
  --restart     Restart service
  --status      Show service status
  --help        Show this help message

Examples:
  $0 --install      # Install service
  $0 --start        # Start service
  $0 --status       # Check status
  $0 --uninstall    # Remove service

Logs:
  journalctl --user -u stretch_tray.service -f

Note: This is a user service, not a system service.
It runs in your user session and has access to your display.
EOF
}

# Main script logic
case "${1:-}" in
    --install)
        install_service
        ;;
    --uninstall)
        uninstall_service
        ;;
    --start)
        start_service
        ;;
    --stop)
        stop_service
        ;;
    --restart)
        restart_service
        ;;
    --status)
        status_service
        ;;
    --help)
        show_usage
        ;;
    *)
        echo "Error: Invalid or missing option"
        echo ""
        show_usage
        exit 1
        ;;
esac

