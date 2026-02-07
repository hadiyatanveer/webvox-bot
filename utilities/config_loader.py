"""
Configuration loader utility for WebVox.
Loads settings from config.yaml with fallback defaults.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """Singleton configuration class for WebVox settings."""
    
    _instance: Optional['Config'] = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls) -> 'Config':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self) -> None:
        """Load configuration from config.yaml."""
        config_path = Path(__file__).parent.parent / "config.yaml"
        
        if config_path.exists():
            with open(config_path, "r") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            # Fallback to example config
            example_path = Path(__file__).parent.parent / "config.example.yaml"
            if example_path.exists():
                with open(example_path, "r") as f:
                    self._config = yaml.safe_load(f) or {}
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Example: config.get('vector_db.similarity_threshold', 0.65)
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value if value is not None else default
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()


# Global config instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config
