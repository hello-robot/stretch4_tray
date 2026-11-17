from dataclasses import dataclass
import yaml
from pathlib import Path


@dataclass
class ScriptsConfig:
    key: str
    icon: str
    name: str
    description: str
    category: str
    """Category to group the script into. This is used for the 'All Scripts' submenu in the System Tray Icon."""
    
    command: str
    """Command to execute in a subprocess. This can be a normal cli command run on Stretch"""

    open_terminal: bool
    """If true, a terminal (terminator if available, else gnome-terminal, etc.) will be opened and the command will be run in it. Otherwise, the command will be run in the background and the result returned to the user."""


    separator_after: bool
    """If true, a separator will be added after this item in the menu in the System Tray Icon."""

    visible_in_tray: bool = False
    """If false, this script will not be shown in the System Tray Icon. It will still be available in the 'All Scripts' submenu."""

    @staticmethod
    def load_scripts_config_from_file(config_file: Path) -> dict[str, "ScriptsConfig"]:
        """Load robot scripts configuration from a yaml file with a list of ScriptConfig."""
        with open(config_file, 'r') as f:
            configs = yaml.safe_load(f)

            if isinstance(configs, list):
                script_configs = [
                    config for config in configs
                    if isinstance(config, dict) and 'key' in config
                ]
                return {config['key']: ScriptsConfig(**config) for config in script_configs}

        raise Exception(f"Failed to load scripts config from {config_file}")

    @staticmethod
    def get_unique_categories(scripts: dict[str, "ScriptsConfig"]) -> list[str]:
        """Get a sorted list of unique categories from the scripts."""
        categories = set()
        for script in scripts.values():
            if script.category:
                categories.add(script.category)
        return sorted(categories)