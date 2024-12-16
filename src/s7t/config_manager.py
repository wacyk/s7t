import json
from pathlib import Path


class ConfigManager:
    def __init__(self, config_file='config.json'):
        # Resolve the file path relative to the app root
        self.config_file = Path(__file__).parent / config_file
        self.config = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from JSON file."""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as file:
                self.config = json.load(file)
        else:
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")

    def save_config(self):
        """Save the current configuration to JSON file."""
        with open(self.config_file, 'w', encoding='utf-8') as file:
            json.dump(self.config, file, ensure_ascii=False, indent=4)

    def get(self, key, default=None):
        """Get a configuration value by key."""
        return self.config.get(key, default)

    def update(self, key, value):
        """Update a configuration key with a new value."""
        self.config[key] = value
        self.save_config()

    def update_nested(self, key_path, value):
        """
        Update a nested key in the configuration.
        Example: key_path=["translator_settings", "target_language"]
        """
        d = self.config
        for key in key_path[:-1]:
            d = d.setdefault(key, {})
        d[key_path[-1]] = value
        self.save_config()