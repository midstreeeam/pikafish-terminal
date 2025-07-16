# Configuration Fix Summary

## Problem
When installing the xiangqi library via pip, users encountered configuration errors:
```
Missing required config section: scoring
Error loading config: Configuration validation failed
Warning: Could not load configuration: Error loading config: Configuration validation failed
Continuing with command line arguments only...
```

The issue was that the library was trying to create and copy configuration files to the user's current directory, which often failed or resulted in missing configuration sections.

## Solution
Modified the configuration handling to **only read from the package's bundled config file** and **never create or copy config files**.

## Changes Made

### 1. Updated `src/pikafish_terminal/config.py`

#### Removed config file creation functionality:
- Removed `_create_default_config()` method
- Removed `shutil` import (no longer needed)

#### Modified `_get_config_file_path()`:
- Now looks for config.yaml in the package directory first
- Added fallback to look in the same directory as config.py (for development)
- No longer creates config files in the current working directory

#### Modified `_load_config()`:
- Now only reads from the package's bundled config.yaml
- Removed logic for creating config files if they don't exist
- Simply raises ConfigError if the package config file is missing

### 2. Updated `README.md`
- Changed description from "Settings are stored in `config.yaml` (auto-created)" 
- To "Settings are loaded from the built-in `config.yaml` file included with the package"

## Key Benefits

1. **No file system permissions issues**: The library no longer tries to write to the user's file system
2. **Consistent configuration**: All users get the same, tested configuration
3. **No missing sections**: The bundled config.yaml includes all required sections
4. **Cleaner deployment**: No unexpected files created in user directories
5. **Better error handling**: Clear error messages if the package config is missing

## Testing Results

After the fix:
```bash
$ PYTHONPATH=src python3 -m pikafish_terminal.cli --config-list
=== Current Configuration ===
Game settings:
  show_score: True
  default_difficulty: 1
  move_history_length: 5

Scoring settings:
  depth: 15
  time_limit_ms: 500

# ... (all sections loaded successfully)
```

The configuration now loads correctly without any warnings or errors, and the library uses the bundled configuration file exclusively.