import json
from pathlib import Path
import asyncio


class AutoSaveDict(dict):
    """Custom dictionary that automatically triggers a save operation when modified (sync-friendly)."""

    def __init__(self, parent_save_callback, lock, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parent_save_callback = parent_save_callback
        self._lock = lock  # Async lock for thread safety

    def __setitem__(self, key, value):
        """Set an item and trigger save."""
        if isinstance(value, dict):
            value = AutoSaveDict(self._parent_save_callback, self._lock, value)
        super().__setitem__(key, value)
        # Schedule save asynchronously
        asyncio.create_task(self._parent_save_callback())

    def __getitem__(self, key):
        """Get an item and wrap it if it's a dictionary."""
        value = super().__getitem__(key)
        if isinstance(value, dict) and not isinstance(value, AutoSaveDict):
            value = AutoSaveDict(self._parent_save_callback, self._lock, value)
            super().__setitem__(key, value)  # Replace with wrapped AutoSaveDict
        return value

    def update(self, *args, **kwargs):
        """Update the dictionary and trigger save."""
        super().update(*args, **kwargs)
        asyncio.create_task(self._parent_save_callback())


class ConfigManager:
    """Configuration Manager that supports auto-save and allows sync-like nested access."""
    _instance = None  # Singleton placeholder

    def __new__(cls, config_file='config.json'):
        if not cls._instance:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.config_file = Path(__file__).parent / config_file
            cls._instance._lock = asyncio.Lock()  # Async lock for thread safety
            asyncio.run(cls._instance._load_config())  # Load config asynchronously
        return cls._instance

    async def _load_config(self):
        """Load configuration from JSON file."""
        if not self.config_file.exists():
            self.config = AutoSaveDict(self.save, self._lock)
        else:
            async with self._lock:
                with open(self.config_file, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    self.config = AutoSaveDict(self.save, self._lock, data)

    async def save(self):
        """Save the current configuration back to the JSON file."""
        async with self._lock:
            with open(self.config_file, 'w', encoding='utf-8') as file:
                json.dump(self.config, file, ensure_ascii=False, indent=4)

    def __getitem__(self, key):
        """Access root-level configuration."""
        return self.config[key]

    def __setitem__(self, key, value):
        """Set root-level configuration."""
        self.config[key] = value