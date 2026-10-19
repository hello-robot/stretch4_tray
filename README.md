# Overview

<img src="./docs/images/stretch_tray.png" width="500"/>

`stretch4_tray` is an Ubuntu system tray application for displaying battery level and providing a system tray menu for launching Stretch tools or help resources. 

To get up and running, please see the [Installation and Updates](#installation-and-updates) section below.

## Installation and Updates

### Installation

To install `stretch4_tray` and configure it to automatically start up when you log in, run:

```bash
# Install the latest version from PyPI
pip install hello-robot-stretch4-tray

# Install the systemd user service so the tray starts at login
stretch_tray --install

# Start the system tray daemon immediately
stretch_tray --restart
```

#### Updating the Package & Menu Scripts

When a new version is released, you can easily upgrade both the software and your system tray menu scripts:

1. **Upgrade the Python package**:
   ```bash
   pip install -U hello-robot-stretch4-tray
   ```

2. **Update your menu scripts**:
   To fetch any newly added commands or tool scripts, run the factory reset command:
   ```bash
   stretch_tray --factory_reset
   ```
   
   > [!TIP]
   > **Your custom scripts are safe!** If you've modified your `stretch_tray.yaml` configuration, `--factory_reset` automatically backs up your existing configuration to a file named `stretch_tray.yaml.bak_<timestamp>`. You can then open that backup and copy your custom commands back into the newly updated `stretch_tray.yaml` config file.

### Managing `stretch4_tray` Service (Recommended)

The easiest way to run `stretch4_tray` is as a linux systemd user service.

To install and start the service:
```bash
stretch_tray --install
```

Other available management commands:
- `stretch_tray --status`: Check if the service is running and view recent logs
- `stretch_tray --restart`: Restart the service
- `stretch_tray --uninstall`: Stop and remove the service, and uninstall the Python package
- `stretch_tray --kill`: Forcefully stop the service and any dangling processes

To view continuous logs:
```bash
journalctl --user -u stretch_tray.service -f
```

### Configuration

On the first run, `stretch_tray` creates a user-editable configuration file at:
`$HELLO_FLEET_PATH/$HELLO_FLEET_ID/stretch_tray.yaml`

By default, this is a copy of the built-in configuration. You can modify this file to add, remove, or change the tools that appear in the tray and the GUI.

If you want to reset your configuration to the default:
```bash
stretch_tray --factory_reset
```


### Developing

To develop on this package:

```bash
sudo apt update
sudo apt install pkg-config libcairo-dev gir1.2-appindicator3-0.1 libgirepository-2.0-dev

git clone https://github.com/hello-robot/stretch4_tray
cd stretch4_tray

uv venv --system-site-packages --no-managed-python
uv pip install -e .
```


## Edit scripts list

To edit the scripts list that shows up in both the system tray and the GUI, please do the following:

1. Edit your user configuration file at $HELLO_FLEET_PATH/$HELLO_FLEET_ID/stretch_tray.yaml
2. Add or modify commands to match the [ScriptsConfig data model](stretch4_tray/scripts_config.py) schema. 
    - Please reference the docstrings in [ScriptsConfig](stretch4_tray/scripts_config.py) for details on each field.
3. Restart the tray: `stretch_tray --restart`
