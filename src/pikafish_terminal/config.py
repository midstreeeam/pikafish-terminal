"""Configuration management for Pikafish Terminal."""

import os
from typing import Dict, Any, Optional, Union
import yaml
import logging


class ConfigError(Exception):
    """Exception raised for configuration-related errors."""
    pass


class ConfigManager:
    """Configuration manager for the game."""
    
    def __init__(self):
        """Initialize the configuration manager."""
        self.logger = logging.getLogger(__name__)
        self.config_file = self._get_config_file_path()
        self._config = {}
        self._load_config()
    
    def _get_config_file_path(self) -> str:
        """Get the path to the configuration file from the package directory."""
        try:
            import pikafish_terminal
            package_dir = os.path.dirname(pikafish_terminal.__file__)
            return os.path.join(package_dir, 'config.yaml')
        except Exception:
            # Fallback: look for config.yaml in the same directory as this file
            # This helps during development when the package isn't properly installed
            current_dir = os.path.dirname(os.path.abspath(__file__))
            fallback_config = os.path.join(current_dir, 'config.yaml')
            if os.path.exists(fallback_config):
                return fallback_config
            raise ConfigError("Could not locate package directory for configuration file")
    
    def _load_config(self) -> None:
        """Load configuration from the package's bundled config file."""
        try:
            # Check if the package config file exists
            if not os.path.exists(self.config_file):
                raise ConfigError(f"Package config file not found: {self.config_file}")
            
            with open(self.config_file, 'r') as f:
                self._config = yaml.safe_load(f) or {}
            
            # Validate configuration
            if not self.validate_config():
                raise ConfigError("Configuration validation failed")
            
            self.logger.debug(f"Loaded config from package: {self.config_file}")
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing config file: {e}")
            raise ConfigError(f"Error parsing config file: {e}")
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            raise ConfigError(f"Error loading config: {e}")
    
    def get(self, key: str, default=None):
        """Get a configuration value by key (dot notation supported)."""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_required(self, key: str):
        """Get a required configuration value by key (dot notation supported)."""
        value = self.get(key)
        if value is None:
            raise ConfigError(f"Required configuration key '{key}' not found in config file")
        return value
    
    def get_difficulty(self, level: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Get difficulty configuration by level number or name."""
        difficulties = self.get('difficulties', {})
        
        if not isinstance(difficulties, dict):
            return None
        
        # First try exact match
        if level in difficulties:
            return difficulties[level]
        
        # If input is string, try converting to int
        if isinstance(level, str):
            try:
                int_level = int(level)
                if int_level in difficulties:
                    return difficulties[int_level]
            except ValueError:
                pass
        
        # If input is int, try converting to string
        elif isinstance(level, int):
            str_level = str(level)
            if str_level in difficulties:
                return difficulties[str_level]
        
        return None
    
    def validate_config(self) -> bool:
        """Validate current configuration."""
        try:
            # Check required sections
            required_sections = ['game', 'scoring', 'hints', 'difficulties', 'engine', 'logging', 'ui']
            for section in required_sections:
                if section not in self._config:
                    self.logger.error(f"Missing required config section: {section}")
                    return False
            
            # Validate specific values
            hints_count = self.get_required('hints.default_count')
            if not isinstance(hints_count, int) or hints_count < 1 or hints_count > 20:
                self.logger.error(f"Invalid hints.default_count: {hints_count} (must be 1-20)")
                return False
            
            # Validate scoring section
            scoring_depth = self.get_required('scoring.depth')
            if not isinstance(scoring_depth, int) or scoring_depth < 1 or scoring_depth > 50:
                self.logger.error(f"Invalid scoring.depth: {scoring_depth} (must be 1-50)")
                return False
            
            scoring_time = self.get_required('scoring.time_limit_ms')
            if not isinstance(scoring_time, int) or scoring_time < 100 or scoring_time > 300000:
                self.logger.error(f"Invalid scoring.time_limit_ms: {scoring_time} (must be 100-300000)")
                return False
            
            default_difficulty = self.get_required('game.default_difficulty')
            # For default_difficulty, check if it exists in difficulties section
            if isinstance(default_difficulty, (int, str)) and self.get_difficulty(default_difficulty) is None:
                self.logger.error(f"Default difficulty '{default_difficulty}' not found in difficulties section")
                return False
            
            # Validate difficulties exist
            difficulties = self.get('difficulties', {})
            if not difficulties:
                self.logger.error("No difficulties configured")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Config validation error: {e}")
            return False


# Global config instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager





 